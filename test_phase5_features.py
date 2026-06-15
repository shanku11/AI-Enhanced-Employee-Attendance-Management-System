#!/usr/bin/env python
import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://localhost:5000"

def make_request(url, method="GET", payload=None, headers=None):
    if headers is None:
        headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        data = None
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            if resp.getheader("Content-Type") == "text/csv":
                return resp.status, content.decode("utf-8"), "csv"
            
            try:
                parsed = json.loads(content.decode("utf-8"))
                return resp.status, parsed, "json"
            except:
                return resp.status, content.decode("utf-8"), "text"
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except:
            err_body = str(e)
        return e.code, err_body, "error"
    except Exception as e:
        return 0, str(e), "exception"

print("="*60)
print("PHASE 5 INTEGRATION VERIFICATION TEST")
print("="*60)

# Wait 2 seconds for server to make sure it's fully ready
time.sleep(2)

# 1. Health check
status, health_resp, _ = make_request(f"{BASE_URL}/api/health")
print(f"[HEALTH] Status: {status}")
print(f"[HEALTH] Response: {health_resp}")
assert status == 200, "Health check failed"

print("\n" + "-"*40)
print("TESTING ADVANCED SEARCH")
print("-"*40)

# Test 1: Full Employee search (empty DSL query)
status, search_resp, _ = make_request(
    f"{BASE_URL}/api/search/advanced",
    method="POST",
    payload={"user_id": 1}
)
print(f"[SEARCH] All Employees Status: {status}")
print(f"[SEARCH] All Employees Count: {len(search_resp) if status == 200 else 'Error'}")
if status == 200:
    for emp in search_resp:
        print(f" - ID: {emp['id']}, Name: {emp['name']}, Dept: {emp['department']}, Risk: {emp['risk_level']}")

# Test 2: Search with specific department filter
status, dept_resp, _ = make_request(
    f"{BASE_URL}/api/search/advanced",
    method="POST",
    payload={"user_id": 1, "department": "Engineering"}
)
print(f"[SEARCH] Dept=Engineering Status: {status}")
if status == 200:
    print(f" - Found {len(dept_resp)} in Engineering")
    for emp in dept_resp:
        assert emp["department"] == "Engineering", "Department filtering failed"

# Test 3: Save custom filter
status, save_resp, _ = make_request(
    f"{BASE_URL}/api/search/advanced",
    method="POST",
    payload={"user_id": 1, "department": "Marketing", "save_filter_name": "Marketing Team Filter"}
)
print(f"[SEARCH] Save Filter Status: {status}")

# Test 4: Retrieve saved filters
status, filters_resp, _ = make_request(f"{BASE_URL}/api/search/filters/1")
print(f"[SEARCH] Get Saved Filters: {filters_resp}")
filter_id = None
if status == 200 and len(filters_resp) > 0:
    filter_id = filters_resp[0]["id"]
    print(f" - Saved Filter Saved Successfully. Filter ID = {filter_id}")

# Test 5: Delete saved filter
if filter_id:
    status, del_resp, _ = make_request(f"{BASE_URL}/api/search/filters/{filter_id}", method="DELETE")
    print(f"[SEARCH] Delete Filter Status: {status}, Resp: {del_resp}")

# Test 6: CSV Export
status, csv_resp, r_type = make_request(
    f"{BASE_URL}/api/search/advanced/export",
    method="POST",
    payload={"user_id": 1}
)
print(f"[SEARCH] CSV Export Status: {status}, Response Type: {r_type}")
if status == 200:
    print("CSV Content Snippet:")
    print("\n".join(csv_resp.split("\n")[:4]))

print("\n" + "-"*40)
print("TESTING SMART ALERTING SYSTEM")
print("-"*40)

# Test 1: Get thresholds
status, thresholds, _ = make_request(f"{BASE_URL}/api/alerts/thresholds")
print(f"[ALERTS] Current Thresholds: {thresholds}")

# Test 2: Set very strict late minutes threshold (e.g. 2 minutes) to test triggers easily
status, upd_thresh, _ = make_request(
    f"{BASE_URL}/api/alerts/thresholds?admin_id=1",
    method="POST",
    payload={
        "late_minutes_threshold": 2,
        "risk_score_threshold": 60.0,
        "anomaly_score_threshold": 40.0,
        "escalation_occurrences": 3
    }
)
print(f"[ALERTS] Update Thresholds Status: {status}, Response: {upd_thresh}")

# Test 3: Get active alerts before triggering
status, pre_alerts, _ = make_request(f"{BASE_URL}/api/alerts/active")
print(f"[ALERTS] Active Alerts Count before triggering: {len(pre_alerts) if status == 200 else 'Error'}")

# Test 4: Trigger late arrival by manually marking attendance for user 2 (Alice) at 9:15 AM
# Since 9:15 is 15 minutes late, and threshold is 2, it should trigger alert!
status, mark_resp, _ = make_request(
    f"{BASE_URL}/api/attendance/mark",
    method="POST",
    payload={
        "user_id": 2,
        "date": "2026-06-04",
        "clock_in": "09:15",
        "status": "Late"
    }
)
print(f"[ALERTS] Mark Late Attendance (Trigger 1) Status: {status}")

# Test 5: Verify alert creation
status, post_alerts1, _ = make_request(f"{BASE_URL}/api/alerts/active")
print(f"[ALERTS] Active Alerts Count after Trigger 1: {len(post_alerts1)}")
alert_id = None
if len(post_alerts1) > 0:
    for al in post_alerts1:
        if al["user_id"] == 2 and al["type"] == "late_arrival":
            alert_id = al["id"]
            print(f" - Found Late Arrival Alert! ID: {alert_id}, Occurrences: {al['occurrences']}, Severity: {al['severity']}")

