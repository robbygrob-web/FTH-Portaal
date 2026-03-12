"""
Database migratie 004: notities en adresvelden
Voegt kolommen toe aan orders en contacten tabellen.
"""
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

def run_migration_004():
    """Voer migratie 004 uit: notities en adresvelden"""
    # Laad .env bestand
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Haal DATABASE_URL op
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[MIGRATION 004] ERROR: DATABASE_URL niet gevonden")
        return False
    
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("[MIGRATION 004] Start migratie: notities en adresvelden")
        
        # Orders: notitievelden
        print("[MIGRATION 004] Voeg notitie_klant toe aan orders...")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS notitie_klant TEXT;")
        conn.commit()
        print("[MIGRATION 004] ✓ notitie_klant toegevoegd aan orders")
        
        print("[MIGRATION 004] Voeg notitie_partner toe aan orders...")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS notitie_partner TEXT;")
        conn.commit()
        print("[MIGRATION 004] ✓ notitie_partner toegevoegd aan orders")
        
        # Contacten: adresvelden
        print("[MIGRATION 004] Voeg adres toe aan contacten...")
        cur.execute("ALTER TABLE contacten ADD COLUMN IF NOT EXISTS adres TEXT;")
        conn.commit()
        print("[MIGRATION 004] ✓ adres toegevoegd aan contacten")
        
        print("[MIGRATION 004] Voeg postcode toe aan contacten...")
        cur.execute("ALTER TABLE contacten ADD COLUMN IF NOT EXISTS postcode VARCHAR(20);")
        conn.commit()
        print("[MIGRATION 004] ✓ postcode toegevoegd aan contacten")
        
        print("[MIGRATION 004] Voeg land toe aan contacten...")
        cur.execute("ALTER TABLE contacten ADD COLUMN IF NOT EXISTS land VARCHAR(100);")
        conn.commit()
        print("[MIGRATION 004] ✓ land toegevoegd aan contacten")
        
        # Mail_logs: foutmelding kolom
        print("[MIGRATION 004] Voeg foutmelding toe aan mail_logs...")
        cur.execute("ALTER TABLE mail_logs ADD COLUMN IF NOT EXISTS foutmelding TEXT;")
        conn.commit()
        print("[MIGRATION 004] ✓ foutmelding toegevoegd aan mail_logs")
        
        # Orders: prijs_partner kolom
        print("[MIGRATION 004] Voeg prijs_partner toe aan orders...")
        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS prijs_partner NUMERIC(10,2);")
        conn.commit()
        print("[MIGRATION 004] ✓ prijs_partner toegevoegd aan orders")
        
        # Artikelen: seed data
        print("[MIGRATION 004] Voeg UNIQUE constraint toe aan artikelen.naam...")
        try:
            cur.execute("ALTER TABLE artikelen ADD CONSTRAINT artikelen_naam_unique UNIQUE (naam);")
            conn.commit()
            print("[MIGRATION 004] ✓ UNIQUE constraint toegevoegd aan artikelen.naam")
        except psycopg2.ProgrammingError as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                print("[MIGRATION 004] UNIQUE constraint bestaat al, overslaan...")
                conn.rollback()
            else:
                raise
        
        print("[MIGRATION 004] Maak odoo_id nullable in artikelen...")
        try:
            cur.execute("ALTER TABLE artikelen ALTER COLUMN odoo_id DROP NOT NULL;")
            conn.commit()
            print("[MIGRATION 004] ✓ odoo_id is nu nullable")
        except psycopg2.ProgrammingError as e:
            print(f"[MIGRATION 004] Opmerking bij odoo_id wijziging: {e}")
            conn.rollback()
        
        # Verwijder kolommen uit artikelen tabel
        print("[MIGRATION 004] Verwijder prijs_excl, btw_pct, btw_bedrag uit artikelen...")
        try:
            cur.execute("ALTER TABLE artikelen DROP COLUMN IF EXISTS prijs_excl;")
            conn.commit()
            print("[MIGRATION 004] ✓ prijs_excl verwijderd")
        except psycopg2.ProgrammingError as e:
            print(f"[MIGRATION 004] Opmerking bij verwijderen prijs_excl: {e}")
            conn.rollback()
        
        try:
            cur.execute("ALTER TABLE artikelen DROP COLUMN IF EXISTS btw_pct;")
            conn.commit()
            print("[MIGRATION 004] ✓ btw_pct verwijderd")
        except psycopg2.ProgrammingError as e:
            print(f"[MIGRATION 004] Opmerking bij verwijderen btw_pct: {e}")
            conn.rollback()
        
        try:
            cur.execute("ALTER TABLE artikelen DROP COLUMN IF EXISTS btw_bedrag;")
            conn.commit()
            print("[MIGRATION 004] ✓ btw_bedrag verwijderd")
        except psycopg2.ProgrammingError as e:
            print(f"[MIGRATION 004] Opmerking bij verwijderen btw_bedrag: {e}")
            conn.rollback()
        
        print("[MIGRATION 004] Seed artikelen...")
        cur.execute("""
            INSERT INTO artikelen (naam, prijs_incl, odoo_id, actief)
            VALUES
              ('Frietpakket', 5.00, NULL, true),
              ('Verse Friet & Snack', 7.50, NULL, true),
              ('Verse Friet & Snacks (onbeperkt)', 10.50, NULL, true),
              ('Verse Friet, Snacks & Burger (onbeperkt)', 11.75, NULL, true),
              ('Broodjes', 1.00, NULL, true),
              ('Drankjes', 3.00, NULL, true),
              ('Reiskosten', 75.00, NULL, true)
            ON CONFLICT (naam) DO NOTHING;
        """)
        conn.commit()
        print("[MIGRATION 004] ✓ artikelen geseed")
        
        # Verwijder kolommen uit order_artikelen tabel
        print("[MIGRATION 004] Verwijder prijs_excl, btw_pct, btw_bedrag uit order_artikelen...")
        try:
            cur.execute("ALTER TABLE order_artikelen DROP COLUMN IF EXISTS prijs_excl;")
            conn.commit()
            print("[MIGRATION 004] ✓ prijs_excl verwijderd uit order_artikelen")
        except psycopg2.ProgrammingError as e:
            print(f"[MIGRATION 004] Opmerking bij verwijderen prijs_excl uit order_artikelen: {e}")
            conn.rollback()
        
        try:
            cur.execute("ALTER TABLE order_artikelen DROP COLUMN IF EXISTS btw_pct;")
            conn.commit()
            print("[MIGRATION 004] ✓ btw_pct verwijderd uit order_artikelen")
        except psycopg2.ProgrammingError as e:
            print(f"[MIGRATION 004] Opmerking bij verwijderen btw_pct uit order_artikelen: {e}")
            conn.rollback()
        
        try:
            cur.execute("ALTER TABLE order_artikelen DROP COLUMN IF EXISTS btw_bedrag;")
            conn.commit()
            print("[MIGRATION 004] ✓ btw_bedrag verwijderd uit order_artikelen")
        except psycopg2.ProgrammingError as e:
            print(f"[MIGRATION 004] Opmerking bij verwijderen btw_bedrag uit order_artikelen: {e}")
            conn.rollback()
        
        print("[MIGRATION 004] Migratie voltooid!")
        return True
        
    except Exception as e:
        print(f"[MIGRATION 004] ERROR: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    run_migration_004()
