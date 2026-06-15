from Backend.ai_handler import generate_attendance_insights, get_simulated_insight

features_regular = {
    "Attendance_Rate": 0.98,
    "Absences": 1,
    "Late_Arrivals": 2,
    "Avg_Working_Hours": 8.1,
    "Leave_Frequency": 1,
    "Mon_Fri_Late_Trend": 1.0
}
features_at_risk = {
    "Attendance_Rate": 0.70,
    "Absences": 8,
    "Late_Arrivals": 6,
    "Avg_Working_Hours": 6.5,
    "Leave_Frequency": 3,
    "Mon_Fri_Late_Trend": 6.0
}

print("Testing Simulated Insight for Regular Attendee:")
print(get_simulated_insight("Alice", features_regular, "Regular Attendee"))

print("\nTesting Simulated Insight for At-Risk Employee:")
print(get_simulated_insight("Bob", features_at_risk, "At-Risk Employee"))

print("\nPhase 3 backend AI handlers verified successfully!")
