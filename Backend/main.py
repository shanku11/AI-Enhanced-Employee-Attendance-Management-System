from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
import hashlib
import datetime
import os
import random
import csv
import io
from typing import List, Optional, Dict
from pydantic import BaseModel
import json

from database import init_db, SessionLocal, User, Attendance, AttendanceLog, ChatMessage, EmployeeInsight, PredictionCache, SavedFilter, Alert, AlertThreshold, AuditLog, SystemSetting
from ml_handler import predict_attendance_behavior, predict_attendance_from_features, detect_attendance_anomalies, calculate_absenteeism_risk
from ai_handler import generate_attendance_insights, ChatManager
from websocket_manager import manager
from trend_analyzer import TrendAnalyzer
from alert_manager import check_and_trigger_alerts, get_or_create_thresholds
from compliance import log_audit_action, export_employee_data, delete_employee_data


# Initialize database
init_db()

app = FastAPI(
    title="AI-Enhanced Employee Attendance Management System API",
    description="Real-time attendance tracking with ML-powered insights and AI chat",
    version="2.0"
)

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ================ PYDANTIC SCHEMAS ================

# Authentication Schemas
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    name: str
    role: str = "employee"
    department: str = "General"

class LoginRequest(BaseModel):
    username: str
    password: str

# Attendance Schemas
class MarkAttendanceRequest(BaseModel):
    user_id: int
    date: str
    clock_in: str
    clock_out: Optional[str] = None
    status: str

class ClockInRequest(BaseModel):
    user_id: int

class ClockOutRequest(BaseModel):
    user_id: int

# ML & Analytics Schemas
class PredictionResponse(BaseModel):
    user_id: int
    prediction: str
    confidence: float
    features: Dict
    description: str
    model_version: str

class AnomalyResponse(BaseModel):
    anomalies: List[Dict]
    anomaly_score: float

class RiskResponse(BaseModel):
    user_id: int
    risk_score: float
    risk_level: str
    risk_factors: Dict

# Chat & AI Schemas
class ChatRequest(BaseModel):
    user_id: int
    question: str
    history: List[dict] = []

class ChatResponse(BaseModel):
    response: str
    timestamp: str

# WebSocket Message Schema
class WebSocketMessage(BaseModel):
    type: str
    data: Dict
    timestamp: str

class EmailJSSettingsRequest(BaseModel):
    enabled: bool = False
    service_id: str = ""
    template_id: str = ""
    public_key: str = ""
    from_name: str = "HR Attendance Team"
    reply_to: str = "hr@company.com"

class WarningPreviewRequest(BaseModel):
    employee_id: int
    warning_type: str = "attendance"
    message: Optional[str] = None

# Helper function to hash password
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _build_attendance_record(user_id: int, current_date: datetime.date, profile_type: str) -> Attendance:
    if profile_type == "regular":
        absent_prob, late_prob = 0.04, 0.08
        min_hour, max_hour = 8.1, 9.1
    elif profile_type == "at_risk":
        absent_prob, late_prob = 0.32, 0.28
        min_hour, max_hour = 5.5, 7.5
    else:
        absent_prob = 0.12
        late_prob = 0.78 if current_date.weekday() in [0, 4] else 0.35
        min_hour, max_hour = 6.8, 8.4

    if random.random() < absent_prob:
        clock = datetime.datetime.combine(current_date, datetime.time(9, 0))
        return Attendance(
            user_id=user_id,
            date=current_date,
            clock_in=clock,
            clock_out=clock,
            status="Absent",
            working_hours=0.0
        )

    is_late = random.random() < late_prob
    if is_late:
        in_time = datetime.time(9, random.randint(5, 55))
    else:
        in_time = datetime.time(8, random.randint(25, 59))

    c_in = datetime.datetime.combine(current_date, in_time)
    hours = random.uniform(min_hour, max_hour)
    c_out = c_in + datetime.timedelta(hours=hours)
    return Attendance(
        user_id=user_id,
        date=current_date,
        clock_in=c_in,
        clock_out=c_out,
        status="Late" if is_late else "Present",
        working_hours=round(hours, 2)
    )

def _seed_attendance_history(db: Session, user: User, profile_type: str, days: int = 45):
    if db.query(Attendance).filter(Attendance.user_id == user.id).count() > 0:
        return

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days)
    for offset in range(days + 1):
        current_date = start_date + datetime.timedelta(days=offset)
        if current_date.weekday() in [5, 6]:
            continue
        db.add(_build_attendance_record(user.id, current_date, profile_type))

