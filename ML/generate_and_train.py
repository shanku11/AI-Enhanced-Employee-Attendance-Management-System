import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import os

# Create directory if it doesn't exist
os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)

# Set random seed for reproducibility
np.random.seed(42)

# Generate synthetic dataset of 500 employees
num_employees = 500

# Features:
# 1. Attendance_Rate: percentage of days present (e.g. 0.5 to 1.0)
# 2. Absences: number of absences (e.g. 0 to 30)
# 3. Late_Arrivals: number of late arrivals (e.g. 0 to 25)
# 4. Avg_Working_Hours: average working hours per day (e.g. 4.0 to 9.5)
# 5. Leave_Frequency: number of leaves taken (e.g. 0 to 15)
# 6. Mon_Fri_Late_Trend: rate of Monday/Friday lateness (e.g. 0 to 10, higher = more frequent lateness on Mon/Fri)

data = []
for i in range(num_employees):
    emp_id = f"EMP{i+1:03d}"
    
    # We will define three classes and generate features corresponding to them
    # Class 0: Regular Attendee
    # Class 1: At-Risk Employee
    # Class 2: Irregular Attendance Pattern
    
    # Distribute classes: 60% Regular, 20% At-Risk, 20% Irregular
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
        avg_working_hours = np.random.uniform(5.5, 7.8)
        leave_frequency = int(np.random.uniform(8, 18))
        mon_fri_late_trend = np.random.uniform(2.0, 6.0)
        status = 1  # At-Risk
    else:
        # Irregular Pattern
        attendance_rate = np.random.uniform(0.80, 0.91)
        absences = int(np.random.poisson(lam=6))
        late_arrivals = int(np.random.uniform(10, 26))
        avg_working_hours = np.random.uniform(7.0, 8.4)
        leave_frequency = int(np.random.poisson(lam=4.0))
        mon_fri_late_trend = np.random.uniform(6.5, 9.5)
        status = 2  # Irregular
        
    data.append({
        "Employee_ID": emp_id,
        "Attendance_Rate": round(attendance_rate, 4),
        "Absences": absences,
        "Late_Arrivals": late_arrivals,
        "Avg_Working_Hours": round(avg_working_hours, 2),
        "Leave_Frequency": leave_frequency,
        "Mon_Fri_Late_Trend": round(mon_fri_late_trend, 2),
        "Status": status
    })

df = pd.DataFrame(data)

# Save dataset
dataset_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance_data.csv")
df.to_csv(dataset_path, index=False)
print(f"Dataset generated and saved to: {dataset_path}")

# Preprocessing & Model Training
X = df[["Attendance_Rate", "Absences", "Late_Arrivals", "Avg_Working_Hours", "Leave_Frequency", "Mon_Fri_Late_Trend"]]
y = df["Status"]

# Train/Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Initialize Random Forest Classifier
rf_clf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)

# Train the model
rf_clf.fit(X_train, y_train)

# Make predictions
y_pred = rf_clf.predict(X_test)

# Evaluate the model
accuracy = accuracy_score(y_test, y_pred)
conf_matrix = confusion_matrix(y_test, y_pred)
class_report = classification_report(y_test, y_pred, target_names=["Regular Attendee", "At-Risk Employee", "Irregular Attendance Pattern"])

print("\n--- Model Evaluation ---")
print(f"Accuracy: {accuracy:.4f}")
print("\nConfusion Matrix:")
print(conf_matrix)
print("\nClassification Report:")
print(class_report)

# Save the trained model
model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance_model.joblib")
joblib.dump(rf_clf, model_path)
print(f"Model saved to: {model_path}")
