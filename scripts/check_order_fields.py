"""
Script om te controleren welke velden prijzen bevatten in bestaande orders.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad omgevingsvariabelen
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    
    # Als interne URL, vervang met publieke URL voor lokaal gebruik
    if "railway.internal" in database_url:
        database_url = database_url.replace(
            "postgres.railway.internal:5432",
            "metro.proxy.rlwy.net:18535"
        )
        if "***" in database_url:
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
    
    return database_url

def main():
    """Hoofdfunctie"""
    print("=" * 80)
    print("BESTAANDE ORDERS ANALYSEREN")
    print("=" * 80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal laatste 3 orders op met alle velden
        cur.execute("""
            SELECT ordernummer, totaal_bedrag, bedrag_excl_btw, bedrag_btw,
                   utm_source, utm_medium, utm_campaign, utm_content,
                   aantal_personen, plaats
            FROM orders
            ORDER BY created_at DESC
            LIMIT 3
        """)
        
        orders = cur.fetchall()
        
        print(f"\nTotaal orders gevonden: {len(orders)}\n")
        
        for idx, order in enumerate(orders, 1):
            print(f"--- ORDER {idx} ---")
            print(f"Ordernummer: {order['ordernummer']}")
            print(f"Plaats: {order['plaats']}")
            print(f"Aantal personen: {order['aantal_personen']}")
            print(f"\nBedragen:")
            print(f"  totaal_bedrag: €{order['totaal_bedrag']}")
            print(f"  bedrag_excl_btw: €{order['bedrag_excl_btw']}")
            print(f"  bedrag_btw: €{order['bedrag_btw']}")
            print(f"\nUTM velden:")
            print(f"  utm_source: {order['utm_source']}")
            print(f"  utm_medium: {order['utm_medium']}")
            print(f"  utm_campaign: {order['utm_campaign']}")
            print(f"  utm_content: {order['utm_content']}")
            print()
        
        print("=" * 80)
        print("ANALYSE")
        print("=" * 80)
        print("\nProbleem geïdentificeerd:")
        print("  - utm_source en utm_content bevatten prijsdata (bijv. 547.5, 390, 432)")
        print("  - Bedragen kolommen staan allemaal op 0.00")
        print("\nOplossing:")
        print("  - Veld '7' en '10' bevatten prijzen, niet UTM data")
        print("  - Deze moeten gemapt worden naar bedragen kolommen")
        print("  - UTM data moet uit andere velden komen (utm_source, utm_medium, etc.)")
        print("=" * 80 + "\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
