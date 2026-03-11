"""
Script om Reiskostenvergoeding bij te werken naar €75 incl 9% BTW.
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
    print("REISKOSTENVERGOEDING BIJWERKEN")
    print("=" * 80)
    
    # Bereken prijzen
    prijs_incl = 75.00
    btw_pct = 9.0
    prijs_excl = round(prijs_incl / (1 + btw_pct / 100), 2)
    btw_bedrag = round(prijs_excl * (btw_pct / 100), 2)
    
    print(f"\nNieuwe waarden:")
    print(f"  Prijs incl: €{prijs_incl:.2f}")
    print(f"  BTW ({btw_pct}%): €{btw_bedrag:.2f}")
    print(f"  Prijs excl: €{prijs_excl:.2f}")
    
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Update Reiskostenvergoeding (odoo_id = 8)
        update_sql = """
        UPDATE artikelen
        SET prijs_excl = %s,
            btw_pct = %s,
            btw_bedrag = %s,
            prijs_incl = %s
        WHERE odoo_id = 8
        RETURNING id, naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl
        """
        
        cur.execute(update_sql, (prijs_excl, btw_pct, btw_bedrag, prijs_incl))
        result = cur.fetchone()
        
        if result:
            conn.commit()
            print(f"\n[OK] Reiskostenvergoeding bijgewerkt:")
            print(f"  Naam: {result['naam']}")
            print(f"  Prijs excl: €{result['prijs_excl']:.2f}")
            print(f"  BTW ({result['btw_pct']}%): €{result['btw_bedrag']:.2f}")
            print(f"  Prijs incl: €{result['prijs_incl']:.2f}")
        else:
            print("\n[WAARSCHUWING] Geen record gevonden met odoo_id = 8")
        
        # Toon alle artikelen
        print("\n" + "=" * 80)
        print("ALLE ARTIKELEN")
        print("=" * 80)
        
        cur.execute("""
            SELECT naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl
            FROM artikelen
            ORDER BY naam
        """)
        all_products = cur.fetchall()
        
        print(f"\n{'Naam':<45} {'Prijs excl':<12} {'BTW %':<8} {'BTW bedrag':<12} {'Prijs incl':<12}")
        print("-" * 80)
        for prod in all_products:
            print(f"{prod['naam']:<45} €{prod['prijs_excl']:>9.2f}  {prod['btw_pct']:>5.2f}%  €{prod['btw_bedrag']:>9.2f}  €{prod['prijs_incl']:>9.2f}")
        
        print("=" * 80 + "\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[ERROR] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
