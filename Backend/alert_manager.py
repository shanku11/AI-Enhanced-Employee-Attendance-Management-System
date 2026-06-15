import datetime
import asyncio
from sqlalchemy.orm import Session
from database import User, Attendance, AttendanceLog, PredictionCache, Alert, AlertThreshold
from websocket_manager import manager
from ml_handler import calculate_absenteeism_risk, detect_attendance_anomalies

def get_or_create_thresholds(db: Session) -> AlertThreshold:
    """
    Fetches the active organization alert thresholds, seeding defaults if none exist.
    """
    thresholds = db.query(AlertThreshold).first()
    if not thresholds:
        thresholds = AlertThreshold(
            late_minutes_threshold=10,
            risk_score_threshold=70.0,
            anomaly_score_threshold=50.0,
            escalation_occurrences=3
        )
        db.add(thresholds)
        db.commit()
        db.refresh(thresholds)
    return thresholds

def check_and_trigger_alerts(employee_id: int, db: Session):
    """
    Runs smart alerting checks for an employee:
    - Late arrivals (via Attendance status or AttendanceLog timestamp)
    - Unplanned absences
    - High absenteeism risk predictions
    - Statistical anomalies
    
    Applies escalation rules and broadcasts alerts via WebSocket in real-time.
    """
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee or employee.role != "employee":
        return
        
    thresholds = get_or_create_thresholds(db)
    today = datetime.date.today()
    triggered_late = False
    
    # 1a. Check Late arrivals from AttendanceLog (fine-grained clock-in time)
    log_record = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == employee_id,
        AttendanceLog.date == today
    ).order_by(AttendanceLog.timestamp.desc()).first()
    
    if log_record and log_record.clock_in_time:
        in_hour = log_record.clock_in_time.hour
        in_minute = log_record.clock_in_time.minute
        # Formula: minutes past 09:00 AM standard start
        minutes_late = (in_hour - 9) * 60 + in_minute
        if minutes_late > thresholds.late_minutes_threshold:
            _trigger_or_escalate_alert(
                employee_id=employee_id,
                alert_type="late_arrival",
                message=f"{employee.name} was late by {int(minutes_late)} minutes on {today.strftime('%Y-%m-%d')} (Clock-in: {in_hour:02d}:{in_minute:02d}).",
                severity="medium",
                thresholds=thresholds,
                db=db
            )
            triggered_late = True

    # 1b. Check status from aggregate Attendance table (seeded or marked records)
    attendance_record = db.query(Attendance).filter(
        Attendance.user_id == employee_id,
        Attendance.date == today
    ).first()
    
    if attendance_record:
        if attendance_record.status == "Late" and not triggered_late:
            in_time = attendance_record.clock_in
            standard_start = datetime.datetime.combine(attendance_record.date, datetime.time(9, 0))
            if in_time and in_time > standard_start:
                minutes_late = (in_time - standard_start).total_seconds() / 60
                if minutes_late > thresholds.late_minutes_threshold:
                    _trigger_or_escalate_alert(
                        employee_id=employee_id,
                        alert_type="late_arrival",
                        message=f"{employee.name} was late by {int(minutes_late)} minutes on {today.strftime('%Y-%m-%d')}.",
                        severity="medium",
                        thresholds=thresholds,
                        db=db
                    )
        elif attendance_record.status == "Absent":
            _trigger_or_escalate_alert(
                employee_id=employee_id,
                alert_type="unplanned_absence",
                message=f"{employee.name} had an unplanned absence on {today.strftime('%Y-%m-%d')}.",
                severity="high",
                thresholds=thresholds,
                db=db
            )
            
    # 2. Check Absenteeism Risk
    try:
        risk_data = calculate_absenteeism_risk(employee_id, db)
        risk_score = risk_data["risk_score"]
        if risk_score > thresholds.risk_score_threshold:
            severity = "critical" if risk_score >= 85 else "high"
            _trigger_or_escalate_alert(
                employee_id=employee_id,
                alert_type="at_risk_prediction",
                message=f"{employee.name} is at critical absenteeism risk (Risk Score: {risk_score:.1f}).",
                severity=severity,
                thresholds=thresholds,
                db=db
            )
    except Exception as e:
        print(f"Error checking risk alert: {e}")
        
    # 3. Check Anomalies
    try:
        anomaly_data = detect_attendance_anomalies(employee_id, db)
        anomaly_score = anomaly_data["anomaly_score"]
        if anomaly_score > thresholds.anomaly_score_threshold:
            for anomaly in anomaly_data.get("anomalies", []):
                _trigger_or_escalate_alert(
                    employee_id=employee_id,
                    alert_type="anomaly",
                    message=f"{employee.name}: Anomaly detected - {anomaly['message']}",
                    severity="high" if anomaly.get("severity") == "high" else "medium",
                    thresholds=thresholds,
                    db=db
                )
    except Exception as e:
        print(f"Error checking anomaly alert: {e}")

def _trigger_or_escalate_alert(employee_id: int, alert_type: str, message: str, severity: str, thresholds: AlertThreshold, db: Session):
    """
    Helper to trigger a new alert or escalate an existing unacknowledged alert.
    """
    # Check if there is an active, unacknowledged alert of the same type for this employee
    existing_alert = db.query(Alert).filter(
        Alert.user_id == employee_id,
        Alert.type == alert_type,
        Alert.is_acknowledged == False
    ).first()
    
    if existing_alert:
        # Increment occurrences
        existing_alert.occurrences += 1
        
        # Apply escalation rules
        if existing_alert.occurrences >= thresholds.escalation_occurrences:
            existing_alert.severity = "critical"
            if not existing_alert.message.startswith("[ESCALATED]"):
                existing_alert.message = f"[ESCALATED] {existing_alert.message}"
        
        existing_alert.created_at = datetime.datetime.utcnow()
        alert_record = existing_alert
    else:
        # Create new alert
        alert_record = Alert(
            user_id=employee_id,
            type=alert_type,
            message=message,
            severity=severity,
            occurrences=1,
            is_acknowledged=False
        )
        db.add(alert_record)
        
    try:
        db.commit()
        db.refresh(alert_record)
        
        # Broadcast alert via WebSocket
        _broadcast_alert(employee_id, alert_record)
    except Exception as e:
        print(f"Error saving alert record: {e}")
        db.rollback()

def _broadcast_alert(employee_id: int, alert: Alert):
    """
    Asynchronously broadcasts an alert payload using the WebSocket ConnectionManager.
    """
    try:
        loop = asyncio.get_event_loop()
        alert_payload = {
            "id": alert.id,
            "user_id": employee_id,
            "type": alert.type,
            "message": alert.message,
            "severity": alert.severity,
            "occurrences": alert.occurrences,
            "is_acknowledged": alert.is_acknowledged,
            "created_at": alert.created_at.isoformat() if alert.created_at else None
        }
        
        if loop.is_running():
            loop.create_task(manager.send_alert(employee_id, alert_payload))
        else:
            # Fallback if no loop is running (e.g. CLI/tests)
            asyncio.run(manager.send_alert(employee_id, alert_payload))
    except Exception as err:
        print(f"WS Alert broadcast failed: {err}")
