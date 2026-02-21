import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def migrate():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        return

    # Fix for postgres:// vs postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        print("Checking for plain_password column...")
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='user' AND column_name='plain_password';")
        column_exists = cur.fetchone()
        
        if not column_exists:
            print("Adding plain_password column to user table...")
            cur.execute("ALTER TABLE \"user\" ADD COLUMN plain_password VARCHAR(200);")
            conn.commit()
            print("Migration successful!")
        else:
            print("Column plain_password already exists.")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
