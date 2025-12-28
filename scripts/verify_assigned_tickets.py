
import requests
import sys

BASE_URL = "http://localhost:8000"

def verify_assigned():
    print("🧪 Verifying Assigned Tickets Endpoint...")
    
    # 1. Login to get token
    email = "newadmin@example.com"
    password = "password123"
    
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "email": email, 
        "password": password
    })

    if res.status_code != 200:
        print(f"❌ Login failed: {res.status_code}")
        # Try registering if login fails (fallback)
        res = requests.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password,
            "name": "New Admin"
        })
        if res.status_code != 200 and "already registered" not in res.text:
             print(f"❌ Registration failed: {res.status_code}")
             return
        # Login again if registered
        res = requests.post(f"{BASE_URL}/auth/login", json={
            "email": email, 
            "password": password
        })

    if res.status_code != 200:
         print("❌ Could not get token.")
         return

    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Test Assigned Endpoint
    print("   Fetching assigned tickets...")
    try:
        assign_res = requests.get(f"{BASE_URL}/admin/tickets/assigned", headers=headers)
        if assign_res.status_code == 200:
            print("✅ SUCCESS: Endpoint returned 200 OK")
            print("   Data:", assign_res.json())
        else:
            print(f"❌ FAILURE: Status {assign_res.status_code}")
            print("   Error:", assign_res.text)
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    verify_assigned()
