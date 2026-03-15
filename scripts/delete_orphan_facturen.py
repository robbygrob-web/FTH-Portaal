"""
Script om factuur records zonder order_id te verwijderen.
Dit zijn testrecords zonder koppeling aan een order.

Gebruik:
  python scripts/delete_orphan_facturen.py
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


def delete_orphan_facturen():
    """Verwijder factuur records zonder order_id"""
    print("="*80)
    print("VERWIJDER ORPHAN FACTUREN")
    print("="*80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Haal records op die verwijderd gaan worden
        print("\n[1/3] Zoeken naar facturen zonder order_id...")
        cur.execute("""
            SELECT 
                id,
                factuurnummer,
                factuurdatum,
                betalingsstatus,
                totaal_bedrag
            FROM facturen
            WHERE order_id IS NULL
            ORDER BY factuurdatum DESC
        """)
        
        orphan_records = cur.fetchall()
        
        if not orphan_records:
            print("   [OK] Geen orphan facturen gevonden - niets te verwijderen")
            cur.close()
            conn.close()
            print("\n" + "="*80)
            print("KLAAR - Geen wijzigingen nodig")
            print("="*80)
            return
        
        # Print records die verwijderd gaan worden
        print(f"\n[INFO] Gevonden {len(orphan_records)} factuur record(s) zonder order_id:")
        print(f"\n{'ID':<40} {'Factuurnummer':<20} {'Datum':<12} {'Status':<15} {'Bedrag'}")
        print("-" * 100)
        
        for record in orphan_records:
            r_id, r_nummer, r_datum, r_status, r_bedrag = record
            r_datum_str = str(r_datum) if r_datum else 'NULL'
            r_status_str = str(r_status) if r_status else 'NULL'
            print(f"{str(r_id):<40} {str(r_nummer):<20} {r_datum_str:<12} {r_status_str:<15} {str(r_bedrag)}")
        
        # Vraag bevestiging
        print("\n[2/3] Bevestiging vereist")
        print("="*80)
        
        # Check voor --confirm flag voor niet-interactief gebruik
        if '--confirm' in sys.argv:
            response = 'JA'
            print("\n[INFO] --confirm flag gebruikt, verwijderen wordt uitgevoerd")
        else:
            try:
                response = input("\nTyp 'JA' om deze records te verwijderen: ")
            except EOFError:
                print("\n[FOUT] Geen interactieve input beschikbaar")
                print("       Gebruik 'python scripts/delete_orphan_facturen.py --confirm' voor niet-interactief gebruik")
                cur.close()
                conn.close()
                return
        
        if response != 'JA':
            print("\n[INFO] Verwijderen geannuleerd")
            cur.close()
            conn.close()
            return
        
        # Verwijder records
        print("\n[3/3] Verwijderen records...")
        cur.execute("""
            DELETE FROM facturen
            WHERE order_id IS NULL
        """)
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"   [OK] {deleted_count} factuur record(s) verwijderd")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("SUCCES: Orphan facturen verwijderd")
        print("="*80)
        
    except Exception as e:
        print(f"\n[FOUT] Verwijderen gefaald: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.rollback()
        sys.exit(1)


if __name__ == "__main__":
    delete_orphan_facturen()
