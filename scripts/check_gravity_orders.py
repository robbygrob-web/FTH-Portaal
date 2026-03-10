"""
Script om te controleren of Gravity Forms orders zijn binnengekomen.
Toont laatste 3 orders en contacten uit de database.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Laad omgevingsvariabelen
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def format_value(value):
    """Format waarde voor weergave"""
    if value is None:
        return "NULL"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def check_gravity_orders():
    """Controleer laatste orders en contacten"""
    print("="*80)
    print("Gravity Forms Orders Check")
    print("="*80)
    
    try:
        # Gebruik publieke Railway URL tijdelijk
        database_url = get_database_url()
        
        # Als interne URL, vervang met publieke URL
        if "railway.internal" in database_url:
            print("\n[INFO] Vervang interne URL met publieke URL...")
            database_url = database_url.replace(
                "postgres.railway.internal:5432",
                "metro.proxy.rlwy.net:18535"
            )
            # Vervang *** met echte password
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
        
        print(f"\n[1/4] Verbinden met database...")
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("   [OK] Verbonden")
        
        # Haal laatste 3 orders op
        print("\n[2/4] Ophalen laatste 3 orders...")
        cur.execute("""
            SELECT * FROM orders 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        orders = cur.fetchall()
        print(f"   [OK] {len(orders)} order(s) gevonden")
        
        # Haal laatste 3 contacten op
        print("\n[3/4] Ophalen laatste 3 contacten...")
        cur.execute("""
            SELECT * FROM contacten 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        contacten = cur.fetchall()
        print(f"   [OK] {len(contacten)} contact(en) gevonden")
        
        # Toon orders
        print("\n" + "="*80)
        print("LAATSTE 3 ORDERS")
        print("="*80)
        
        if not orders:
            print("\nGeen orders gevonden.")
        else:
            for idx, order in enumerate(orders, 1):
                print(f"\n--- ORDER {idx} ---")
                order_dict = dict(order)
                for key, value in order_dict.items():
                    if value is not None and value != "" and value != 0:
                        print(f"  {key:30} = {format_value(value)}")
        
        # Toon contacten
        print("\n" + "="*80)
        print("LAATSTE 3 CONTACTEN")
        print("="*80)
        
        if not contacten:
            print("\nGeen contacten gevonden.")
        else:
            for idx, contact in enumerate(contacten, 1):
                print(f"\n--- CONTACT {idx} ---")
                contact_dict = dict(contact)
                for key, value in contact_dict.items():
                    if value is not None and value != "" and value != 0:
                        print(f"  {key:30} = {format_value(value)}")
        
        # Zoek specifiek naar Gravity Forms orders (ordernummer begint met GF-)
        print("\n" + "="*80)
        print("GRAVITY FORMS ORDERS (ordernummer begint met 'GF-')")
        print("="*80)
        
        cur.execute("""
            SELECT * FROM orders 
            WHERE ordernummer LIKE 'GF-%'
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        gf_orders = cur.fetchall()
        
        if not gf_orders:
            print("\nGeen Gravity Forms orders gevonden.")
        else:
            print(f"\n{len(gf_orders)} Gravity Forms order(s) gevonden:")
            for idx, order in enumerate(gf_orders, 1):
                print(f"\n--- GF ORDER {idx} ---")
                order_dict = dict(order)
                for key, value in order_dict.items():
                    if value is not None and value != "" and value != 0:
                        print(f"  {key:30} = {format_value(value)}")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("Klaar!")
        print("="*80)
        
    except Exception as e:
        print(f"\n[FOUT] Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_gravity_orders()
