"""
Database migratie 006: Annuleer token veld
Voegt annuleer_token kolom toe aan orders tabel.
"""
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

def run_migration_006():
    """Voer migratie 006 uit: annuleer token veld"""
    # Laad .env bestand
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Haal DATABASE_URL op
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[MIGRATION 006] ERROR: DATABASE_URL niet gevonden")
        return False
    
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("[MIGRATION 006] Start migratie: annuleer token veld")
        
        # Orders: annuleer_token
        print("[MIGRATION 006] Voeg annuleer_token toe aan orders...")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS annuleer_token UUID;")
        conn.commit()
        print("[MIGRATION 006] ✓ annuleer_token toegevoegd aan orders")
        
        print("[MIGRATION 006] Migratie voltooid!")
        return True
        
    except Exception as e:
        print(f"[MIGRATION 006] ERROR: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    run_migration_006()
