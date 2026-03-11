"""
Script om alle artikelen te tonen met alle velden.
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
    print("ARTIKELEN IN DATABASE")
    print("=" * 80)
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM artikelen ORDER BY naam
        """)
        
        artikelen = cur.fetchall()
        
        print(f"\nTotaal artikelen: {len(artikelen)}\n")
        
        for idx, artikel in enumerate(artikelen, 1):
            print(f"--- ARTIKEL {idx} ---")
            print("-" * 80)
            for key, value in artikel.items():
                if value is not None:
                    if isinstance(value, list):
                        value_str = str(value)
                    else:
                        value_str = str(value)
                    
                    if len(value_str) > 60:
                        value_str = value_str[:57] + "..."
                    
                    print(f"  {key:<30} = {value_str}")
            print()
        
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
