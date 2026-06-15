#!/usr/bin/env python
import urllib.request
import urllib.error
import json

# Test the three chat endpoints
BASE_URL = "http://localhost:5000"

print("Testing /api/health endpoint...")
try:
    req = urllib.request.Request(f"{BASE_URL}/api/health", method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        content = json.loads(resp.read().decode("utf-8"))
        print(f"Health Status: {resp.status}")
        print(f"Health Response: {content}")
except Exception as e:
    print(f"Health Error: {e}")

print("\n" + "="*50)
print("Testing /api/chat/send endpoint...")
try:
    payload = {
        "user_id": 2,
        "question": "Is Alice often late?",
        "history": []
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat/send",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = json.loads(resp.read().decode("utf-8"))
        print(f"Chat Send Status: {resp.status}")
        print(f"Chat Send Response: {json.dumps(content, indent=2)}")
except Exception as e:
    print(f"Chat Send Error: {e}")

print("\n" + "="*50)
print("Testing /api/chat/history/2 endpoint...")
try:
    req = urllib.request.Request(f"{BASE_URL}/api/chat/history/2", method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        content = json.loads(resp.read().decode("utf-8"))
        print(f"Chat History Status: {resp.status}")
        print(f"Chat History Response: {json.dumps(content, indent=2)}")
except Exception as e:
    print(f"Chat History Error: {e}")

print("\n" + "="*50)
print("Testing /api/chat/clear/2 endpoint...")
try:
    req = urllib.request.Request(f"{BASE_URL}/api/chat/clear/2", method="DELETE")
    with urllib.request.urlopen(req, timeout=5) as resp:
        content = json.loads(resp.read().decode("utf-8"))
        print(f"Chat Clear Status: {resp.status}")
        print(f"Chat Clear Response: {json.dumps(content, indent=2)}")
except Exception as e:
    print(f"Chat Clear Error: {e}")
