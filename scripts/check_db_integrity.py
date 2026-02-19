
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("❌ Missing Supabase credentials")
    exit(1)

client = create_client(url, key)

tables_to_check = ["users", "tickets", "email_accounts", "email_messages"]

print("🔍 Checking database content...")

for table in tables_to_check:
    try:
        # Get count of rows
        response = client.table(table).select("id", count="exact").limit(0).execute()
        count = response.count
        print(f"✅ Table '{table}' exists. Rows: {count}")
    except Exception as e:
        print(f"❌ Table '{table}' check failed: {e}")
