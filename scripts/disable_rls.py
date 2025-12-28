
import os
import psycopg2
from urllib.parse import urlparse

# URL Encoded Password
DATABASE_URL = "postgres://postgres:Kannan%40123@db.xalhhtxwtrhdxrmrvqgo.supabase.co:5432/postgres"

def disable_rls_and_fix_perms():
    print("🔌 Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    print("🛡️  Disabling Row Level Security (RLS) on all tables...")
    try:
        # Get all table names
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        for table in tables:
            print(f"   Disabling RLS on {table}...")
            # Disable RLS
            cur.execute(f'ALTER TABLE "public"."{table}" DISABLE ROW LEVEL SECURITY;')
            # Explicitly grant privileges again to be sure
            cur.execute(f'GRANT ALL ON "public"."{table}" TO anon;')
            cur.execute(f'GRANT ALL ON "public"."{table}" TO authenticated;')
            cur.execute(f'GRANT ALL ON "public"."{table}" TO service_role;')
            
    except Exception as e:
        print(f"❌ Failed to disable RLS: {e}")
        return

    print("✅ RLS Disabled & Permissions Fixed!")
    conn.close()

if __name__ == "__main__":
    disable_rls_and_fix_perms()
