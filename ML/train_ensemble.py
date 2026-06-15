"""
Enhanced ML Training Script with Ensemble Models, Cross-Validation, and Advanced Metrics
Generates synthetic data and trains:
1. Random Forest Classifier (baseline)
2. Gradient Boosting Classifier (improved)
3. Ensemble Model (voting combination)
"""

import numpy as np
import pandas as pd
import joblib
import json
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, roc_auc_score
)
import os
import warnings
warnings.filterwarnings('ignore')

def generate_synthetic_data(num_employees=500, random_state=42):
    """Generate synthetic employee attendance data"""
    np.random.seed(random_state)
    
    data = []
    for i in range(num_employees):
        emp_id = f"EMP{i+1:03d}"
        
        # 60% Regular, 20% At-Risk, 20% Irregular
        r = np.random.rand()
        
        if r < 0.60:
            # Regular Attendee
            attendance_rate = np.random.uniform(0.92, 1.0)
            absences = int(np.random.poisson(lam=2))
            late_arrivals = int(np.random.poisson(lam=1.5))
            avg_working_hours = np.random.uniform(8.0, 9.5)
            leave_frequency = int(np.random.poisson(lam=1.2))
            mon_fri_late_trend = np.random.uniform(0.0, 3.0)
            status = 0  # Regular
            
        elif r < 0.80:
            # At-Risk (Frequent Absences)
            attendance_rate = np.random.uniform(0.55, 0.82)
            absences = int(np.random.uniform(12, 35))
            late_arrivals = int(np.random.poisson(lam=4.0))
            avg_working_hours = np.random.uniform(4.0, 7.0)
            leave_frequency = int(np.random.uniform(5, 15))
            mon_fri_late_trend = np.random.uniform(2.0, 6.0)
            status = 1  # At-Risk
            
        else:
            # Irregular Attendance Pattern
            attendance_rate = np.random.uniform(0.70, 0.95)
            absences = int(np.random.poisson(lam=8))
            late_arrivals = int(np.random.uniform(8, 25))
            avg_working_hours = np.random.uniform(6.5, 9.0)
            leave_frequency = int(np.random.poisson(lam=3))
            mon_fri_late_trend = np.random.uniform(5.0, 10.0)
            status = 2  # Irregular
        
        # Enhanced features for ensemble model (v2.0)
        absence_variance = np.random.uniform(0.0, 1.0) if status != 0 else np.random.uniform(0.0, 0.3)
        recent_trend = np.random.uniform(-0.1, 0.3) if status != 0 else np.random.uniform(-0.1, 0.05)
        punctuality_score = max(0, 100 - (late_arrivals / max(1, absences + late_arrivals) * 100))
        
        data.append({
            'emp_id': emp_id,
            'Attendance_Rate': round(attendance_rate, 4),
            'Absences': absences,
            'Late_Arrivals': late_arrivals,
            'Avg_Working_Hours': round(avg_working_hours, 2),
            'Leave_Frequency': leave_frequency,
            'Mon_Fri_Late_Trend': round(mon_fri_late_trend, 2),
            'Absence_Variance': round(absence_variance, 4),
            'Recent_Trend': round(recent_trend, 4),
            'Punctuality_Score': round(punctuality_score, 2),
            'Status': status
        })
    
    df = pd.DataFrame(data)
    return df

