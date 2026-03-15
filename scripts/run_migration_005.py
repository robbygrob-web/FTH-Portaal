"""
Database migratie 005: Enrich mail_logs met ontvanger_id
Vult ontvanger_id in voor bestaande mail_logs records door email matching.
"""
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

def run_migration_005():
    """Voer migratie 005 uit: enrich mail_logs met ontvanger_id"""
    # Laad .env bestand
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Haal DATABASE_URL op
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[MIGRATION 005] ERROR: DATABASE_URL niet gevonden")
        return False
    
    # Als interne URL, vervang met publieke URL voor lokaal gebruik
    if "railway.internal" in database_url:
        print("[MIGRATION 005] Vervang interne URL met publieke URL voor lokaal gebruik...")
        database_url = database_url.replace(
            "postgres.railway.internal:5432",
            "metro.proxy.rlwy.net:18535"
        )
        # Vervang *** met echte password (tijdelijk voor lokaal gebruik)
        if "***" in database_url:
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
    
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("[MIGRATION 005] Start enrichment mail_logs met ontvanger_id...")
        
        # Uitgaande mails: match via mail_logs.naar
        print("[MIGRATION 005] Update uitgaande mails (match via naar)...")
        cur.execute("""
            UPDATE mail_logs ml
            SET ontvanger_id = c.id
            FROM contacten c
            WHERE ml.naar = c.email
              AND ml.ontvanger_id IS NULL
              AND ml.richting = 'uitgaand'
        """)
        rows_uitgaand = cur.rowcount
        conn.commit()
        print(f"[MIGRATION 005] ✓ Uitgaande mails: {rows_uitgaand} rijen geüpdatet")
        
        # Inkomende mails: match via mail_logs.email_van
        print("[MIGRATION 005] Update inkomende mails (match via email_van)...")
        cur.execute("""
            UPDATE mail_logs ml
            SET ontvanger_id = c.id
            FROM contacten c
            WHERE ml.email_van = c.email
              AND ml.ontvanger_id IS NULL
              AND ml.richting = 'inkomend'
        """)
        rows_inkomend = cur.rowcount
        conn.commit()
        print(f"[MIGRATION 005] ✓ Inkomende mails: {rows_inkomend} rijen geüpdatet")
        
        print(f"[MIGRATION 005] Totaal: {rows_uitgaand + rows_inkomend} rijen geüpdatet")
        print("[MIGRATION 005] Migratie voltooid!")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"[MIGRATION 005] ERROR: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    run_migration_005()
