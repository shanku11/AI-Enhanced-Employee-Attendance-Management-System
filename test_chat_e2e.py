import sys
sys.path.insert(0, "D:\\Projects\\Gradious\\Backend")
from fastapi.testclient import TestClient
from Backend.main import app

client = TestClient(app)

print("Testing Chat Endpoints with TestClient")

# 1. Clear chat for user 2
print("\n--- Clearing Chat ---")
response = client.delete("/api/chat/clear/2")
print(response.status_code)
print(response.json())

# 2. Get history (should be empty)
print("\n--- Get History ---")
response = client.get("/api/chat/history/2")
print(response.status_code)
print(response.json())

# 3. Send a message
print("\n--- Send Message ---")
payload = {
    "user_id": 2,
    "question": "Is Alice often late?",
    "history": []
}
response = client.post("/api/chat/send", json=payload)
print(response.status_code)
print(response.json())

# 4. Get history again
print("\n--- Get History After Sending ---")
response = client.get("/api/chat/history/2")
print(response.status_code)
print(response.json())

print("\n--- DONE ---")