def ensure_demo_workforce(db: Session, min_employees: int = 24):
    existing_count = db.query(User).filter(User.role == "employee").count()
    if existing_count >= min_employees:
        return

    demo_people = [
        ("Aarav Mehta", "aarav", "Engineering", "regular"),
        ("Priya Nair", "priya", "Engineering", "regular"),
        ("Rohan Kapoor", "rohan", "Engineering", "irregular"),
        ("Sneha Rao", "sneha", "Engineering", "regular"),
        ("Vikram Sethi", "vikram", "Marketing", "at_risk"),
        ("Ananya Iyer", "ananya", "Marketing", "regular"),
        ("Karan Malhotra", "karan", "Marketing", "irregular"),
        ("Meera Shah", "meera", "Sales", "regular"),
        ("Nikhil Verma", "nikhil", "Sales", "at_risk"),
        ("Isha Jain", "isha", "Sales", "regular"),
        ("Dev Patel", "dev", "Operations", "irregular"),
        ("Tara Singh", "tara", "Operations", "regular"),
        ("Kabir Das", "kabir", "Operations", "at_risk"),
        ("Neha Kulkarni", "neha", "Human Resources", "regular"),
        ("Siddharth Roy", "siddharth", "Finance", "regular"),
        ("Pooja Menon", "pooja", "Finance", "at_risk"),
        ("Arjun Reddy", "arjun", "Finance", "irregular"),
        ("Kavya Pillai", "kavya", "Customer Success", "regular"),
        ("Manav Bhatia", "manav", "Customer Success", "regular"),
        ("Ritika Sen", "ritika", "Customer Success", "at_risk"),
        ("Om Prakash", "om", "Data Science", "regular"),
        ("Diya Banerjee", "diya", "Data Science", "irregular"),
        ("Harsh Vardhan", "harsh", "Data Science", "regular"),
        ("Leena Thomas", "leena", "Design", "regular"),
        ("Aditya Bose", "aditya", "Design", "at_risk")
    ]

    for name, username, department, profile_type in demo_people:
        if db.query(User).filter(User.username == username).first():
            user = db.query(User).filter(User.username == username).first()
            _seed_attendance_history(db, user, profile_type)
            continue

        user = User(
            username=username,
            email=f"{username}@company.com",
            password_hash=hash_password("password123"),
            role="employee",
            name=name,
            department=department
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        _seed_attendance_history(db, user, profile_type)
        db.commit()

# ----------------- DB SEEDING ON STARTUP -----------------
def seed_data_if_empty(db: Session):
    if db.query(User).count() > 0:
        return
        
    print("INFO: Database is empty! Seeding realistic demo data...")
    
    # 1. Create Admins and Employees
    admin = User(
        username="admin",
        email="hr@company.com",
        password_hash=hash_password("password123"),
        role="admin",
        name="HR Administrator",
        department="Human Resources"
    )
    
    alice = User(
        username="alice",
        email="alice@company.com",
        password_hash=hash_password("password123"),
        role="employee",
        name="Alice Johnson",
        department="Engineering"
    )  # Target: Regular Attendee
    
    bob = User(
        username="bob",
        email="bob@company.com",
        password_hash=hash_password("password123"),
        role="employee",
        name="Bob Smith",
        department="Marketing"
    )  # Target: At-Risk
    
    charlie = User(
        username="charlie",
        email="charlie@company.com",
        password_hash=hash_password("password123"),
        role="employee",
        name="Charlie Davis",
        department="Sales"
    )  # Target: Irregular
    
    db.add_all([admin, alice, bob, charlie])
    db.commit()
    db.refresh(alice)
    db.refresh(bob)
    db.refresh(charlie)
    
    # 2. Populate 30 Days of History
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=30)
    
    users_to_seed = [
        {"user": alice, "type": "regular"},
        {"user": bob, "type": "at_risk"},
        {"user": charlie, "type": "irregular"}
    ]
    
    for i in range(31):
        current_date = start_date + datetime.timedelta(days=i)
        
        # Skip weekends for realistic work attendance
        if current_date.weekday() in [5, 6]:
            continue
            
        for item in users_to_seed:
            user = item["user"]
            u_type = item["type"]
            
            # Setup clock in/out structures based on category types
            if u_type == "regular":
                # 95% present, 5% absent, very punctual (usually between 8:30 and 9:00)
                is_absent = random.random() < 0.05
                if is_absent:
                    att = Attendance(
                        user_id=user.id,
                        date=current_date,
                        clock_in=datetime.datetime.combine(current_date, datetime.time(9, 0)),
                        clock_out=datetime.datetime.combine(current_date, datetime.time(9, 0)),
                        status="Absent",
                        working_hours=0.0
                    )
                else:
                    is_late = random.random() < 0.05
                    in_hour = 9 if is_late else 8
                    in_minute = random.randint(1, 15) if is_late else random.randint(30, 59)
                    
                    c_in = datetime.datetime.combine(current_date, datetime.time(in_hour, in_minute))
                    c_out = datetime.datetime.combine(current_date, datetime.time(17, random.randint(30, 59)))
                    
                    working_hours = (c_out - c_in).total_seconds() / 3600.0
                    att = Attendance(
                        user_id=user.id,
                        date=current_date,
                        clock_in=c_in,
                        clock_out=c_out,
                        status="Late" if is_late else "Present",
                        working_hours=round(working_hours, 2)
                    )
                    
            elif u_type == "at_risk":
                # 65% present, 35% absent, lower working hours
                is_absent = random.random() < 0.35
                if is_absent:
                    att = Attendance(
                        user_id=user.id,
                        date=current_date,
                        clock_in=datetime.datetime.combine(current_date, datetime.time(9, 0)),
                        clock_out=datetime.datetime.combine(current_date, datetime.time(9, 0)),
                        status="Absent",
                        working_hours=0.0
                    )
                else:
                    is_late = random.random() < 0.20
                    in_hour = 9 if is_late else 8
                    in_minute = random.randint(1, 45) if is_late else random.randint(45, 59)
                    
                    c_in = datetime.datetime.combine(current_date, datetime.time(in_hour, in_minute))
                    # Leaves early often
                    c_out = datetime.datetime.combine(current_date, datetime.time(15 if random.random() < 0.3 else 17, random.randint(0, 30)))
                    
                    working_hours = (c_out - c_in).total_seconds() / 3600.0
                    att = Attendance(
                        user_id=user.id,
                        date=current_date,
                        clock_in=c_in,
                        clock_out=c_out,
                        status="Late" if is_late else "Present",
                        working_hours=round(working_hours, 2)
                    )
                    
            else:  # irregular
                # 90% present, 10% absent, highly late, especially on Mondays (0) and Fridays (4)
                is_absent = random.random() < 0.10
                if is_absent:
                    att = Attendance(
                        user_id=user.id,
                        date=current_date,
                        clock_in=datetime.datetime.combine(current_date, datetime.time(9, 0)),
                        clock_out=datetime.datetime.combine(current_date, datetime.time(9, 0)),
                        status="Absent",
                        working_hours=0.0
                    )
                else:
                    # High late probability on Mon/Fri (80%), moderate on other days (30%)
                    is_mon_or_fri = current_date.weekday() in [0, 4]
                    late_prob = 0.85 if is_mon_or_fri else 0.30
                    is_late = random.random() < late_prob
                    
                    in_hour = 9 if is_late else 8
                    in_minute = random.randint(5, 55) if is_late else random.randint(40, 59)
                    
                    c_in = datetime.datetime.combine(current_date, datetime.time(in_hour, in_minute))
                    c_out = datetime.datetime.combine(current_date, datetime.time(17, random.randint(0, 45)))
                    
                    working_hours = (c_out - c_in).total_seconds() / 3600.0
                    att = Attendance(
                        user_id=user.id,
                        date=current_date,
                        clock_in=c_in,
                        clock_out=c_out,
                        status="Late" if is_late else "Present",
                        working_hours=round(working_hours, 2)
                    )
            
            db.add(att)
    db.commit()
    print("INFO: Seeding completed! Database is fully populated with mock records.")

# Run seeding on startup as an event
@app.on_event("startup")
def startup_seed():
    db = SessionLocal()
    try:
        seed_data_if_empty(db)
        ensure_demo_workforce(db, min_employees=24)
    finally:
        db.close()

# ----------------- AUTHENTICATION ROUTES -----------------
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    # Check if username or email already exists
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    new_user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        role=req.role,
        name=req.name,
        department=req.department
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
        "name": new_user.name,
        "department": new_user.department,
        "message": "User registered successfully"
    }

@app.post("/api/auth/login")
def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    hashed_pwd = hash_password(req.password)
    if user.password_hash != hashed_pwd:
        raise HTTPException(status_code=401, detail="Invalid password credentials")
        
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "department": user.department,
        "message": "Login successful"
    }

