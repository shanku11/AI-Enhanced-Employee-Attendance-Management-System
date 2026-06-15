from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import os

# Database Connection configuration
# Default to project-root attendance_runtime_v2.db so SQLite can create journal
# files reliably whether the app is launched from the root or Backend directory.
# app is launched from the project root or from the Backend directory.
# Can be configured for MySQL by supplying DATABASE_URL, e.g.
# mysql+pymysql://user:pass@host/dbname
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
DEFAULT_SQLITE_PATH = os.path.join(PROJECT_ROOT, "attendance_runtime_v3.db")
DEFAULT_SQLITE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.replace(os.sep, '/')}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

# If using SQLite, we need connect_args={"check_same_thread": False}
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    role = Column(String(20), default="employee")  # 'employee' or 'admin'
    name = Column(String(100), nullable=False)
    department = Column(String(100), default="General")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    attendances = relationship("Attendance", back_populates="user", cascade="all, delete-orphan")
    attendance_logs = relationship("AttendanceLog", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    predictions = relationship("PredictionCache", back_populates="user", cascade="all, delete-orphan")
    insights = relationship("EmployeeInsight", back_populates="user", cascade="all, delete-orphan")
    saved_filters = relationship("SavedFilter", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")

class Attendance(Base):
    __tablename__ = "attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, default=datetime.date.today, nullable=False, index=True)
    clock_in = Column(DateTime, nullable=False)
    clock_out = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)  # 'Present', 'Absent', 'Late'
    working_hours = Column(Float, default=0.0)
    
    user = relationship("User", back_populates="attendances")

class AttendanceLog(Base):
    """Fine-grained attendance tracking for real-time updates"""
    __tablename__ = "attendance_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, default=datetime.date.today, nullable=False, index=True)
    clock_in_time = Column(DateTime, nullable=True, index=True)
    clock_out_time = Column(DateTime, nullable=True, index=True)
    current_status = Column(String(20), nullable=False)  # 'clocked_in', 'clocked_out', 'on_break'
    working_hours_so_far = Column(Float, default=0.0)
    break_minutes = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    
    user = relationship("User", back_populates="attendance_logs")

class PredictionCache(Base):
    """Cache ML predictions with timestamps for performance"""
    __tablename__ = "prediction_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    prediction_type = Column(String(50), nullable=False)  # 'behavior_category', 'absenteeism_risk', etc.
    prediction_value = Column(String(100), nullable=False)  # 'Regular', 'At-Risk', 'Irregular'
    confidence_score = Column(Float, nullable=False)  # 0-100
    features = Column(JSON, nullable=True)  # Store features used for prediction
    model_version = Column(String(50), default="1.0")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)  # Cache expiration
    
    user = relationship("User", back_populates="predictions")

class ChatMessage(Base):
    """Store AI chat history for persistence and context"""
    __tablename__ = "chat_message"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sender = Column(String(20), nullable=False)  # 'user' or 'assistant'
    message_text = Column(Text, nullable=False)
    context_employee_id = Column(Integer, nullable=True)  # Employee being asked about
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    
    user = relationship("User", back_populates="chat_messages")

class EmployeeInsight(Base):
    """Store AI-generated insights about employees"""
    __tablename__ = "employee_insight"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    insight_type = Column(String(50), nullable=False)  # 'recommendation', 'alert', 'summary'
    insight_title = Column(String(200), nullable=False)
    insight_content = Column(Text, nullable=False)
    severity = Column(String(20), default="info")  # 'info', 'warning', 'critical'
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    
    user = relationship("User", back_populates="insights")

class SavedFilter(Base):
    __tablename__ = "saved_filters"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    filter_criteria = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="saved_filters")

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # 'late_arrival', 'unplanned_absence', 'at_risk_prediction', 'anomaly'
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="info")  # 'low', 'medium', 'high', 'critical'
    occurrences = Column(Integer, default=1)
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="alerts")

class AlertThreshold(Base):
    __tablename__ = "alert_thresholds"
    
    id = Column(Integer, primary_key=True, index=True)
    late_minutes_threshold = Column(Integer, default=10)
    risk_score_threshold = Column(Float, default=70.0)
    anomaly_score_threshold = Column(Float, default=50.0)
    escalation_occurrences = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, nullable=False, index=True)
    action = Column(String(50), nullable=False)  # 'read_data', 'modify_data', 'delete_employee', 'export_data'
    resource = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
