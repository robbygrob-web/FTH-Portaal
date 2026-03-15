"""
Cleanup migratie 001:
1. Verwijder ongebruikte kolom klant_notitie van orders tabel
2. Voeg foreign key constraint toe aan betalingen.order_id

Gebruik:
  python scripts/migrate_cleanup_001.py
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

# Laad omgevingsvariabelen
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    
    # Als interne URL, vervang met publieke URL voor lokaal gebruik
    if "railway.internal" in database_url:
        print("[INFO] Vervang interne URL met publieke URL voor lokaal gebruik...")
        database_url = database_url.replace(
            "postgres.railway.internal:5432",
            "metro.proxy.rlwy.net:18535"
        )
        # Vervang *** met echte password (tijdelijk voor lokaal gebruik)
        if "***" in database_url:
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
    
    return database_url


def drop_klant_notitie():
    """Verwijder ongebruikte kolom klant_notitie van orders tabel"""
    print("\n" + "="*80)
    print("[1/2] Verwijder ongebruikte kolom klant_notitie")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Check of kolom bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders' AND column_name = 'klant_notitie'
        """)
        
        if not cur.fetchone():
            print("\n[INFO] Kolom 'klant_notitie' bestaat niet in orders tabel")
            cur.close()
            conn.close()
            return
        
        # Drop kolom
        cur.execute("""
            ALTER TABLE orders DROP COLUMN IF EXISTS klant_notitie
        """)
        
        conn.commit()
        print("\n[OK] Kolom 'klant_notitie' verwijderd uit orders tabel")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FOUT] Verwijderen kolom gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def add_betalingen_order_fk():
    """Voeg foreign key constraint toe aan betalingen.order_id"""
    print("\n" + "="*80)
    print("[2/2] Voeg FK constraint toe aan betalingen.order_id")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Check of constraint al bestaat
        cur.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'betalingen'
            AND constraint_name = 'fk_betalingen_order_id'
        """)
        
        if cur.fetchone():
            print("\n[INFO] Foreign key constraint 'fk_betalingen_order_id' bestaat al")
            cur.close()
            conn.close()
            return
        
        # Check of order_id kolom bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'betalingen' AND column_name = 'order_id'
        """)
        
        if not cur.fetchone():
            print("\n[FOUT] Kolom 'order_id' bestaat niet in betalingen tabel")
            cur.close()
            conn.close()
            sys.exit(1)
        
        # Voeg FK constraint toe
        cur.execute("""
            ALTER TABLE betalingen
            ADD CONSTRAINT fk_betalingen_order_id
            FOREIGN KEY (order_id) REFERENCES orders(id)
        """)
        
        conn.commit()
        print("\n[OK] Foreign key constraint 'fk_betalingen_order_id' toegevoegd")
        
        # Verifieer
        cur.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'betalingen'
            AND constraint_name = 'fk_betalingen_order_id'
        """)
        constraint = cur.fetchone()
        
        if constraint:
            print(f"[INFO] Constraint geverifieerd: {constraint[0]} ({constraint[1]})")
        
        cur.close()
        conn.close()
        
    except psycopg2.IntegrityError as e:
        print(f"\n[FOUT] Foreign key constraint toevoegen gefaald: {e}")
        print("       Mogelijk zijn er bestaande records die de constraint schenden")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"\n[FOUT] Foreign key constraint toevoegen gefaald: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        sys.exit(1)


def main():
    """Hoofdfunctie"""
    print("="*80)
    print("CLEANUP MIGRATIE 001")
    print("="*80)
    print("\nDoel:")
    print("  1. Verwijder ongebruikte kolom klant_notitie van orders")
    print("  2. Voeg FK constraint toe aan betalingen.order_id")
    
    drop_klant_notitie()
    add_betalingen_order_fk()
    
    print("\n" + "="*80)
    print("SUCCES: Cleanup migratie voltooid")
    print("="*80)


if __name__ == "__main__":
    main()
