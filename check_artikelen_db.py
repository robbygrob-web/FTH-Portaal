"""
Script om actieve artikelen uit de database te halen.
Voer uit: python check_artikelen_db.py
"""
import os
import sys
from pathlib import Path

# Voeg project root toe aan path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Laad environment variabelen
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL niet gevonden in environment variabelen")
        print("Zorg dat .env bestand bestaat met DATABASE_URL")
        return
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT naam FROM artikelen WHERE actief = TRUE ORDER BY naam")
        artikelen = cur.fetchall()
        
        print("=" * 60)
        print("ACTIEVE ARTIKELEN IN DATABASE:")
        print("=" * 60)
        
        if not artikelen:
            print("Geen actieve artikelen gevonden.")
        else:
            for i, artikel in enumerate(artikelen, 1):
                naam = artikel["naam"]
                print(f"{i:2d}. \"{naam}\"")
        
        print("=" * 60)
        print(f"\nTotaal: {len(artikelen)} actieve artikelen")
        print("\nGravity Forms stuurt: \"Puntzak Verse Friet & Snack\"")
        print("\nVergelijk de namen hierboven met wat Gravity Forms stuurt.")
        
        cur.close()
        conn.close()
        
    except psycopg2.OperationalError as e:
        print(f"ERROR: Kon niet verbinden met database: {e}")
        print("\nMogelijke oorzaken:")
        print("- DATABASE_URL is niet correct geconfigureerd")
        print("- Database is niet bereikbaar (Railway internal URL werkt alleen in Railway)")
        print("\nTip: Gebruik DATABASE_PUBLIC_URL voor lokale toegang")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
