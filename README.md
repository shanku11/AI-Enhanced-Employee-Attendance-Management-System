# AI-Enhanced Employee Attendance Management System

## Project Overview

This is a full-stack, web-based employee attendance management system integrated with a classic Machine Learning model (Random Forest Classifier) for behavior category prediction and a Generative AI module (simulated or via Google Gemini API) for natural language HR insights.

This project fulfills the requirements for the Gradious AI-Enhanced Employee Attendance Management System assignment.

## Folder Structure

The project is structured into three main directories:

*   **`Frontend/`**: Contains the client-side code (HTML, CSS, JS). Built with vanilla web technologies and features a premium, modern glassmorphic design.
*   **`Backend/`**: Contains the FastAPI server, SQLite database configuration, and API endpoints for authentication, attendance marking, ML inference, and AI insight generation.
*   **`ML/`**: Contains the Python scripts and Jupyter Notebook for generating synthetic data, preprocessing, training the Random Forest Classifier, and evaluating its performance.
*   **`database/`**: Contains MySQL-compatible schema and seed account script.
*   **`docs/`**: Contains architecture and project report documentation.

## Technology Stack

*   **Frontend**: HTML5, CSS3 (Vanilla, custom properties, glassmorphism), JavaScript (Vanilla)
*   **Backend**: Python, FastAPI, Uvicorn, SQLAlchemy, SQLite (default, easily configurable to MySQL)
*   **Machine Learning**: Python, Scikit-learn, Pandas, NumPy, Joblib
*   **Generative AI**: Google Gemini API (with a robust rule-based fallback simulator if no API key is provided)

## Getting Started

### Prerequisites

*   Python 3.7+ installed on your system.

### 1. Backend Setup

1.  Open a terminal in the project root directory (`Gradious/`).
2.  Install the required Python packages:
    ```bash
    py -m pip install -r Backend/requirements.txt
    ```
    *(Note: If you run into issues, you can also manually install: `pip install fastapi uvicorn sqlalchemy scikit-learn pandas numpy joblib`)*
3.  **(Optional)**: If you want to use real Google Gemini AI, open `Backend/.env` and add your `GEMINI_API_KEY`. If left blank, the system will use a highly realistic simulated AI generator.
4.  Start the FastAPI backend server:
    ```bash
    cd Backend
    py -m uvicorn main:app --port 5000
    ```
    On this workstation you can also run:
    ```powershell
    .\run_backend.ps1
    ```
    *The server will start on `http://127.0.0.1:5000`. On the first run, it will automatically create the SQLite database (`attendance_runtime_v2.db`) and seed it with realistic mock data.*

### 2. Machine Learning Module (Optional)

The backend already includes a pre-trained model. If you want to view the training process or retrain the model:

1.  Open the Jupyter Notebook `ML/ML_Notebook.ipynb` to see the step-by-step workflow.
2.  Alternatively, you can run the generator script directly to generate new data and train the model:
    ```bash
    py ML/generate_and_train.py
    ```

### 3. Frontend Usage

1.  Simply open the `Frontend/index.html` file in any modern web browser.
2.  **Demo Accounts** (The system is pre-seeded with these accounts):
    *   **HR Admin**: Username: `admin`, Password: `password123`
    *   **Regular Employee**: Username: `alice`, Password: `password123`
    *   **At-Risk Employee**: Username: `bob`, Password: `password123`
    *   **Irregular Employee**: Username: `charlie`, Password: `password123`

## Key Features

*   **Role-Based Access**: Distinct dashboard views for Employees and HR Administrators.
*   **Live Clock-in/out**: Employees can mark their attendance with automatic working hours calculation.
*   **Predictive Analytics**: The system utilizes a Random Forest model to classify employees into "Regular", "At-Risk", or "Irregular" patterns based on their historical attendance data.
*   **Generative AI Insights**: The HR dashboard generates contextual, professional HR recommendations for selected employees based on their data.
*   **AI Chat Assistant**: HR admins can chat with the interactive AI to ask specific questions about an employee's attendance record (e.g., "Is Bob late often?").
*   **Reports and Exports**: Daily and monthly reports are available as JSON and can be exported as CSV, Excel, or PDF.
*   **Expanded Demo Workforce**: Startup seeding creates 20+ employees with mixed regular, at-risk, and irregular attendance histories.
*   **Company CSV Labeling**: HR can upload a company CSV and classify each row with the same ML model used by the dashboard.
*   **EmailJS Warning Mail**: HR settings allow EmailJS service/template/public-key configuration and warning email previews for selected employees.
*   **Premium UI**: A sleek, dynamic interface with responsive charts, custom typography, and micro-animations.

## Report Endpoints

```text
GET /api/reports/daily?date=2026-06-09
GET /api/reports/monthly?year=2026&month=6
GET /api/reports/export?report_type=daily&date=2026-06-09&format=csv
GET /api/reports/export?report_type=monthly&year=2026&month=6&format=xlsx
GET /api/reports/export?report_type=monthly&year=2026&month=6&format=pdf
```

## Company CSV Upload

Use the HR dashboard `Company CSV` tab or call:

```text
GET  /api/company/csv-template
POST /api/company/upload-csv
```

CSV columns:

```text
EmployeeID,Name,Email,Department,Absences,LateCount,AvgHours,LeaveFrequency,AttendanceRate
```

The response labels each employee row as `Regular`, `At-Risk`, or `Irregular` with model confidence.

A ready-to-upload sample file is available at `docs/sample_company_attendance.csv`.

## EmailJS Warning Mail

Use the HR dashboard `Settings` tab or call:

```text
GET  /api/settings/emailjs
POST /api/settings/emailjs
POST /api/warnings/email-preview
```

Required EmailJS values are `service_id`, `template_id`, and `public_key`. The frontend sends template variables including `to_name`, `to_email`, `subject`, `message`, `prediction`, `confidence`, `from_name`, and `reply_to`.

## MySQL Setup

The default development database is SQLite. To run against MySQL:

1. Import `database/schema_mysql.sql` into your MySQL server.
2. Set `DATABASE_URL` in `Backend/.env` or your shell:
   ```text
   mysql+pymysql://user:password@localhost/ai_attendance_system
   ```
3. Restart the backend.

## Submission Checklist

* Source code: `Backend/`, `Frontend/`, `ML/`
* Database script: `database/schema_mysql.sql`
* ML dataset and trained models: `ML/attendance_data.csv`, `ML/attendance_model_current.joblib`, `ML/ensemble_model_current.joblib`
* ML notebook: `ML/ML_Notebook.ipynb`
* Documentation: `README.md`, `docs/ARCHITECTURE.md`, `docs/PROJECT_REPORT.md`
