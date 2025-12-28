
import os
import psycopg2
import sys

# URL Encoded Password
DATABASE_URL = "postgres://postgres:Kannan%40123@db.xalhhtxwtrhdxrmrvqgo.supabase.co:5432/postgres"

def make_super_admin(email):
    print(f"🔌 Connecting to database...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    print(f"🔍 Looking for user: {email}")
    cur.execute("SELECT id, role, name FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    
    if not user:
        print(f"❌ User not found! Please register as a customer first.")
        return

    user_id, current_role, name = user
    print(f"   Found user: {name} (Current Role: {current_role})")

    if current_role == 'super_admin':
        print(f"✅ User is already a Super Admin.")
        return

    print(f"🚀 Promoting to Super Admin...")
    try:
        cur.execute("UPDATE users SET role = 'super_admin' WHERE id = %s", (user_id,))
        print(f"✅ Success! {email} is now a Super Admin.")
    except Exception as e:
        print(f"❌ Failed to update role: {e}")

    conn.close()

if __name__ == "__main__":
    target_email = "kannankhosla2405@gmail.com"
    if len(sys.argv) > 1:
        target_email = sys.argv[1]
    
    make_super_admin(target_email)
