
import requests

def verify_stats():
    try:
        res = requests.get("http://localhost:8000/stats")
        print(f"Status Code: {res.status_code}")
        if res.status_code == 200:
            print("Response:", res.json())
            print("✅ Stats endpoint working.")
        else:
            print("❌ Stats endpoint failed:", res.text)
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    verify_stats()
