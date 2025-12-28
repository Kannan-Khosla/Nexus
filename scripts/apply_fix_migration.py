
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("❌ DATABASE_URL not found in .env")
    exit(1)

def apply_migration():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        with open("migrations/015_fix_missing_columns_and_view.sql", "r") as f:
            sql = f.read()
            print("Applying migration 015...")
            cur.execute(sql)
            conn.commit()
            print("✅ Migration applied successfully.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error applying migration: {e}")

if __name__ == "__main__":
    apply_migration()