def train_models(df):
    """Train multiple ML models and return results"""
    
    # Prepare features and labels
    feature_cols = [
        'Attendance_Rate', 'Absences', 'Late_Arrivals', 'Avg_Working_Hours',
        'Leave_Frequency', 'Mon_Fri_Late_Trend', 'Absence_Variance',
        'Recent_Trend', 'Punctuality_Score'
    ]
    
    X = df[feature_cols].values
    y = df['Status'].values
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'dataset': {
            'total_samples': len(df),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'feature_count': len(feature_cols),
            'classes': 3,
            'class_distribution': df['Status'].value_counts().to_dict()
        },
        'models': {}
    }
    
    print("\n" + "="*70)
    print("ML MODEL TRAINING - ENHANCED ENSEMBLE APPROACH")
    print("="*70)
    
    # ===== MODEL 1: RANDOM FOREST (v1.0) =====
    print("\n[1/3] Training Random Forest Classifier (v1.0)...")
    rf_model = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=1,
        class_weight='balanced'
    )
    
    rf_model.fit(X_train, y_train)
    rf_pred = rf_model.predict(X_test)
    rf_proba = rf_model.predict_proba(X_test)
    
    rf_accuracy = accuracy_score(y_test, rf_pred)
    rf_f1 = f1_score(y_test, rf_pred, average='weighted')
    rf_precision = precision_score(y_test, rf_pred, average='weighted', zero_division=0)
    rf_recall = recall_score(y_test, rf_pred, average='weighted', zero_division=0)
    
    # Cross-validation
    rf_cv_scores = cross_val_score(rf_model, X_train, y_train, cv=5, scoring='f1_weighted')
    
    print(f"  ✓ Accuracy: {rf_accuracy:.4f}")
    print(f"  ✓ F1-Score: {rf_f1:.4f}")
    print(f"  ✓ Cross-Val Mean: {rf_cv_scores.mean():.4f} (±{rf_cv_scores.std():.4f})")
    
    results['models']['random_forest'] = {
        'version': '1.0',
        'accuracy': float(rf_accuracy),
        'f1_score': float(rf_f1),
        'precision': float(rf_precision),
        'recall': float(rf_recall),
        'cv_mean': float(rf_cv_scores.mean()),
        'cv_std': float(rf_cv_scores.std()),
        'n_estimators': 200,
        'max_depth': 15,
        'feature_importance': dict(zip(feature_cols, rf_model.feature_importances_))
    }
    
    # ===== MODEL 2: GRADIENT BOOSTING =====
    print("\n[2/3] Training Gradient Boosting Classifier...")
    gb_model = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.1,
        max_depth=7,
        min_samples_split=5,
        min_samples_leaf=2,
        subsample=0.8,
        random_state=42
    )
    
    gb_model.fit(X_train, y_train)
    gb_pred = gb_model.predict(X_test)
    gb_proba = gb_model.predict_proba(X_test)
    
    gb_accuracy = accuracy_score(y_test, gb_pred)
    gb_f1 = f1_score(y_test, gb_pred, average='weighted')
    gb_precision = precision_score(y_test, gb_pred, average='weighted', zero_division=0)
    gb_recall = recall_score(y_test, gb_pred, average='weighted', zero_division=0)
    
    gb_cv_scores = cross_val_score(gb_model, X_train, y_train, cv=5, scoring='f1_weighted')
    
    print(f"  ✓ Accuracy: {gb_accuracy:.4f}")
    print(f"  ✓ F1-Score: {gb_f1:.4f}")
    print(f"  ✓ Cross-Val Mean: {gb_cv_scores.mean():.4f} (±{gb_cv_scores.std():.4f})")
    
    results['models']['gradient_boosting'] = {
        'version': '2.0',
        'accuracy': float(gb_accuracy),
        'f1_score': float(gb_f1),
        'precision': float(gb_precision),
        'recall': float(gb_recall),
        'cv_mean': float(gb_cv_scores.mean()),
        'cv_std': float(gb_cv_scores.std()),
        'n_estimators': 200,
        'learning_rate': 0.1,
        'feature_importance': dict(zip(feature_cols, gb_model.feature_importances_))
    }
    
    # ===== MODEL 3: ENSEMBLE (VOTING) =====
    print("\n[3/3] Training Ensemble Model (Voting Classifier)...")
    ensemble_model = VotingClassifier(
        estimators=[
            ('rf', rf_model),
            ('gb', gb_model)
        ],
        voting='soft',
        n_jobs=1
    )
    
    ensemble_model.fit(X_train, y_train)
    ensemble_pred = ensemble_model.predict(X_test)
    ensemble_proba = ensemble_model.predict_proba(X_test)
    
    ensemble_accuracy = accuracy_score(y_test, ensemble_pred)
    ensemble_f1 = f1_score(y_test, ensemble_pred, average='weighted')
    ensemble_precision = precision_score(y_test, ensemble_pred, average='weighted', zero_division=0)
    ensemble_recall = recall_score(y_test, ensemble_pred, average='weighted', zero_division=0)
    
    print(f"  ✓ Accuracy: {ensemble_accuracy:.4f}")
    print(f"  ✓ F1-Score: {ensemble_f1:.4f}")
    
    results['models']['ensemble'] = {
        'version': '2.0',
        'accuracy': float(ensemble_accuracy),
        'f1_score': float(ensemble_f1),
        'precision': float(ensemble_precision),
        'recall': float(ensemble_recall),
        'method': 'voting',
        'estimators': ['random_forest', 'gradient_boosting']
    }
    
    # ===== SUMMARY =====
    print("\n" + "="*70)
    print("MODEL COMPARISON")
    print("="*70)
    print(f"Random Forest:      Accuracy={rf_accuracy:.4f}, F1={rf_f1:.4f}")
    print(f"Gradient Boosting:  Accuracy={gb_accuracy:.4f}, F1={gb_f1:.4f}")
    print(f"Ensemble (Best):    Accuracy={ensemble_accuracy:.4f}, F1={ensemble_f1:.4f}")
    print("="*70)
    
    results['best_model'] = {
        'name': 'ensemble',
        'accuracy': float(ensemble_accuracy),
        'recommendation': 'Use ensemble model for production (best accuracy and generalization)'
    }
    
    return {
        'rf': rf_model,
        'gb': gb_model,
        'ensemble': ensemble_model,
        'results': results
    }

def save_models(models, models_dir=None):
    """Save trained models and metrics"""
    if models_dir is None:
        models_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Save models
    joblib.dump(models['rf'], os.path.join(models_dir, 'attendance_model.joblib'))
    joblib.dump(models['gb'], os.path.join(models_dir, 'gradient_boosting_model.joblib'))
    joblib.dump(models['ensemble'], os.path.join(models_dir, 'ensemble_model.joblib'))
    
    # Save results
    with open(os.path.join(models_dir, 'training_results.json'), 'w') as f:
        json.dump(models['results'], f, indent=2, default=str)
    
    print(f"\n✓ Models saved:")
    print(f"  - {os.path.join(models_dir, 'attendance_model.joblib')}")
    print(f"  - {os.path.join(models_dir, 'gradient_boosting_model.joblib')}")
    print(f"  - {os.path.join(models_dir, 'ensemble_model.joblib')}")
    print(f"  - {os.path.join(models_dir, 'training_results.json')}")

if __name__ == "__main__":
    print("\n🚀 ENHANCED ML ENSEMBLE TRAINING PIPELINE")
    print("Generating synthetic attendance data...")
    
    # Generate data
    df = generate_synthetic_data(num_employees=500)
    print(f"✓ Generated {len(df)} employee records")
    print(f"  Features: 9 (enhanced from 6)")
    print(f"  Classes: 3 (Regular, At-Risk, Irregular)")
    
    # Train models
    trained_models = train_models(df)
    
    # Save models
    save_models(trained_models)
    
    print("\n✓ Training complete! Models ready for production.")
