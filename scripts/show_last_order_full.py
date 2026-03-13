"""
Script om alle velden van de laatste order te tonen.
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
    print("LAATSTE ORDER - ALLE VELDEN")
    print("=" * 80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Voer query uit om alle velden op te halen
        cur.execute("""
            SELECT o.*, c.naam as klant_naam, c.email as klant_email
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            ORDER BY o.created_at DESC 
            LIMIT 1
        """)
        
        order = cur.fetchone()
        
        if order:
            print(f"\n--- ORDER DETAILS ---")
            print("-" * 80)
            
            # Toon alle velden
            for key, value in order.items():
                if value is not None:
                    # Format waarde voor leesbaarheid
                    if isinstance(value, str) and len(value) > 100:
                        value_str = value[:100] + "..."
                    else:
                        value_str = str(value)
                    
                    print(f"  {key:<30} = {value_str}")
                else:
                    print(f"  {key:<30} = NULL")
        else:
            print("\nGeen orders gevonden.")
        
        print("\n" + "=" * 80 + "\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