# ----------------- ATTENDANCE MANAGEMENT ROUTES -----------------
@app.post("/api/attendance/mark")
def mark_attendance(req: MarkAttendanceRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # Parse date and times
    try:
        att_date = datetime.datetime.strptime(req.date, "%Y-%m-%d").date()
        
        # Clock in time
        ci_hour, ci_minute = map(int, req.clock_in.split(":"))
        c_in = datetime.datetime.combine(att_date, datetime.time(ci_hour, ci_minute))
        
        # Clock out time (optional)
        c_out = None
        working_hours = 0.0
        if req.clock_out:
            co_hour, co_minute = map(int, req.clock_out.split(":"))
            c_out = datetime.datetime.combine(att_date, datetime.time(co_hour, co_minute))
            working_hours = (c_out - c_in).total_seconds() / 3600.0
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time format: {e}")
        
    # Check if attendance already logged for this date
    existing_record = db.query(Attendance).filter(
        Attendance.user_id == req.user_id,
        Attendance.date == att_date
    ).first()
    
    if existing_record:
        # Update existing record
        existing_record.clock_in = c_in
        if c_out:
            existing_record.clock_out = c_out
            existing_record.working_hours = round(working_hours, 2)
        existing_record.status = req.status
        db.commit()
        db.refresh(existing_record)
        record = existing_record
    else:
        # Create new record
        new_record = Attendance(
            user_id=req.user_id,
            date=att_date,
            clock_in=c_in,
            clock_out=c_out,
            status=req.status,
            working_hours=round(working_hours, 2) if c_out else 0.0
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        record = new_record
        
    # Log GDPR audit action
    log_audit_action(actor_id=req.user_id, action="modify_data", resource=f"Attendance Mark for user {req.user_id} on {att_date}", db=db)
    
    # Trigger smart alerting checks
    check_and_trigger_alerts(req.user_id, db)
        
    return {
        "id": record.id,
        "user_id": record.user_id,
        "date": str(record.date),
        "clock_in": record.clock_in.strftime("%H:%M"),
        "clock_out": record.clock_out.strftime("%H:%M") if record.clock_out else None,
        "status": record.status,
        "working_hours": record.working_hours,
        "message": "Attendance marked successfully"
    }

@app.get("/api/attendance/reports")
def get_attendance_reports(user_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Returns attendance reports. If user_id is provided, returns employee report,
    otherwise returns all records (HR Admin view).
    """
    if user_id:
        records = db.query(Attendance).filter(Attendance.user_id == user_id).order_by(Attendance.date.desc()).all()
    else:
        records = db.query(Attendance).order_by(Attendance.date.desc()).all()
        
    res = []
    for r in records:
        res.append({
            "id": r.id,
            "user_id": r.user_id,
            "employee_name": r.user.name,
            "department": r.user.department,
            "date": str(r.date),
            "clock_in": r.clock_in.strftime("%H:%M"),
            "clock_out": r.clock_out.strftime("%H:%M") if r.clock_out else None,
            "status": r.status,
            "working_hours": r.working_hours
        })
    return res

@app.get("/api/attendance/employees")
def get_all_employees(db: Session = Depends(get_db)):
    """
    Returns a list of all registered employees for the HR admin selector
    """
    employees = db.query(User).filter(User.role == "employee").all()
    return [{
        "id": e.id,
        "name": e.name,
        "username": e.username,
        "email": e.email,
        "department": e.department
    } for e in employees]

# ----------------- REPORTS MODULE -----------------
def _attendance_query_for_period(db: Session, start_date: datetime.date, end_date: datetime.date):
    return db.query(Attendance).filter(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date.desc(), Attendance.user_id.asc()).all()

def _summarize_attendance(records: List[Attendance]) -> Dict:
    total_records = len(records)
    present = sum(1 for r in records if r.status == "Present")
    late = sum(1 for r in records if r.status == "Late")
    absent = sum(1 for r in records if r.status == "Absent")
    attended = present + late
    avg_hours = (
        sum(r.working_hours or 0 for r in records if r.status != "Absent") / attended
        if attended else 0.0
    )
    return {
        "total_records": total_records,
        "present": present,
        "late": late,
        "absent": absent,
        "attendance_rate": round((attended / total_records) * 100, 2) if total_records else 0.0,
        "average_hours": round(avg_hours, 2)
    }

def _format_report_rows(records: List[Attendance]) -> List[Dict]:
    return [{
        "employee_id": r.user_id,
        "employee_name": r.user.name if r.user else "Unknown",
        "department": r.user.department if r.user else "Unknown",
        "date": str(r.date),
        "check_in": r.clock_in.strftime("%H:%M") if r.clock_in else "",
        "check_out": r.clock_out.strftime("%H:%M") if r.clock_out else "",
        "status": r.status,
        "working_hours": r.working_hours
    } for r in records]

@app.get("/api/reports/daily")
def get_daily_report(date: Optional[str] = None, db: Session = Depends(get_db)):
    report_date = (
        datetime.datetime.strptime(date, "%Y-%m-%d").date()
        if date else datetime.date.today()
    )
    records = _attendance_query_for_period(db, report_date, report_date)
    return {
        "report_type": "daily",
        "date": str(report_date),
        "summary": _summarize_attendance(records),
        "records": _format_report_rows(records)
    }

@app.get("/api/reports/monthly")
def get_monthly_report(year: int, month: int, db: Session = Depends(get_db)):
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    start_date = datetime.date(year, month, 1)
    if month == 12:
        end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    records = _attendance_query_for_period(db, start_date, end_date)
    return {
        "report_type": "monthly",
        "year": year,
        "month": month,
        "summary": _summarize_attendance(records),
        "records": _format_report_rows(records)
    }

@app.get("/api/reports/export")
def export_report(
    report_type: str = "monthly",
    format: str = "csv",
    date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db)
):
    if report_type == "daily":
        report = get_daily_report(date, db)
        filename_base = f"daily_attendance_{report['date']}"
    elif report_type == "monthly":
        if year is None or month is None:
            today = datetime.date.today()
            year = year or today.year
            month = month or today.month
        report = get_monthly_report(year, month, db)
        filename_base = f"monthly_attendance_{year}_{month:02d}"
    else:
        raise HTTPException(status_code=400, detail="report_type must be 'daily' or 'monthly'")

    rows = report["records"]
    headers = ["employee_id", "employee_name", "department", "date", "check_in", "check_out", "status", "working_hours"]
    export_format = format.lower()

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.csv"}
        )

    if export_format in ["xlsx", "excel"]:
        try:
            from openpyxl import Workbook
        except ImportError:
            raise HTTPException(status_code=500, detail="Install openpyxl to enable Excel export")

        wb = Workbook()
        ws = wb.active
        ws.title = "Attendance Report"
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
        excel_stream = io.BytesIO()
        wb.save(excel_stream)
        excel_stream.seek(0)
        return StreamingResponse(
            excel_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.xlsx"}
        )

    if export_format == "pdf":
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except ImportError:
            raise HTTPException(status_code=500, detail="Install reportlab to enable PDF export")

        pdf_stream = io.BytesIO()
        c = canvas.Canvas(pdf_stream, pagesize=letter)
        width, height = letter
        y = height - 40
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, f"{report_type.title()} Attendance Report")
        y -= 28
        c.setFont("Helvetica", 9)
        c.drawString(40, y, f"Summary: {json.dumps(report['summary'])}")
        y -= 24
        for row in rows:
            line = f"{row['date']} | {row['employee_name']} | {row['department']} | {row['status']} | {row['working_hours']} hrs"
            c.drawString(40, y, line[:110])
            y -= 14
            if y < 40:
                c.showPage()
                c.setFont("Helvetica", 9)
                y = height - 40
        c.save()
        pdf_stream.seek(0)
        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"}
        )

    raise HTTPException(status_code=400, detail="format must be csv, xlsx, excel, or pdf")

# ----------------- COMPANY CSV ML LABELING & SETTINGS -----------------
def _get_row_value(row: Dict, aliases: List[str], default=None):
    normalized = {str(k).strip().lower().replace(" ", "").replace("_", ""): v for k, v in row.items()}
    for alias in aliases:
        key = alias.strip().lower().replace(" ", "").replace("_", "")
        if key in normalized and str(normalized[key]).strip() != "":
            return normalized[key]
    return default

def _to_float(value, field_name: str, row_number: int) -> float:
    try:
        return float(str(value).strip().replace("%", ""))
    except Exception:
        raise ValueError(f"Row {row_number}: invalid numeric value for {field_name}")

@app.post("/api/company/upload-csv")
async def upload_company_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must include headers")

    results = []
    errors = []
    required_fields = ["Absences", "LateCount", "AvgHours", "LeaveFrequency", "AttendanceRate"]

    for idx, row in enumerate(reader, start=2):
        try:
            absences = _to_float(_get_row_value(row, ["Absences", "AbsentDays", "AbsenceCount"], 0), "Absences", idx)
            late_count = _to_float(_get_row_value(row, ["LateCount", "Late_Arrivals", "LateArrivals"], 0), "LateCount", idx)
            avg_hours = _to_float(_get_row_value(row, ["AvgHours", "AverageWorkingHours", "Avg_Working_Hours"], 8), "AvgHours", idx)
            leave_frequency = _to_float(_get_row_value(row, ["LeaveFrequency", "Leaves", "LeaveCount"], absences), "LeaveFrequency", idx)
            attendance_rate = _to_float(_get_row_value(row, ["AttendanceRate", "Attendance_Rate", "Attendance%"], 100), "AttendanceRate", idx)
            total_days = _to_float(_get_row_value(row, ["TotalDays", "WorkingDays"], 30), "TotalDays", idx)

            if total_days <= 0:
                total_days = 30
            absence_rate = min(1.0, absences / total_days)
            late_rate = min(1.0, late_count / total_days)
            mon_fri_late_trend = min(10.0, late_rate * 10)
            punctuality_score = max(0.0, 100.0 - (late_rate * 100.0))

            prediction = predict_attendance_from_features({
                "Attendance_Rate": attendance_rate,
                "Absences": absences,
                "Late_Arrivals": late_count,
                "Avg_Working_Hours": avg_hours,
                "Leave_Frequency": leave_frequency,
                "Mon_Fri_Late_Trend": mon_fri_late_trend,
                "Absence_Variance": absence_rate * (1 - absence_rate),
                "Recent_Trend": 0.0,
                "Punctuality_Score": punctuality_score
            })

            result = {
                "row": idx,
                "employee_id": _get_row_value(row, ["EmployeeID", "Employee_ID", "ID"], ""),
                "name": _get_row_value(row, ["Name", "EmployeeName", "Employee"], ""),
                "email": _get_row_value(row, ["Email", "EmployeeEmail"], ""),
                "department": _get_row_value(row, ["Department", "Dept"], ""),
                "absences": int(absences),
                "late_count": int(late_count),
                "avg_hours": round(avg_hours, 2),
                "leave_frequency": int(leave_frequency),
                "attendance_rate": round(attendance_rate, 2),
                "prediction": prediction["prediction"],
                "confidence": prediction["confidence"],
                "description": prediction["description"]
            }
            results.append(result)
        except Exception as e:
            errors.append(str(e))

    log_audit_action(
        actor_id=1,
        action="read_data",
        resource=f"Uploaded company CSV classification ({len(results)} rows)",
        db=db
    )

    return {
        "filename": file.filename,
        "required_fields": required_fields,
        "processed": len(results),
        "errors": errors,
        "results": results
    }

@app.get("/api/company/csv-template")
def get_company_csv_template():
    content = (
        "EmployeeID,Name,Email,Department,Absences,LateCount,AvgHours,LeaveFrequency,AttendanceRate\n"
        "201,Sample Regular,sample.regular@company.com,Engineering,1,1,8.5,1,96\n"
        "202,Sample At Risk,sample.risk@company.com,Sales,12,7,6.1,6,64\n"
        "203,Sample Irregular,sample.irregular@company.com,Operations,4,13,7.4,3,86\n"
    )
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=company_attendance_template.csv"}
    )

@app.get("/api/settings/emailjs")
def get_emailjs_settings(db: Session = Depends(get_db)):
    setting = db.query(SystemSetting).filter(SystemSetting.key == "emailjs").first()
    if not setting:
        return {
            "enabled": False,
            "service_id": "",
            "template_id": "",
            "public_key": "",
            "from_name": "HR Attendance Team",
            "reply_to": "hr@company.com"
        }
    return setting.value

@app.post("/api/settings/emailjs")
def update_emailjs_settings(req: EmailJSSettingsRequest, db: Session = Depends(get_db)):
    payload = req.dict()
    setting = db.query(SystemSetting).filter(SystemSetting.key == "emailjs").first()
    if setting:
        setting.value = payload
        setting.updated_at = datetime.datetime.utcnow()
    else:
        setting = SystemSetting(key="emailjs", value=payload)
        db.add(setting)
    db.commit()
    return {"status": "success", "settings": payload}

@app.post("/api/warnings/email-preview")
def get_warning_email_preview(req: WarningPreviewRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == req.employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    prediction = predict_attendance_behavior(user.id, db)
    features = prediction["features"]
    subject = f"Attendance Warning: {prediction['prediction']} status"
    message = req.message or (
        f"Dear {user.name}, your attendance profile is currently labeled as {prediction['prediction']} "
        f"with {features['Absences']} absences, {features['Late_Arrivals']} late arrivals, "
        f"and an attendance rate of {features['Attendance_Rate'] * 100:.1f}%. "
        "Please connect with HR to discuss support steps and improve attendance consistency."
    )

    return {
        "to_name": user.name,
        "to_email": user.email,
        "employee_id": user.id,
        "department": user.department,
        "subject": subject,
        "message": message,
        "prediction": prediction["prediction"],
        "confidence": prediction["confidence"]
    }

# ----------------- MACHINE LEARNING ANALYTICS ROUTES -----------------
@app.get("/api/analytics/predict/{user_id}")
def get_employee_prediction(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    prediction_results = predict_attendance_behavior(user_id, db)
    return {
        "employee_name": user.name,
        "department": user.department,
        **prediction_results
    }

# ----------------- GENERATIVE AI INSIGHTS ROUTES -----------------
@app.get("/api/analytics/insights/{user_id}")
def get_employee_insights(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # 1. Run Machine Learning behavior prediction to get model label
    prediction_results = predict_attendance_behavior(user_id, db)
    
    # 2. Run GenAI insights generator
    features = prediction_results["features"]
    prediction = prediction_results["prediction"]
    
    insights = generate_attendance_insights(user.name, features, prediction)
    
    return {
        "employee_name": user.name,
        "department": user.department,
        "ml_category": prediction,
        "ml_confidence": prediction_results["confidence"],
        "ai_insights": insights
    }

# ================ NEW PHASE 1: ENHANCED ML ANALYTICS ================

@app.get("/api/analytics/prediction/{user_id}")
def get_attendance_prediction(user_id: int, db: Session = Depends(get_db)):
    """Get comprehensive attendance prediction with confidence scores"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    prediction_results = predict_attendance_behavior(user_id, db)
    return {
        "employee_name": user.name,
        "department": user.department,
        **prediction_results
    }

@app.get("/api/analytics/anomalies/{user_id}")
def get_attendance_anomalies(user_id: int, db: Session = Depends(get_db)):
    """Detect unusual attendance patterns"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    anomalies = detect_attendance_anomalies(user_id, db)
    return {
        "employee_name": user.name,
        "department": user.department,
        **anomalies
    }

@app.get("/api/analytics/risk/{user_id}")
def get_absenteeism_risk(user_id: int, db: Session = Depends(get_db)):
    """Calculate absenteeism risk for predictive HR management"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    risk_data = calculate_absenteeism_risk(user_id, db)
    return {
        "employee_name": user.name,
        "department": user.department,
        **risk_data
    }

@app.get("/api/analytics/all-employees")
def get_all_employees_analytics(db: Session = Depends(get_db)):
    """Get analytics for all employees (admin dashboard)"""
    users = db.query(User).filter(User.role == "employee").all()
    
    analytics_list = []
    for user in users:
        try:
            prediction = predict_attendance_behavior(user.id, db)
            risk = calculate_absenteeism_risk(user.id, db)
            
            analytics_list.append({
                "user_id": user.id,
                "name": user.name,
                "department": user.department,
                "prediction": prediction["prediction"],
                "confidence": prediction["confidence"],
                "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"]
            })
        except Exception as e:
            print(f"[WARN] Error processing user {user.id}: {e}")
            continue
    
    return {
        "total_employees": len(analytics_list),
        "employees": analytics_list
    }

# ================ REAL-TIME WEBSOCKET ENDPOINTS ================

@app.websocket("/ws/attendance/{user_id}")
async def websocket_attendance(websocket: WebSocket, user_id: int, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for real-time attendance updates.
    Clients connect here to receive live attendance status updates.
    """
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle ping/keep-alive messages
            if message_data.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.datetime.utcnow().isoformat()})
            
            # Handle clock-in/out requests
            elif message_data.get("type") == "clock_in":
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    # Create attendance log entry
                    log_entry = AttendanceLog(
                        user_id=user_id,
                        date=datetime.date.today(),
                        clock_in_time=datetime.datetime.utcnow(),
                        current_status="clocked_in"
                    )
                    db.add(log_entry)
                    db.commit()
                    
                    # Broadcast update
                    await manager.send_attendance_update(user_id, {
                        "status": "clocked_in",
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "user_id": user_id,
                        "user_name": user.name
                    })
            
            elif message_data.get("type") == "clock_out":
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    # Update last clock_in log entry
                    last_log = db.query(AttendanceLog).filter(
                        AttendanceLog.user_id == user_id,
                        AttendanceLog.date == datetime.date.today()
                    ).order_by(AttendanceLog.timestamp.desc()).first()
                    
                    if last_log:
                        last_log.clock_out_time = datetime.datetime.utcnow()
                        last_log.current_status = "clocked_out"
                        db.commit()
                    
                    # Broadcast update
                    await manager.send_attendance_update(user_id, {
                        "status": "clocked_out",
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "user_id": user_id,
                        "user_name": user.name
                    })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WARN] WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket)

@app.websocket("/ws/analytics/{admin_id}")
async def websocket_analytics(websocket: WebSocket, admin_id: int):
    """
    WebSocket endpoint for real-time analytics updates.
    Admins connect here to receive live employee analytics updates.
    """
    await manager.connect(websocket, admin_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.datetime.utcnow().isoformat()})
            
            elif message_data.get("type") == "request_stats":
                stats = manager.get_connection_stats()
                await websocket.send_json({"type": "stats", "data": stats})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WARN] Analytics WebSocket error for admin {admin_id}: {e}")
        manager.disconnect(websocket)

@app.get("/api/ws/stats")
def get_websocket_stats():
    """Get WebSocket connection statistics"""
    return manager.get_connection_stats()

# ================ IMPROVED ATTENDANCE ENDPOINTS ================

@app.post("/api/attendance/clock-in")
def clock_in_employee(req: ClockInRequest, db: Session = Depends(get_db)):
    """Real-time clock-in endpoint"""
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    today = datetime.date.today()
    clock_in_time = datetime.datetime.utcnow()
    
    # Create attendance log
    log_entry = AttendanceLog(
        user_id=req.user_id,
        date=today,
        clock_in_time=clock_in_time,
        current_status="clocked_in"
    )
    db.add(log_entry)
    db.commit()
    
    # Log GDPR audit action
    log_audit_action(actor_id=req.user_id, action="modify_data", resource=f"Attendance Log Clock-in for user {req.user_id}", db=db)
    
    # Trigger smart alerting checks
    check_and_trigger_alerts(req.user_id, db)
    
    return {
        "status": "success",
        "message": f"{user.name} clocked in at {clock_in_time.isoformat()}",
        "user_id": req.user_id,
        "timestamp": clock_in_time.isoformat()
    }

@app.post("/api/attendance/clock-out")
def clock_out_employee(req: ClockOutRequest, db: Session = Depends(get_db)):
    """Real-time clock-out endpoint"""
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    today = datetime.date.today()
    clock_out_time = datetime.datetime.utcnow()
    
    # Find and update today's log
    last_log = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == req.user_id,
        AttendanceLog.date == today
    ).order_by(AttendanceLog.timestamp.desc()).first()
    
    if last_log:
        last_log.clock_out_time = clock_out_time
        last_log.current_status = "clocked_out"
        if last_log.clock_in_time:
            working_seconds = (clock_out_time - last_log.clock_in_time).total_seconds()
            last_log.working_hours_so_far = round(working_seconds / 3600, 2)
        db.commit()
        
    # Log GDPR audit action
    log_audit_action(actor_id=req.user_id, action="modify_data", resource=f"Attendance Log Clock-out for user {req.user_id}", db=db)
    
    # Trigger smart alerting checks
    check_and_trigger_alerts(req.user_id, db)
    
    return {
        "status": "success",
        "message": f"{user.name} clocked out at {clock_out_time.isoformat()}",
        "user_id": req.user_id,
        "timestamp": clock_out_time.isoformat(),
        "working_hours": last_log.working_hours_so_far if last_log else 0
    }

@app.get("/api/attendance/today/{user_id}")
def get_today_attendance(user_id: int, db: Session = Depends(get_db)):
    """Get today's attendance status in real-time"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    today = datetime.date.today()
    logs = db.query(AttendanceLog).filter(
        AttendanceLog.user_id == user_id,
        AttendanceLog.date == today
    ).order_by(AttendanceLog.timestamp).all()
    
    if not logs:
        return {
            "user_id": user_id,
            "date": today.isoformat(),
            "status": "not_clocked_in",
            "clock_in_time": None,
            "clock_out_time": None,
            "working_hours": 0
        }
    
    latest_log = logs[-1]
    return {
        "user_id": user_id,
        "date": today.isoformat(),
        "status": latest_log.current_status,
        "clock_in_time": latest_log.clock_in_time.isoformat() if latest_log.clock_in_time else None,
        "clock_out_time": latest_log.clock_out_time.isoformat() if latest_log.clock_out_time else None,
        "working_hours": latest_log.working_hours_so_far,
        "last_updated": latest_log.timestamp.isoformat()
    }

# ================ HEALTH & DEBUG ENDPOINTS ================

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "websocket_connections": manager.get_active_users_count()
    }

@app.get("/api/system/stats")
def system_stats(db: Session = Depends(get_db)):
    """System statistics"""
    total_users = db.query(User).count()
    total_employees = db.query(User).filter(User.role == "employee").count()
    total_admins = db.query(User).filter(User.role == "admin").count()
    total_attendance_records = db.query(Attendance).count()
    
    return {
        "total_users": total_users,
        "total_employees": total_employees,
        "total_admins": total_admins,
        "total_attendance_records": total_attendance_records,
        "websocket_connections": manager.get_active_users_count(),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ================ TREND ANALYSIS ENDPOINTS (NEW) ================

@app.get("/api/analytics/trends/{user_id}")
def get_employee_trends(user_id: int, db: Session = Depends(get_db)):
    """Get comprehensive trend analysis for an employee"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    records = db.query(Attendance).filter(Attendance.user_id == user_id).all()
    analyzer = TrendAnalyzer()
    trends = analyzer.analyze_employee_trends(records, user_id)
    
    return {
        "employee_name": user.name,
        "department": user.department,
        **trends
    }

@app.get("/api/analytics/seasonal/{user_id}")
def get_seasonal_patterns(user_id: int, db: Session = Depends(get_db)):
    """Detect seasonal attendance patterns (day of week, month)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    records = db.query(Attendance).filter(Attendance.user_id == user_id).all()
    analyzer = TrendAnalyzer()
    patterns = analyzer.detect_seasonal_patterns(records, user_id)
    
    return {
        "employee_name": user.name,
        "department": user.department,
        **patterns
    }

@app.get("/api/analytics/department-trends/{department}")
def get_department_trends(department: str, db: Session = Depends(get_db)):
    """Get trend analysis for entire department"""
    users = db.query(User).filter(
        User.department == department,
        User.role == "employee"
    ).all()
    
    records_by_employee = {}
    for user in users:
        records = db.query(Attendance).filter(Attendance.user_id == user.id).all()
        records_by_employee[user.id] = records
    
    analyzer = TrendAnalyzer()
    trends = analyzer.analyze_department_trends(records_by_employee)
    
    return {
        "department": department,
        **trends
    }

@app.get("/api/analytics/departments")
def get_all_departments_trends(db: Session = Depends(get_db)):
    """Get trend summary for all departments"""
    departments = db.query(User.department).distinct().filter(
        User.role == "employee"
    ).all()
    
    results = []
    for (dept,) in departments:
        if dept:
            users = db.query(User).filter(
                User.department == dept,
                User.role == "employee"
            ).all()
            
            records_by_employee = {}
            for user in users:
                records = db.query(Attendance).filter(Attendance.user_id == user.id).all()
                records_by_employee[user.id] = records
            
            analyzer = TrendAnalyzer()
            trends = analyzer.analyze_department_trends(records_by_employee)
            results.append({
                "department": dept,
                **trends
            })
    
    return {"departments": results, "timestamp": datetime.datetime.utcnow().isoformat()}

# ================ ENHANCED ANALYTICS DASHBOARD ================

@app.get("/api/dashboard/admin-summary")
def get_admin_dashboard_summary(db: Session = Depends(get_db)):
    """
    Comprehensive admin dashboard summary with:
    - Employee statistics
    - Risk assessments
    - Trend indicators
    - Alerts and recommendations
    """
    employees = db.query(User).filter(User.role == "employee").all()
    
    analytics = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "total_employees": len(employees),
        "risk_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "prediction_breakdown": {"regular": 0, "at_risk": 0, "irregular": 0},
        "employees_data": []
    }
    
    for emp in employees:
        try:
            # Get prediction
            prediction = predict_attendance_behavior(emp.id, db)
            # Get risk
            risk = calculate_absenteeism_risk(emp.id, db)
            # Get anomalies
            anomalies = detect_attendance_anomalies(emp.id, db)
            
            # Update breakdown
            analytics["prediction_breakdown"][prediction["prediction"].lower().replace(" ", "_")] += 1
            analytics["risk_breakdown"][risk["risk_level"].lower()] += 1
            
            # Add employee data
            emp_data = {
                "id": emp.id,
                "name": emp.name,
                "department": emp.department,
                "prediction": prediction["prediction"],
                "confidence": prediction["confidence"],
                "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"],
                "anomaly_score": anomalies["anomaly_score"],
                "has_anomalies": len(anomalies.get("anomalies", [])) > 0
            }
            analytics["employees_data"].append(emp_data)
        except Exception as e:
            print(f"Error processing employee {emp.id}: {e}")
            continue
    
    # Sort by risk score
    analytics["employees_data"].sort(
        key=lambda x: x["risk_score"],
        reverse=True
    )
    
    # Top 10 at-risk
    analytics["top_at_risk"] = analytics["employees_data"][:10]
    
    return analytics


@app.post("/api/analytics/chat")
def chat_with_hr_bot(req: ChatRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # 1. Run Machine Learning behavior prediction to get model label
    prediction_results = predict_attendance_behavior(req.user_id, db)
    features = prediction_results["features"]
    prediction = prediction_results["prediction"]
    
    # 2. Call real Google Gemini API if key is present
    api_key = os.getenv("GEMINI_API_KEY")
    
    data_context = (
        f"Selected Employee Name: {user.name}\n"
        f"ML Attendance Behavior Classification: {prediction}\n"
        f"Attendance Rate: {features['Attendance_Rate'] * 100:.2f}%\n"
        f"Total Absences: {features['Absences']}\n"
        f"Total Late Arrivals: {features['Late_Arrivals']}\n"
        f"Average Daily Working Hours: {features['Avg_Working_Hours']} hours\n"
        f"Leave Frequency: {features['Leave_Frequency']} times\n"
        f"Monday/Friday Late Trend: {features['Mon_Fri_Late_Trend']}/10\n"
    )
    
    sys_instruction = (
        f"You are a Senior HR Analytics AI Assistant. You help managers understand employee attendance behaviors.\n"
        f"Context for the selected employee:\n{data_context}\n"
        f"Provide a helpful, precise answer in 1-2 sentences max. Speak directly, confidently, and professionally. "
        f"Be very specific about their database metrics."
    )
    
    contents = []
    for msg in req.history:
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({
            "role": role,
            "parts": [{"text": msg.get("content", "")}]
        })
        
    contents.append({
        "role": "user",
        "parts": [{"text": req.question}]
    })
    
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": contents,
                "systemInstruction": {
                    "parts": [{"text": sys_instruction}]
                },
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 200
                }
            }
            
            headers = {"Content-Type": "application/json"}
            import urllib.request
            import json
            req_http = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers=headers, 
                method="POST"
            )
            
            with urllib.request.urlopen(req_http, timeout=8) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                if "candidates" in res_data and res_data["candidates"]:
                    candidate = res_data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        ai_text = candidate["content"]["parts"][0]["text"].strip()
                        return {"response": ai_text}
        except Exception as e:
            print(f"WARNING: Gemini chat call failed: {e}. Falling back to rule-based chatbot.")
            
    # Rule-based chatbot fallback response
    q = req.question.lower()
    name = user.name
    
    if "late" in q or "punctual" in q:
        if prediction == "Irregular Attendance Pattern":
            response = f"{name}'s data indicates a significant late trend with {features['Late_Arrivals']} total late clock-ins, highly clustered on Mondays and Fridays (trend score of {features['Mon_Fri_Late_Trend']}/10). We recommend discussing flexible schedules."
        elif prediction == "Regular Attendee":
            response = f"{name} is exceptionally punctual, maintaining a near-perfect clock-in record with only {features['Late_Arrivals']} late arrival(s) in the past month."
        else:
            response = f"{name} has {features['Late_Arrivals']} late arrival(s), though their primary concern is overall absenteeism."
    elif "absent" in q or "absence" in q or "leave" in q:
        if prediction == "At-Risk Employee (Frequent Absence)":
            response = f"Yes, {name} is classified as high-risk due to {features['Absences']} absences, resulting in a low attendance rate of {features['Attendance_Rate'] * 100:.1f}%."
        else:
            response = f"{name} has a strong attendance record, with only {features['Absences']} absences/leaves logged in the past 30 days."
    elif "hour" in q or "work" in q:
        response = f"{name} averages {features['Avg_Working_Hours']} working hours per day, which indicates good capacity utilization for regular status, but shows disengagement if low."
    elif "advice" in q or "suggest" in q or "action" in q:
        if prediction == "Regular Attendee":
            response = f"Maintain {name}'s excellent workflow, provide opportunities for ownership, and praise their strong punctuality."
        elif prediction == "Irregular Attendance Pattern":
            response = f"Recommend reviewing transit schedules, setting clear core attendance hours, and checking for remote work alignment for {name}."
        else:
            response = f"Arrange an immediate supportive 1-on-1 check-in with {name} to investigate workload burn-out or health-related struggles."
    else:
        response = f"Regarding {name}'s attendance profile: they are classified as a {prediction} with an overall attendance rate of {features['Attendance_Rate'] * 100:.1f}% and an average of {features['Avg_Working_Hours']} hours worked daily."
        
    return {"response": response}

