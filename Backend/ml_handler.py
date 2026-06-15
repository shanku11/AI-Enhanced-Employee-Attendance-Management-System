import os
import joblib
import numpy as np
import datetime
from sqlalchemy.orm import Session
from database import Attendance, PredictionCache
from typing import Dict, Tuple
import json

# Retrieve model path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(os.path.dirname(CURRENT_DIR), "ML", "attendance_model_current.joblib")
ENSEMBLE_MODEL_PATH = os.path.join(os.path.dirname(CURRENT_DIR), "ML", "ensemble_model_current.joblib")
LEGACY_MODEL_PATH = os.path.join(os.path.dirname(CURRENT_DIR), "ML", "attendance_model.joblib")
LEGACY_ENSEMBLE_MODEL_PATH = os.path.join(os.path.dirname(CURRENT_DIR), "ML", "ensemble_model.joblib")

# Load models
model = None
ensemble_model = None

if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print(f"[OK] Random Forest model loaded from: {MODEL_PATH}")
    except Exception as e:
        print(f"[WARN] Error loading Random Forest model: {e}")
elif os.path.exists(LEGACY_MODEL_PATH):
    try:
        model = joblib.load(LEGACY_MODEL_PATH)
        print(f"[OK] Legacy Random Forest model loaded from: {LEGACY_MODEL_PATH}")
    except Exception as e:
        print(f"[WARN] Error loading legacy Random Forest model: {e}")

if os.path.exists(ENSEMBLE_MODEL_PATH):
    try:
        ensemble_model = joblib.load(ENSEMBLE_MODEL_PATH)
        print(f"[OK] Ensemble model loaded from: {ENSEMBLE_MODEL_PATH}")
    except Exception as e:
        print(f"[WARN] Error loading Ensemble model: {e}")
elif os.path.exists(LEGACY_ENSEMBLE_MODEL_PATH):
    try:
        ensemble_model = joblib.load(LEGACY_ENSEMBLE_MODEL_PATH)
        print(f"[OK] Legacy Ensemble model loaded from: {LEGACY_ENSEMBLE_MODEL_PATH}")
    except Exception as e:
        print(f"[WARN] Error loading legacy Ensemble model: {e}")

def calculate_employee_features(user_id: int, db: Session) -> Dict:
    """
    Calculate comprehensive features from attendance records for ML inference.
    Includes historical patterns, trends, and anomaly indicators.
    """
    records = db.query(Attendance).filter(Attendance.user_id == user_id).all()
    
    if not records:
        return {
            "Attendance_Rate": 1.0,
            "Absences": 0,
            "Late_Arrivals": 0,
            "Avg_Working_Hours": 8.0,
            "Leave_Frequency": 0,
            "Mon_Fri_Late_Trend": 0.0,
            "Absence_Variance": 0.0,
            "Recent_Trend": 0.0,
            "Punctuality_Score": 100.0
        }
    
    total_days = len(records)
    absences = sum(1 for r in records if r.status == "Absent")
    late_arrivals = sum(1 for r in records if r.status == "Late")
    present_or_late_days = sum(1 for r in records if r.status in ["Present", "Late"])
    
    attendance_rate = present_or_late_days / total_days if total_days > 0 else 1.0
    
    working_hours_list = [r.working_hours for r in records if r.working_hours and r.working_hours > 0]
    avg_working_hours = sum(working_hours_list) / len(working_hours_list) if working_hours_list else 8.0
    
    # Calculate Monday/Friday late trend (0-10 scale)
    mon_fri_lates = sum(1 for r in records if r.status == "Late" and r.date.weekday() in [0, 4])
    mon_fri_late_trend = (mon_fri_lates / late_arrivals * 10.0) if late_arrivals > 0 else 0.0
    
    # Calculate absence variance (trend indicator)
    absence_variance = 0.0
    if len(records) > 1:
        daily_absences = [1 if r.status == "Absent" else 0 for r in records]
        absence_variance = np.var(daily_absences) if len(daily_absences) > 1 else 0.0
    
    # Recent trend (last 7 days vs overall)
    recent_records = records[-7:] if len(records) > 7 else records
    recent_absences = sum(1 for r in recent_records if r.status == "Absent")
    recent_trend = (recent_absences / len(recent_records)) - (absences / total_days) if len(recent_records) > 0 else 0.0
    
    # Punctuality score (0-100)
    punctuality_score = max(0, 100 - (late_arrivals / total_days * 100))
    
    return {
        "Attendance_Rate": round(attendance_rate, 4),
        "Absences": absences,
        "Late_Arrivals": late_arrivals,
        "Avg_Working_Hours": round(avg_working_hours, 2),
        "Leave_Frequency": absences,
        "Mon_Fri_Late_Trend": round(mon_fri_late_trend, 2),
        "Absence_Variance": round(absence_variance, 4),
        "Recent_Trend": round(recent_trend, 4),
        "Punctuality_Score": round(punctuality_score, 2),
        "Total_Days": total_days,
        "Present_Days": total_days - absences
    }

