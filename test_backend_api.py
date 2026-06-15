import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_health():
    print(f"Testing connectivity to {BASE_URL}...")
    try:
        # FastAPI default docs endpoint can serve as a health check
        res = requests.get(f"{BASE_URL}/docs")
        if res.status_code == 200:
            print("✅ Server is running.")
        else:
            print(f"❌ Server returned status {res.status_code}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

def test_login():
    print("\nTesting Login...")
    payload = {"username": "admin", "password": "password123"}
    try:
        res = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
        if res.status_code == 200:
            print("✅ Login successful.")
            return res.json()
        else:
            print(f"❌ Login failed: {res.text}")
    except Exception as e:
        print(f"❌ Login request failed: {e}")
    return None

def test_employees():
    print("\nTesting get all employees...")
    try:
        res = requests.get(f"{BASE_URL}/api/attendance/employees")
        if res.status_code == 200:
            emps = res.json()
            print(f"✅ Fetched {len(emps)} employees.")
            return emps
        else:
            print(f"❌ Get employees failed: {res.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")
    return []

if __name__ == "__main__":
    test_health()
    admin_user = test_login()
    employees = test_employees()