# ================ AI CHAT SYSTEM ENDPOINTS (NEW) ================

@app.post("/api/chat/send")
def send_chat_message(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a chat message and receive an AI response with employee context.
    Supports multi-turn conversations with persistent history.
    """
    try:
        # Validate user exists
        user = db.query(User).filter(User.id == req.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Initialize ChatManager
        chat_manager = ChatManager(db)
        
        # Fetch comprehensive employee context
        employee_context = chat_manager.get_employee_context(req.user_id)
        
        # Get recent chat history for context
        recent_messages = db.query(ChatMessage).filter(
            ChatMessage.user_id == req.user_id
        ).order_by(ChatMessage.created_at.desc()).limit(10).all()
        
        chat_history = [
            {
                "sender": msg.sender,
                "message_text": msg.message_text,
                "created_at": msg.created_at.isoformat()
            }
            for msg in reversed(recent_messages)
        ]
        
        # Generate response using ChatManager
        ai_response = chat_manager.generate_chat_response(
            req.question,
            employee_context,
            chat_history
        )
        
        # Store user message in database
        user_msg = ChatMessage(
            user_id=req.user_id,
            sender="user",
            message_text=req.question,
            created_at=datetime.datetime.utcnow()
        )
        db.add(user_msg)
        
        # Store assistant response in database
        assistant_msg = ChatMessage(
            user_id=req.user_id,
            sender="assistant",
            message_text=ai_response,
            created_at=datetime.datetime.utcnow()
        )
        db.add(assistant_msg)
        db.commit()
        
        return {
            "response": ai_response,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "context": employee_context
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}"
        )

@app.get("/api/chat/history/{user_id}")
def get_chat_history(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """
    Retrieve chat history for a specific user.
    Returns messages in chronological order, limited to most recent N messages.
    """
    try:
        # Validate user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Fetch chat messages
        messages = db.query(ChatMessage).filter(
            ChatMessage.user_id == user_id
        ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
        
        # Reverse to get chronological order
        messages = list(reversed(messages))
        
        history = [
            {
                "id": msg.id,
                "sender": msg.sender,
                "message": msg.message_text,
                "timestamp": msg.created_at.isoformat(),
                "context_employee_id": msg.context_employee_id
            }
            for msg in messages
        ]
        
        return {
            "user_id": user_id,
            "user_name": user.name,
            "message_count": len(history),
            "messages": history,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR fetching chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving chat history: {str(e)}"
        )

@app.delete("/api/chat/clear/{session_id}")
def clear_chat_session(session_id: int, db: Session = Depends(get_db)):
    """
    Clear all chat messages for a user session.
    session_id is treated as user_id for session management.
    Returns confirmation of deleted messages.
    """
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == session_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Count messages before deletion
        message_count = db.query(ChatMessage).filter(
            ChatMessage.user_id == session_id
        ).count()
        
        if message_count == 0:
            return {
                "status": "success",
                "user_id": session_id,
                "messages_deleted": 0,
                "message": "No messages to clear",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        
        # Delete all messages for this user
        db.query(ChatMessage).filter(
            ChatMessage.user_id == session_id
        ).delete()
        db.commit()
        
        return {
            "status": "success",
            "user_id": session_id,
            "messages_deleted": message_count,
            "message": f"Successfully cleared {message_count} chat message(s)",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR clearing chat session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing chat session: {str(e)}"
        )

# ================ PHASE 5: ADVANCED SEARCH ENDPOINTS ================

class AdvancedSearchRequest(BaseModel):
    query: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    save_filter_name: Optional[str] = None
    user_id: int

@app.post("/api/search/advanced")
def advanced_search(req: AdvancedSearchRequest, db: Session = Depends(get_db)):
    """
    Perform advanced search across employees and attendance logs.
    """
    try:
        # Full-text search matching employee name, department or notes in logs
        user_ids_matching_notes = []
        if req.query:
            notes_query = db.query(AttendanceLog.user_id).filter(
                AttendanceLog.notes.like(f"%{req.query}%")
            ).distinct().all()
            user_ids_matching_notes = [u[0] for u in notes_query]
            
        users_query = db.query(User).filter(User.role == "employee")
        
        if req.query:
            users_query = users_query.filter(
                (User.name.like(f"%{req.query}%")) |
                (User.department.like(f"%{req.query}%")) |
                (User.id.in_(user_ids_matching_notes))
            )
            
        if req.department:
            users_query = users_query.filter(User.department == req.department)
            
        if req.role:
            users_query = users_query.filter(User.role == req.role)
            
        matched_users = []
        for employee in users_query.all():
            prediction = predict_attendance_behavior(employee.id, db)
            risk = calculate_absenteeism_risk(employee.id, db)
            
            # Filter by status (risk level or prediction)
            status_match = True
            if req.status:
                status_lower = req.status.lower()
                is_risk_level = status_lower in ["low", "medium", "high", "critical"]
                is_prediction = status_lower in ["regular", "at-risk", "irregular"]
                is_attendance = status_lower in ["present", "absent", "late"]
                
                if is_risk_level:
                    status_match = (risk["risk_level"].lower() == status_lower)
                elif is_prediction:
                    status_match = (status_lower in prediction["prediction"].lower())
                elif is_attendance:
                    att_q = db.query(Attendance).filter(Attendance.user_id == employee.id, Attendance.status.like(f"%{req.status}%"))
                    if req.date_from:
                        df = datetime.datetime.strptime(req.date_from, "%Y-%m-%d").date()
                        att_q = att_q.filter(Attendance.date >= df)
                    if req.date_to:
                        dt = datetime.datetime.strptime(req.date_to, "%Y-%m-%d").date()
                        att_q = att_q.filter(Attendance.date <= dt)
                    status_match = (att_q.count() > 0)
                else:
                    status_match = (
                        status_lower in risk["risk_level"].lower() or
                        status_lower in prediction["prediction"].lower()
                    )
            
            # Filter by date range (must have attendance records in range if range provided)
            if (req.date_from or req.date_to) and status_match:
                att_q = db.query(Attendance).filter(Attendance.user_id == employee.id)
                if req.date_from:
                    df = datetime.datetime.strptime(req.date_from, "%Y-%m-%d").date()
                    att_q = att_q.filter(Attendance.date >= df)
                if req.date_to:
                    dt = datetime.datetime.strptime(req.date_to, "%Y-%m-%d").date()
                    att_q = att_q.filter(Attendance.date <= dt)
                if att_q.count() == 0:
                    status_match = False
                    
            if status_match:
                matched_users.append({
                    "id": employee.id,
                    "name": employee.name,
                    "department": employee.department,
                    "role": employee.role,
                    "email": employee.email,
                    "prediction": prediction["prediction"],
                    "risk_level": risk["risk_level"],
                    "risk_score": risk["risk_score"]
                })
                
        # Save filter if requested
        if req.save_filter_name:
            criteria = {
                "query": req.query,
                "department": req.department,
                "role": req.role,
                "status": req.status,
                "date_from": req.date_from,
                "date_to": req.date_to
            }
            new_filter = SavedFilter(
                user_id=req.user_id,
                name=req.save_filter_name,
                filter_criteria=criteria
            )
            db.add(new_filter)
            db.commit()
            
        # Log audit action
        log_audit_action(
            actor_id=req.user_id,
            action="read_data",
            resource=f"Advanced search execution (Matches: {len(matched_users)})",
            db=db
        )
        
        return matched_users
    except Exception as e:
        print(f"Error in advanced search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search/advanced/export")
def export_search_results(req: AdvancedSearchRequest, db: Session = Depends(get_db)):
    """
    Export search results directly to CSV.
    """
    try:
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        # Reuse search query logic
        matched_users = advanced_search(req, db)
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Department", "Role", "Email", "Prediction", "Risk Level", "Risk Score"])
        for item in matched_users:
            writer.writerow([
                item["id"],
                item["name"],
                item["department"],
                item["role"],
                item["email"],
                item["prediction"],
                item["risk_level"],
                item["risk_score"]
            ])
        output.seek(0)
        
        # Log audit action
        log_audit_action(
            actor_id=req.user_id,
            action="export_data",
            resource=f"CSV export of advanced search results ({len(matched_users)} employees)",
            db=db
        )
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=advanced_search_results.csv"}
        )
    except Exception as e:
        print(f"Error exporting search results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/filters/{user_id}")
def get_saved_filters(user_id: int, db: Session = Depends(get_db)):
    """
    Get all saved filters for a specific user.
    """
    filters = db.query(SavedFilter).filter(SavedFilter.user_id == user_id).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "criteria": f.filter_criteria,
            "created_at": f.created_at.isoformat() if f.created_at else None
        } for f in filters
    ]

@app.delete("/api/search/filters/{filter_id}")
def delete_saved_filter(filter_id: int, db: Session = Depends(get_db)):
    """
    Delete a saved filter by ID.
    """
    f = db.query(SavedFilter).filter(SavedFilter.id == filter_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    db.delete(f)
    db.commit()
    return {"status": "success", "message": "Saved filter deleted"}

# ================ PHASE 5: SMART ALERTING ENDPOINTS ================

class AcknowledgeRequest(BaseModel):
    admin_id: int

class AlertThresholdRequest(BaseModel):
    late_minutes_threshold: int
    risk_score_threshold: float
    anomaly_score_threshold: float
    escalation_occurrences: int

@app.get("/api/alerts/active")
def get_active_alerts(db: Session = Depends(get_db)):
    """
    Get all active (unacknowledged) alerts.
    """
    alerts = db.query(Alert).filter(Alert.is_acknowledged == False).order_by(Alert.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "employee_name": a.user.name if a.user else "Unknown",
            "type": a.type,
            "message": a.message,
            "severity": a.severity,
            "occurrences": a.occurrences,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in alerts
    ]

@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, req: AcknowledgeRequest, db: Session = Depends(get_db)):
    """
    Acknowledge an alert.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert.is_acknowledged = True
    alert.acknowledged_by = req.admin_id
    alert.acknowledged_at = datetime.datetime.utcnow()
    db.commit()
    
    # Log GDPR audit action
    log_audit_action(
        actor_id=req.admin_id,
        action="modify_data",
        resource=f"Acknowledge Alert #{alert_id} for user {alert.user_id}",
        db=db
    )
    
    return {"status": "success", "message": f"Alert #{alert_id} acknowledged"}

@app.get("/api/alerts/thresholds")
def get_alert_thresholds(db: Session = Depends(get_db)):
    """
    Get the current alert thresholds.
    """
    thresholds = get_or_create_thresholds(db)
    return {
        "id": thresholds.id,
        "late_minutes_threshold": thresholds.late_minutes_threshold,
        "risk_score_threshold": thresholds.risk_score_threshold,
        "anomaly_score_threshold": thresholds.anomaly_score_threshold,
        "escalation_occurrences": thresholds.escalation_occurrences
    }

@app.post("/api/alerts/thresholds")
def update_alert_thresholds(req: AlertThresholdRequest, admin_id: int, db: Session = Depends(get_db)):
    """
    Update the alert thresholds.
    """
    thresholds = get_or_create_thresholds(db)
    thresholds.late_minutes_threshold = req.late_minutes_threshold
    thresholds.risk_score_threshold = req.risk_score_threshold
    thresholds.anomaly_score_threshold = req.anomaly_score_threshold
    thresholds.escalation_occurrences = req.escalation_occurrences
    db.commit()
    
    # Log GDPR audit action
    log_audit_action(
        actor_id=admin_id,
        action="modify_data",
        resource="Update alert thresholds",
        db=db
    )
    
    return {"status": "success", "message": "Alert thresholds updated successfully"}

# ================ PHASE 5: GDPR COMPLIANCE ENDPOINTS ================

class GDPRRequest(BaseModel):
    actor_id: int

@app.post("/api/compliance/export/{employee_id}")
def compliance_export(employee_id: int, req: GDPRRequest, db: Session = Depends(get_db)):
    """
    GDPR Portability requirement: Export all data associated with an employee.
    """
    # Check if employee exists
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    data = export_employee_data(employee_id, db)
    
    # Log GDPR audit action
    log_audit_action(
        actor_id=req.actor_id,
        action="export_data",
        resource=f"GDPR Export for Employee ID #{employee_id} ({user.name})",
        db=db
    )
    
    return data

@app.post("/api/compliance/delete/{employee_id}")
def compliance_delete(employee_id: int, req: GDPRRequest, db: Session = Depends(get_db)):
    """
    GDPR Right to be Forgotten: Permanently erase an employee's record and all logs.
    """
    # Check if employee exists
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    emp_name = user.name
    success = delete_employee_data(employee_id, db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete employee data")
        
    # Log GDPR audit action
    log_audit_action(
        actor_id=req.actor_id,
        action="delete_employee",
        resource=f"GDPR Delete Employee ID #{employee_id} ({emp_name})",
        db=db
    )
    
    return {"status": "success", "message": f"Successfully deleted all data for employee: {emp_name}"}

@app.get("/api/compliance/audit-trail/{employee_id}")
def get_audit_trail(employee_id: int, actor_id: int, db: Session = Depends(get_db)):
    """
    Retrieve audit trail logs involving a specific employee's resource.
    """
    # Check if employee exists
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    # Retrieve logs that mention "user {employee_id}" or "Employee ID #{employee_id}"
    logs = db.query(AuditLog).filter(
        (AuditLog.resource.like(f"%user {employee_id}%")) |
        (AuditLog.resource.like(f"%Employee ID #{employee_id}%"))
    ).order_by(AuditLog.timestamp.desc()).all()
    
    # Log GDPR audit access action
    log_audit_action(
        actor_id=actor_id,
        action="read_data",
        resource=f"Access GDPR Audit trail for employee #{employee_id}",
        db=db
    )
    
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "action": log.action,
            "resource": log.resource,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "old_value": log.old_value,
            "new_value": log.new_value
        } for log in logs
    ]

