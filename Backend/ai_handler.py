import os
import json
import urllib.request
import urllib.error
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

class ChatManager:
    """Manages AI chat sessions with context awareness and history persistence"""
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("GEMINI_API_KEY")
    
    def get_employee_context(self, employee_id: int) -> Dict[str, Any]:
        """Fetch comprehensive employee context for AI awareness"""
        from database import User, Attendance
        from ml_handler import predict_attendance_behavior
        
        user = self.db.query(User).filter(User.id == employee_id).first()
        if not user:
            return {}
        
        # Get attendance data for last 30 days
        today = datetime.now().date()
        thirty_days_ago = today - timedelta(days=30)
        attendances = self.db.query(Attendance).filter(
            Attendance.user_id == employee_id,
            Attendance.date >= thirty_days_ago
        ).all()
        
        # Calculate metrics
        total_days = len(attendances)
        present_days = len([a for a in attendances if a.status == "Present"])
        late_days = len([a for a in attendances if a.status == "Late"])
        absent_days = len([a for a in attendances if a.status == "Absent"])
        avg_working_hours = sum([a.working_hours for a in attendances]) / total_days if total_days > 0 else 0
        
        # Get ML prediction
        try:
            prediction_results = predict_attendance_behavior(employee_id, self.db)
            prediction = prediction_results["prediction"]
            confidence = prediction_results["confidence"]
            features = prediction_results["features"]
        except:
            prediction = "Unknown"
            confidence = 0
            features = {}
        
        # Calculate trend
        first_half = attendances[:len(attendances)//2]
        second_half = attendances[len(attendances)//2:]
        first_half_rate = len([a for a in first_half if a.status in ["Present", "Late"]]) / len(first_half) if first_half else 0
        second_half_rate = len([a for a in second_half if a.status in ["Present", "Late"]]) / len(second_half) if second_half else 0
        trend = "improving" if second_half_rate > first_half_rate else "declining" if second_half_rate < first_half_rate else "stable"
        
        return {
            "name": user.name,
            "department": user.department,
            "role": user.role,
            "total_days_tracked": total_days,
            "present_days": present_days,
            "late_days": late_days,
            "absent_days": absent_days,
            "attendance_rate": present_days / total_days if total_days > 0 else 0,
            "avg_working_hours": round(avg_working_hours, 2),
            "ml_prediction": prediction,
            "confidence_score": confidence,
            "trend": trend,
            "features": features
        }
    
    def build_context_prompt(self, employee_context: Dict[str, Any], query: str) -> str:
        """Build a rich context prompt for HR-focused queries"""
        
        context = employee_context
        context_str = (
            f"EMPLOYEE CONTEXT:\n"
            f"- Name: {context.get('name', 'Unknown')}\n"
            f"- Department: {context.get('department', 'Unknown')}\n"
            f"- Days Tracked (Last 30 Days): {context.get('total_days_tracked', 0)}\n"
            f"- Attendance Rate: {context.get('attendance_rate', 0) * 100:.1f}%\n"
            f"- Present Days: {context.get('present_days', 0)}\n"
            f"- Late Days: {context.get('late_days', 0)}\n"
            f"- Absent Days: {context.get('absent_days', 0)}\n"
            f"- Avg Working Hours: {context.get('avg_working_hours', 0)} hrs/day\n"
            f"- ML Classification: {context.get('ml_prediction', 'Unknown')}\n"
            f"- Classification Confidence: {context.get('confidence_score', 0):.0%}\n"
            f"- Trend: {context.get('trend', 'unknown').upper()}\n"
            f"\nQUEST ION FROM HR MANAGER: {query}"
        )
        return context_str
    
    def generate_chat_response(self, query: str, employee_context: Dict[str, Any], chat_history: List[Dict]) -> str:
        """Generate a contextual response using Gemini API or fallback"""
        
        context_prompt = self.build_context_prompt(employee_context, query)
        
        system_instruction = (
            "You are a Senior HR Analytics Assistant specializing in employee attendance and workforce insights. "
            "Provide clear, actionable, and professional responses based on employee data. "
            "Be specific with metrics and recommendations. Keep responses concise but thorough (2-3 sentences max)."
        )
        
        # Try Gemini API first
        if self.api_key:
            try:
                response = self._call_gemini_api(system_instruction, context_prompt, chat_history)
                if response:
                    return response
            except Exception as e:
                print(f"WARNING: Gemini API call failed: {e}. Using fallback response.")
        
        # Fallback to rule-based response
        return self._generate_fallback_response(query, employee_context)
    
    def _call_gemini_api(self, system_instruction: str, context: str, history: List[Dict]) -> Optional[str]:
        """Call Google Gemini API with system instruction and context"""
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        
        # Build message history
        contents = []
        for msg in history[-5:]:  # Limit to last 5 messages for context
            role = "model" if msg.get("sender") == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("message_text", "")}]
            })
        
        # Add current context and query
        contents.append({
            "role": "user",
            "parts": [{"text": context}]
        })
        
        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 250
            }
        }
        
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
                if "candidates" in res_data and res_data["candidates"]:
                    candidate = res_data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        return candidate["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"Gemini API error: {e}")
            return None
        
        return None
    
    def _generate_fallback_response(self, query: str, context: Dict[str, Any]) -> str:
        """Generate professional fallback responses based on context and query patterns"""
        
        q_lower = query.lower()
        name = context.get("name", "This employee")
        prediction = context.get("ml_prediction", "Unknown")
        attendance_rate = context.get("attendance_rate", 0) * 100
        late_days = context.get("late_days", 0)
        absent_days = context.get("absent_days", 0)
        avg_hours = context.get("avg_working_hours", 0)
        trend = context.get("trend", "stable")
        
        # Pattern-based responses
        if any(word in q_lower for word in ["late", "punctual", "arrival"]):
            if late_days > 5:
                return f"{name} shows {late_days} late arrivals in the past 30 days, indicating a punctuality concern. This aligns with the '{prediction}' classification. Consider discussing scheduling or commute challenges."
            else:
                return f"{name} maintains good punctuality with only {late_days} late arrivals. This demonstrates strong time management."
        
        elif any(word in q_lower for word in ["absent", "absence", "leave"]):
            if absent_days > 4:
                return f"{name} has {absent_days} absences in the last 30 days, resulting in a {attendance_rate:.1f}% attendance rate. Urgent HR intervention recommended."
            else:
                return f"{name} maintains a {attendance_rate:.1f}% attendance rate with {absent_days} absences, showing good commitment."
        
        elif any(word in q_lower for word in ["hour", "work", "productivity", "effort"]):
            return f"{name} averages {avg_hours:.1f} working hours daily. This indicates {'strong engagement' if avg_hours >= 8 else 'potential capacity concerns'} and should be monitored."
        
        elif any(word in q_lower for word in ["trend", "improve", "progress", "concern"]):
            return f"{name}'s attendance trend is {trend.upper()} with {prediction}. Recent patterns {'show improvement' if trend == 'improving' else 'require attention' if trend == 'declining' else 'remain stable'}."
        
        elif any(word in q_lower for word in ["recommend", "action", "advice", "suggest"]):
            if prediction == "Regular Attendee":
                return f"Recommend recognizing {name}'s excellent attendance. Consider opportunities for leadership or mentoring roles to maintain engagement."
            elif prediction == "Irregular Attendance Pattern":
                return f"Recommend scheduling a supportive conversation with {name} to understand barriers. Explore flexible arrangements or workload adjustments."
            else:
                return f"Recommend urgent HR intervention with {name}. Conduct wellness check-in to address attendance challenges and provide support."
        
        else:
            return f"{name} is classified as '{prediction}' with {attendance_rate:.1f}% attendance rate and averages {avg_hours:.1f} working hours daily. Their attendance {trend} recently."


def generate_attendance_insights(employee_name: str, features: dict, prediction: str) -> str:
    """
    Generates rich, contextual GenAI insights for an employee based on their attendance features
    and ML prediction. Calls the real Google Gemini API if GEMINI_API_KEY is configured,
    and falls back to a highly realistic rules-based output if the key is not configured.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Detailed data context for prompt
    data_context = (
        f"Employee Name: {employee_name}\n"
        f"ML Punctuality Prediction: {prediction}\n"
        f"Attendance Rate: {features['Attendance_Rate'] * 100:.2f}%\n"
        f"Total Absences: {features['Absences']}\n"
        f"Total Late Arrivals: {features['Late_Arrivals']}\n"
        f"Average Daily Working Hours: {features['Avg_Working_Hours']} hours\n"
        f"Leave Frequency: {features['Leave_Frequency']} times\n"
        f"Monday/Friday Late Trend: {features['Mon_Fri_Late_Trend']}/10 (higher indicates high lateness concentration on Mon/Fri)\n"
    )
    
    prompt = (
        f"You are a Senior HR Analytics AI Assistant.\n"
        f"Analyze the following attendance profile and generate a concise, professional 3-sentence action plan/insight. "
        f"Do not include greeting or introductory statements. Start directly with the analysis of the employee's behaviors.\n\n"
        f"Employee Record:\n{data_context}\n"
        f"Instructions:\n"
        f"- Sentence 1: Analyze overall presence rate and punctuality trends (e.g. note specific Monday/Friday patterns if any).\n"
        f"- Sentence 2: Analyze working hours consistency and productivity implications.\n"
        f"- Sentence 3: Provide a professional HR recommendation (e.g. support, mentoring, or checking for burnout)."
    )
    
    # 1. Call real Google Gemini API if key is present
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 200
                }
            }
            
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers=headers, 
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=8) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
                # Extract text response from Gemini structure
                if "candidates" in res_data and res_data["candidates"]:
                    candidate = res_data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        ai_text = candidate["content"]["parts"][0]["text"].strip()
                        return ai_text
                        
        except Exception as e:
            print(f"WARNING: Gemini API call failed: {e}. Falling back to simulated GenAI generator.")
            
    # 2. Simulated/Fallback AI Generator (Highly realistic and contextual)
    return get_simulated_insight(employee_name, features, prediction)

def get_simulated_insight(name: str, features: dict, prediction: str) -> str:
    """
    Simulated Generative AI text generator. Analyzes features dynamically
    and builds customized professional insights.
    """
    rate = features["Attendance_Rate"] * 100
    absences = features["Absences"]
    lates = features["Late_Arrivals"]
    hours = features["Avg_Working_Hours"]
    mon_fri_trend = features["Mon_Fri_Late_Trend"]
    
    if prediction == "Regular Attendee":
        sentence_1 = f"The employee, {name}, demonstrates excellent commitment with a stellar attendance rate of {rate:.1f}% and negligible absenteeism."
        sentence_2 = f"Average daily working hours ({hours:.1f} hrs) are highly stable, reflecting strong productivity and alignment with core corporate hours."
        sentence_3 = f"Recommendation: Recognize their consistent performance and consider them for leadership or mentoring roles in their department."
    
    elif prediction == "Irregular Attendance Pattern":
        trend_explanation = "specifically clustered around Mondays and Fridays" if mon_fri_trend >= 5.0 else "scattered throughout the week"
        sentence_1 = f"Analysis of {name}'s attendance shows a moderate presence rate ({rate:.1f}%), but reveals a notable late arrival count ({lates} instances), {trend_explanation}."
        sentence_2 = f"Their average working hours fluctuate at {hours:.1f} hours, indicating potential task slippage or time management bottlenecks."
        sentence_3 = f"Recommendation: Initiate a friendly coaching session to address punctuality trends, review remote-work options, or examine commute constraints."
        
    else:  # At-Risk Employee
        sentence_1 = f"We observe highly concerning attendance patterns for {name}, characterized by a critical attendance rate of {rate:.1f}% and {absences} unexplained absences."
        sentence_2 = f"Average daily working hours have dropped to {hours:.1f} hours, signaling significant disengagement and potential capacity strain."
        sentence_3 = f"Recommendation: HR should schedule a private wellness check-in immediately to support the employee, discuss workload fatigue, and explore leaves of absence if needed."
        
    return f"{sentence_1} {sentence_2} {sentence_3}"
