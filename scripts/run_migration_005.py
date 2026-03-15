"""
Database migratie 005: Planning email systeem velden
Voegt kolommen toe aan orders tabel voor planning email functionaliteit.
"""
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

def run_migration_005():
    """Voer migratie 005 uit: planning email systeem velden"""
    # Laad .env bestand
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Haal DATABASE_URL op
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[MIGRATION 005] ERROR: DATABASE_URL niet gevonden")
        return False
    
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("[MIGRATION 005] Start migratie: planning email systeem velden")
        
        # Orders: planning_afgemeld
        print("[MIGRATION 005] Voeg planning_afgemeld toe aan orders...")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS planning_afgemeld BOOLEAN DEFAULT FALSE;")
        conn.commit()
        print("[MIGRATION 005] ✓ planning_afgemeld toegevoegd aan orders")
        
        # Orders: planning_afmeld_token
        print("[MIGRATION 005] Voeg planning_afmeld_token toe aan orders...")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS planning_afmeld_token UUID;")
        conn.commit()
        print("[MIGRATION 005] ✓ planning_afmeld_token toegevoegd aan orders")
        
        print("[MIGRATION 005] Migratie voltooid!")
        return True
        
    except Exception as e:
        print(f"[MIGRATION 005] ERROR: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    run_migration_005()