@app.post("/api/compliance/audit-trail/cleanup")
def cleanup_audit_logs(actor_id: int, retention_years: int = 7, db: Session = Depends(get_db)):
    """
    Manually trigger cleanup of audit logs older than the retention period.
    """
    from compliance import clean_expired_audit_logs
    deleted = clean_expired_audit_logs(db, retention_years)
    
    log_audit_action(
        actor_id=actor_id,
        action="modify_data",
        resource=f"Cleaned expired audit logs (deleted {deleted} entries)",
        db=db
    )
    return {"status": "success", "deleted_count": deleted}

# ================ PHASE 3: AI CHAT ENDPOINTS ================

class ChatMessageRequest(BaseModel):
    user_id: int
    question: str
    history: List[Dict] = []

@app.post("/api/chat/send")
def chat_send(req: ChatMessageRequest, db: Session = Depends(get_db)):
    """
    Send a message to the AI Chat assistant and get a response.
    """
    try:
        chat_manager = ChatManager(db)
        # Fetch employee context for the requested user
        emp_context = chat_manager.get_employee_context(req.user_id)
        if not emp_context:
            raise HTTPException(status_code=404, detail="Employee not found")
            
        # Get AI response
        ai_response = chat_manager.generate_chat_response(req.question, emp_context, req.history)
        
        # Save user message to history
        user_msg = ChatMessage(
            user_id=1,  # Assuming admin (id=1) is chatting
            sender="user",
            message_text=req.question,
            context_employee_id=req.user_id
        )
        db.add(user_msg)
        
        # Save AI response to history
        ai_msg = ChatMessage(
            user_id=1,
            sender="assistant",
            message_text=ai_response,
            context_employee_id=req.user_id
        )
        db.add(ai_msg)
        db.commit()
        
        return {"response": ai_response}
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history/{user_id}")
def get_chat_history(user_id: int, db: Session = Depends(get_db)):
    """
    Get chat history related to a specific employee.
    """
    history = db.query(ChatMessage).filter(
        ChatMessage.context_employee_id == user_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return [
        {
            "id": msg.id,
            "sender": msg.sender,
            "message_text": msg.message_text,
            "timestamp": msg.created_at.isoformat() if msg.created_at else None
        } for msg in history
    ]

@app.delete("/api/chat/clear/{user_id}")
def clear_chat_history(user_id: int, db: Session = Depends(get_db)):
    """
    Clear chat history related to a specific employee.
    """
    db.query(ChatMessage).filter(ChatMessage.context_employee_id == user_id).delete()
    db.commit()
    return {"status": "success", "message": "Chat history cleared"}

if __name__ == "__main__":
    import uvicorn
    # Use environment PORT or default to 5000
    port = int(os.getenv("PORT", 5000))
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)
