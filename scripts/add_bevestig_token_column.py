"""
Script om bevestig_token kolom toe te voegen aan orders tabel.
"""
import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

def add_bevestig_token_column():
    """Voeg bevestig_token kolom toe aan orders tabel"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL niet gevonden in environment variabelen")
        sys.exit(1)
    
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check of kolom al bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders' AND column_name = 'bevestig_token'
        """)
        
        if cur.fetchone():
            print("✓ Kolom bevestig_token bestaat al")
            return
        
        # Voeg kolom toe
        cur.execute("""
            ALTER TABLE orders
            ADD COLUMN bevestig_token VARCHAR(64) UNIQUE
        """)
        
        conn.commit()
        print("✓ Kolom bevestig_token succesvol toegevoegd aan orders tabel")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    add_bevestig_token_column()
