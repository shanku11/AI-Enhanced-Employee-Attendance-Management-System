# Project Report

## Title

AI-Enhanced Employee Attendance Management System

## Objective

Build a full-stack attendance system that supports employee attendance marking, HR analytics, Random Forest based attendance behavior prediction, and automated HR insight generation.

## Implemented Modules

| Module | Implementation |
| --- | --- |
| Authentication | Employee/admin registration and login APIs with role-based dashboards |
| Attendance Management | Present, Absent, Late marking; check-in/check-out; working hour calculation |
| Employee Dashboard | Personal attendance statistics and attendance history |
| HR Dashboard | Employee overview, company stats, master logs, search, alerts, compliance tools |
| Machine Learning | Scikit-learn Random Forest trained from attendance features and served through analytics APIs |
| Generative AI | Gemini API integration with local fallback insight generator |
| Reports | Daily and monthly report APIs with CSV, Excel, and PDF export endpoints |
| Database | SQLAlchemy models with SQLite default and MySQL support through `DATABASE_URL` |

## ML Feature Set

The prediction module derives these features from attendance records:

- Attendance rate
- Absences
- Late arrivals
- Average working hours
- Leave frequency
- Monday/Friday lateness trend
- Absence variance
- Recent trend
- Punctuality score

## Prediction Classes

- Regular
- At-Risk
- Irregular

## Important API Endpoints

| Area | Endpoint |
| --- | --- |
| Register | `POST /api/auth/register` |
| Login | `POST /api/auth/login` |
| Mark Attendance | `POST /api/attendance/mark` |
| Employee Reports | `GET /api/attendance/reports?user_id=2` |
| ML Prediction | `GET /api/analytics/predict/{user_id}` |
| GenAI Insight | `GET /api/analytics/insights/{user_id}` |
| Daily Report | `GET /api/reports/daily?date=2026-06-09` |
| Monthly Report | `GET /api/reports/monthly?year=2026&month=6` |
| Export | `GET /api/reports/export?report_type=monthly&year=2026&month=6&format=csv` |

## Demo Flow

1. Sign in as `alice` / `password123`.
2. Mark attendance from the employee dashboard.
3. Sign out and sign in as `admin` / `password123`.
4. Review company statistics and attendance logs.
5. Select an employee to view Random Forest classification and AI-generated HR insight.
6. Use report export endpoints for CSV, Excel, or PDF output.