def predict_attendance_behavior(user_id: int, db: Session) -> Dict:
    """
    Predict employee attendance category using ensemble models with confidence scores.
    Uses Random Forest + Gradient Boosting for improved accuracy.
    """
    features = calculate_employee_features(user_id, db)
    
    # Feature vector for model input
    feature_vector = np.array([[
        features["Attendance_Rate"],
        features["Absences"],
        features["Late_Arrivals"],
        features["Avg_Working_Hours"],
        features["Leave_Frequency"],
        features["Mon_Fri_Late_Trend"],
        features["Absence_Variance"],
        features["Recent_Trend"],
        features["Punctuality_Score"]
    ]])
    
    category_map = {
        0: "Regular",
        1: "At-Risk",
        2: "Irregular"
    }
    
    description_map = {
        "Regular": "Consistent attendance with minimal absences and good punctuality.",
        "At-Risk": "Elevated absence rates with declining work hours. Immediate attention recommended.",
        "Irregular": "Frequent late arrivals and unpredictable attendance patterns, especially on Mondays/Fridays."
    }
    
    confidence = 0.0
    prediction = "Regular"
    
    # Try ensemble model first, fall back to single model
    if ensemble_model is not None:
        try:
            pred_class = int(ensemble_model.predict(feature_vector)[0])
            pred_proba = ensemble_model.predict_proba(feature_vector)[0]
            confidence = float(pred_proba[pred_class])
            prediction = category_map.get(pred_class, "Regular")
        except Exception as e:
            print(f"[WARN] Ensemble model error: {e}. Falling back to Random Forest.")
            if model is not None:
                try:
                    pred_class = int(model.predict(feature_vector)[0])
                    pred_proba = model.predict_proba(feature_vector)[0]
                    confidence = float(pred_proba[pred_class])
                    prediction = category_map.get(pred_class, "Regular")
                except:
                    prediction = rule_based_classify(features)
                    confidence = 0.75
            else:
                prediction = rule_based_classify(features)
                confidence = 0.70
    elif model is not None:
        try:
            pred_class = int(model.predict(feature_vector)[0])
            pred_proba = model.predict_proba(feature_vector)[0]
            confidence = float(pred_proba[pred_class])
            prediction = category_map.get(pred_class, "Regular")
        except Exception as e:
            print(f"[WARN] Model error: {e}. Using rule-based classifier.")
            prediction = rule_based_classify(features)
            confidence = 0.75
    else:
        # Rules-based fallback
        prediction = rule_based_classify(features)
        confidence = 0.70
    
    # Cache prediction
    try:
        cache_entry = PredictionCache(
            user_id=user_id,
            prediction_type="behavior_category",
            prediction_value=prediction,
            confidence_score=round(confidence * 100, 2),
            features=features,
            model_version="2.0",
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        )
        db.add(cache_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[WARN] Failed to cache prediction: {e}")
    
    return {
        "user_id": user_id,
        "features": features,
        "prediction": prediction,
        "confidence": round(confidence * 100, 2),
        "description": description_map.get(prediction, "Unknown category"),
        "model_version": "2.0"
    }

def predict_attendance_from_features(features: Dict) -> Dict:
    """
    Predict attendance category from a feature dictionary, used for uploaded
    company CSV files where rows are not yet stored in the local database.
    """
    normalized = {
        "Attendance_Rate": float(features.get("Attendance_Rate", features.get("attendance_rate", 1.0))),
        "Absences": int(float(features.get("Absences", features.get("absences", 0)))),
        "Late_Arrivals": int(float(features.get("Late_Arrivals", features.get("late_count", 0)))),
        "Avg_Working_Hours": float(features.get("Avg_Working_Hours", features.get("avg_hours", 8.0))),
        "Leave_Frequency": int(float(features.get("Leave_Frequency", features.get("leave_frequency", 0)))),
        "Mon_Fri_Late_Trend": float(features.get("Mon_Fri_Late_Trend", features.get("mon_fri_late_trend", 0.0))),
        "Absence_Variance": float(features.get("Absence_Variance", features.get("absence_variance", 0.0))),
        "Recent_Trend": float(features.get("Recent_Trend", features.get("recent_trend", 0.0))),
        "Punctuality_Score": float(features.get("Punctuality_Score", features.get("punctuality_score", 100.0)))
    }

    # Accept uploaded attendance rates as either 0-1 ratios or 0-100 percentages.
    if normalized["Attendance_Rate"] > 1:
        normalized["Attendance_Rate"] = normalized["Attendance_Rate"] / 100.0

    feature_vector = np.array([[
        normalized["Attendance_Rate"],
        normalized["Absences"],
        normalized["Late_Arrivals"],
        normalized["Avg_Working_Hours"],
        normalized["Leave_Frequency"],
        normalized["Mon_Fri_Late_Trend"],
        normalized["Absence_Variance"],
        normalized["Recent_Trend"],
        normalized["Punctuality_Score"]
    ]])

    category_map = {0: "Regular", 1: "At-Risk", 2: "Irregular"}
    description_map = {
        "Regular": "Consistent attendance with minimal absences and good punctuality.",
        "At-Risk": "Elevated absence rates or reduced hours need HR follow-up.",
        "Irregular": "Frequent late arrivals or unstable attendance patterns detected."
    }

    prediction = rule_based_classify(normalized)
    confidence = 70.0

    active_model = ensemble_model or model
    if active_model is not None:
        try:
            pred_class = int(active_model.predict(feature_vector)[0])
            pred_proba = active_model.predict_proba(feature_vector)[0]
            prediction = category_map.get(pred_class, prediction)
            confidence = round(float(pred_proba[pred_class]) * 100, 2)
        except Exception as e:
            print(f"[WARN] Uploaded-row model prediction failed: {e}. Using rule-based label.")

    return {
        "features": normalized,
        "prediction": prediction,
        "confidence": confidence,
        "description": description_map.get(prediction, "Unknown category"),
        "model_version": "2.0"
    }

def detect_attendance_anomalies(user_id: int, db: Session) -> Dict:
    """
    Detect unusual attendance patterns using statistical anomaly detection.
    Flags sudden changes in behavior.
    """
    records = db.query(Attendance).filter(Attendance.user_id == user_id).order_by(Attendance.date).all()
    
    anomalies = []
    
    if len(records) < 5:
        return {"anomalies": [], "anomaly_score": 0.0}
    
    # Check for sudden absence increase
    first_half = records[:len(records)//2]
    second_half = records[len(records)//2:]
    
    first_absence_rate = sum(1 for r in first_half if r.status == "Absent") / len(first_half)
    second_absence_rate = sum(1 for r in second_half if r.status == "Absent") / len(second_half)
    
    if second_absence_rate - first_absence_rate > 0.2:
        anomalies.append({
            "type": "absence_spike",
            "severity": "high",
            "message": f"Absence rate increased by {(second_absence_rate - first_absence_rate)*100:.1f}%"
        })
    
    # Check for sudden lateness increase
    first_late_rate = sum(1 for r in first_half if r.status == "Late") / len(first_half)
    second_late_rate = sum(1 for r in second_half if r.status == "Late") / len(second_half)
    
    if second_late_rate - first_late_rate > 0.3:
        anomalies.append({
            "type": "lateness_spike",
            "severity": "medium",
            "message": f"Late arrivals increased by {(second_late_rate - first_late_rate)*100:.1f}%"
        })
    
    # Check for working hours drop
    first_hours = np.mean([r.working_hours for r in first_half if r.working_hours > 0])
    second_hours = np.mean([r.working_hours for r in second_half if r.working_hours > 0])
    
    if first_hours - second_hours > 2.0:
        anomalies.append({
            "type": "hours_drop",
            "severity": "medium",
            "message": f"Average working hours decreased by {first_hours - second_hours:.1f} hours"
        })
    
    # Calculate anomaly score (0-100)
    anomaly_score = min(100, len(anomalies) * 25)
    
    return {
        "anomalies": anomalies,
        "anomaly_score": anomaly_score,
        "detected_at": datetime.datetime.utcnow().isoformat()
    }

def calculate_absenteeism_risk(user_id: int, db: Session) -> Dict:
    """
    Calculate absenteeism risk score for predictive HR management.
    Higher score = higher risk of absence.
    """
    features = calculate_employee_features(user_id, db)
    
    # Risk factors (0-100 scale)
    absence_risk = min(100, features["Absences"] * 5)
    lateness_risk = min(100, features["Late_Arrivals"] * 3)
    variance_risk = min(100, features["Absence_Variance"] * 50)
    trend_risk = max(0, features["Recent_Trend"] * 100)
    
    # Weighted average
    risk_score = (
        absence_risk * 0.4 +
        lateness_risk * 0.2 +
        variance_risk * 0.2 +
        trend_risk * 0.2
    )
    
    risk_level = "Low"
    if risk_score >= 70:
        risk_level = "Critical"
    elif risk_score >= 50:
        risk_level = "High"
    elif risk_score >= 30:
        risk_level = "Medium"
    
    return {
        "user_id": user_id,
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "risk_factors": {
            "absence_risk": round(absence_risk, 2),
            "lateness_risk": round(lateness_risk, 2),
            "variance_risk": round(variance_risk, 2),
            "trend_risk": round(trend_risk, 2)
        }
    }

def rule_based_classify(features: Dict) -> str:
    """
    Fallback rule-based classifier for when ML models are unavailable.
    """
    if features["Attendance_Rate"] < 0.80:
        return "At-Risk"
    elif features["Late_Arrivals"] >= 8 or features["Mon_Fri_Late_Trend"] >= 5.0:
        return "Irregular"
    else:
        return "Regular"