# Test 6: Verify escalation rules (occurrences trigger)
# Trigger late arrival 2 more times (occurrences = 2, then occurrences = 3 which triggers critical severity)
print(" - Triggering alert occurrence #2...")
make_request(
    f"{BASE_URL}/api/attendance/mark",
    method="POST",
    payload={"user_id": 2, "date": "2026-06-05", "clock_in": "09:15", "status": "Late"}
)
print(" - Triggering alert occurrence #3 (should escalate to critical)...")
make_request(
    f"{BASE_URL}/api/attendance/mark",
    method="POST",
    payload={"user_id": 2, "date": "2026-06-06", "clock_in": "09:15", "status": "Late"}
)

status, post_alerts3, _ = make_request(f"{BASE_URL}/api/alerts/active")
for al in post_alerts3:
    if al["user_id"] == 2 and al["type"] == "late_arrival":
        print(f" - Escalated Alert Check -> ID: {al['id']}, Occurrences: {al['occurrences']}, Severity: {al['severity']}, Message: {al['message']}")
        assert al["occurrences"] == 3, "Escalation occurrences check failed"
        assert al["severity"] == "critical", "Escalation severity upgrade failed"
        assert "[ESCALATED]" in al["message"], "Escalation prefixing failed"

# Test 7: Acknowledge alert
if alert_id:
    status, ack_resp, _ = make_request(
        f"{BASE_URL}/api/alerts/{alert_id}/acknowledge",
        method="POST",
        payload={"admin_id": 1}
    )
    print(f"[ALERTS] Acknowledge Alert Status: {status}, Response: {ack_resp}")
    
    status, post_alerts_ack, _ = make_request(f"{BASE_URL}/api/alerts/active")
    print(f"[ALERTS] Active Alerts Count after acknowledgement: {len(post_alerts_ack)}")
    assert len(post_alerts_ack) == len(post_alerts3) - 1, "Acknowledgement failed to clear active status"

print("\n" + "-"*40)
print("TESTING GDPR COMPLIANCE & AUDIT")
print("-"*40)

# Test 1: GDPR Employee Data Export (Employee 2 - Alice)
status, export_resp, _ = make_request(
    f"{BASE_URL}/api/compliance/export/2",
    method="POST",
    payload={"actor_id": 1}
)
print(f"[GDPR] Export Status: {status}")
if status == 200:
    print("Export JSON Keys:", list(export_resp.keys()))
    print("User Name in export:", export_resp["user_profile"]["name"])
    print("Attendance records exported count:", len(export_resp["attendance_records"]))
    print("Alerts exported count:", len(export_resp["alerts"]))
    assert export_resp["user_profile"]["name"] == "Alice Johnson", "GDPR export data matching failed"

# Test 2: GDPR Audit Trail Retrieval
status, audit_trail, _ = make_request(f"{BASE_URL}/api/compliance/audit-trail/2?actor_id=1")
print(f"[GDPR] Audit Trail Status: {status}")
if status == 200:
    print(f" - Audit trail has {len(audit_trail)} logs for user #2:")
    for log in audit_trail[:5]:
        print(f"   * Actor {log['actor_id']} performed '{log['action']}' on '{log['resource']}' at {log['timestamp']}")
    # Assert there is a read_data/export_data log
    actions = [l["action"] for l in audit_trail]
    assert "export_data" in actions, "GDPR audit trail failed to log data export"

# Test 3: GDPR Right to be Forgotten (Delete Employee 4 - Charlie Davis)
# Let's verify Charlie exists first
status, charlie_search, _ = make_request(
    f"{BASE_URL}/api/search/advanced",
    method="POST",
    payload={"user_id": 1, "query": "Charlie"}
)
print(f"[GDPR] Pre-delete Charlie Search Count: {len(charlie_search) if status == 200 else 0}")
assert len(charlie_search) > 0, "Charlie not found in database before delete"

# Perform GDPR deletion
status, delete_resp, _ = make_request(
    f"{BASE_URL}/api/compliance/delete/4",
    method="POST",
    payload={"actor_id": 1}
)
print(f"[GDPR] Delete Employee Status: {status}, Response: {delete_resp}")
assert status == 200, "GDPR delete failed"

# Verify employee is completely erased
status, post_charlie_search, _ = make_request(
    f"{BASE_URL}/api/search/advanced",
    method="POST",
    payload={"user_id": 1, "query": "Charlie"}
)
print(f"[GDPR] Post-delete Charlie Search Count: {len(post_charlie_search) if status == 200 else 0}")
assert len(post_charlie_search) == 0, "GDPR delete failed to remove user record"

# Verify user 4 login fails/does not exist
status, login_err, _ = make_request(
    f"{BASE_URL}/api/auth/login",
    method="POST",
    payload={"username": "charlie", "password": "password123"}
)
print(f"[GDPR] Charlie Login check (should fail): Status={status}, Response={login_err}")
assert status == 404, "Erased user is still able to log in"

# Verify audit trail logs for cleanup
status, cleanup_resp, _ = make_request(f"{BASE_URL}/api/compliance/audit-trail/cleanup?actor_id=1&retention_years=7", method="POST")
print(f"[GDPR] Cleanup old logs Status: {status}, Response: {cleanup_resp}")
assert status == 200, "Compliance log cleanup endpoint failed"

print("\n" + "="*60)
print("ALL TESTS PASSED SUCCESSFULLY! [SUCCESS]")
print("="*60)

