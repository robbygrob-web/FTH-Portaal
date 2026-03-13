"""
Script om de laatste order te bekijken met bedragen en UTM velden.
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
    print("LAATSTE ORDER")
    print("=" * 80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Voer query uit
        cur.execute("""
            SELECT ordernummer, totaal_bedrag, bedrag_excl_btw, bedrag_btw, utm_source, utm_content 
            FROM orders 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        order = cur.fetchone()
        
        if order:
            print(f"\nOrdernummer: {order['ordernummer']}")
            print(f"\nBedragen:")
            print(f"  totaal_bedrag: €{order['totaal_bedrag']:.2f}")
            print(f"  bedrag_excl_btw: €{order['bedrag_excl_btw']:.2f}")
            print(f"  bedrag_btw: €{order['bedrag_btw']:.2f}")
            print(f"\nUTM velden:")
            print(f"  utm_source: {order['utm_source']}")
            print(f"  utm_content: {order['utm_content']}")
        else:
            print("\nGeen orders gevonden.")
        
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
