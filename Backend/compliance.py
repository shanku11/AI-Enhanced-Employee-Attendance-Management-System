import json
import datetime
from sqlalchemy.orm import Session
from database import User, Attendance, AttendanceLog, PredictionCache, ChatMessage, EmployeeInsight, SavedFilter, Alert, AuditLog

def log_audit_action(actor_id: int, action: str, resource: str, old_value: str = None, new_value: str = None, db: Session = None):
    """
    Logs an access or modification action in the audit_logs table for GDPR compliance.
    """
    if not db:
        return
    try:
        log_entry = AuditLog(
            actor_id=actor_id,
            action=action,
            resource=resource,
            old_value=old_value,
            new_value=new_value,
            timestamp=datetime.datetime.utcnow()
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"ERROR logging audit action: {e}")
        db.rollback()

def export_employee_data(employee_id: int, db: Session) -> dict:
    """
    Exports all employee data in a portable JSON format.
    """
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        return {}
        
    attendances = db.query(Attendance).filter(Attendance.user_id == employee_id).all()
    logs = db.query(AttendanceLog).filter(AttendanceLog.user_id == employee_id).all()
    predictions = db.query(PredictionCache).filter(PredictionCache.user_id == employee_id).all()
    chats = db.query(ChatMessage).filter(ChatMessage.user_id == employee_id).all()
    insights = db.query(EmployeeInsight).filter(EmployeeInsight.user_id == employee_id).all()
    alerts = db.query(Alert).filter(Alert.user_id == employee_id).all()
    
    data = {
        "user_profile": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "name": user.name,
            "department": user.department,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None
        },
        "attendance_records": [
            {
                "id": a.id,
                "date": str(a.date),
                "clock_in": a.clock_in.isoformat() if a.clock_in else None,
                "clock_out": a.clock_out.isoformat() if a.clock_out else None,
                "status": a.status,
                "working_hours": a.working_hours
            } for a in attendances
        ],
        "attendance_logs": [
            {
                "id": l.id,
                "date": str(l.date),
                "clock_in_time": l.clock_in_time.isoformat() if l.clock_in_time else None,
                "clock_out_time": l.clock_out_time.isoformat() if l.clock_out_time else None,
                "current_status": l.current_status,
                "working_hours_so_far": l.working_hours_so_far,
                "break_minutes": l.break_minutes,
                "notes": l.notes,
                "timestamp": l.timestamp.isoformat() if l.timestamp else None
            } for l in logs
        ],
        "prediction_cache": [
            {
                "id": p.id,
                "prediction_type": p.prediction_type,
                "prediction_value": p.prediction_value,
                "confidence_score": p.confidence_score,
                "features": p.features,
                "model_version": p.model_version,
                "created_at": p.created_at.isoformat() if p.created_at else None
            } for p in predictions
        ],
        "chat_history": [
            {
                "id": c.id,
                "sender": c.sender,
                "message_text": c.message_text,
                "context_employee_id": c.context_employee_id,
                "created_at": c.created_at.isoformat() if c.created_at else None
            } for c in chats
        ],
        "employee_insights": [
            {
                "id": i.id,
                "insight_type": i.insight_type,
                "insight_title": i.insight_title,
                "insight_content": i.insight_content,
                "severity": i.severity,
                "is_read": i.is_read,
                "created_at": i.created_at.isoformat() if i.created_at else None
            } for i in insights
        ],
        "alerts": [
            {
                "id": al.id,
                "type": al.type,
                "message": al.message,
                "severity": al.severity,
                "occurrences": al.occurrences,
                "is_acknowledged": al.is_acknowledged,
                "created_at": al.created_at.isoformat() if al.created_at else None
            } for al in alerts
        ]
    }
    
    return data

def delete_employee_data(employee_id: int, db: Session) -> bool:
    """
    Deletes all records for an employee to satisfy GDPR Right to be Forgotten.
    """
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        return False
        
    try:
        # Cascade relationships are configured, but explicitly deleting them ensures SQLite handles it properly
        db.query(Attendance).filter(Attendance.user_id == employee_id).delete()
        db.query(AttendanceLog).filter(AttendanceLog.user_id == employee_id).delete()
        db.query(PredictionCache).filter(PredictionCache.user_id == employee_id).delete()
        db.query(ChatMessage).filter(ChatMessage.user_id == employee_id).delete()
        db.query(EmployeeInsight).filter(EmployeeInsight.user_id == employee_id).delete()
        db.query(SavedFilter).filter(SavedFilter.user_id == employee_id).delete()
        db.query(Alert).filter(Alert.user_id == employee_id).delete()
        
        # Delete user record
        db.delete(user)
        db.commit()
        return True
    except Exception as e:
        print(f"ERROR deleting employee data: {e}")
        db.rollback()
        return False

def clean_expired_audit_logs(db: Session, retention_years: int = 7) -> int:
    """
    Deletes audit logs older than retention_years (default 7 years).
    """
    cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=retention_years * 365)
    try:
        deleted_count = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()
        db.commit()
        return deleted_count
    except Exception as e:
        print(f"ERROR cleaning expired audit logs: {e}")
        db.rollback()
        return 0
