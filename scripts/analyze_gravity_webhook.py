"""
Script om te analyseren wat er binnenkomt via Gravity Forms webhook
en wat er wordt opgeslagen in de orders tabel.
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad .env bestand
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    # Gebruik publieke URL voor lokale uitvoering
    database_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def analyze_orders_table():
    """Analyseer de orders tabel structuur"""
    print("=" * 80)
    print("1. ORDERS TABEL STRUCTUUR")
    print("=" * 80)
    
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal kolommen op uit information_schema
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = 'orders'
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        
        print(f"\nTotaal aantal kolommen: {len(columns)}\n")
        print(f"{'Kolom':<30} {'Type':<25} {'Nullable':<10} {'Default'}")
        print("-" * 80)
        
        for col in columns:
            col_name = col['column_name']
            data_type = col['data_type']
            max_length = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
            nullable = col['is_nullable']
            default = str(col['column_default'])[:30] if col['column_default'] else ""
            
            print(f"{col_name:<30} {data_type}{max_length:<20} {nullable:<10} {default}")
        
        cur.close()
        return columns
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()


def get_recent_orders():
    """Haal de 3 meest recente orders op"""
    print("\n" + "=" * 80)
    print("2. 3 MEEST RECENTE ORDERS")
    print("=" * 80)
    
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal 3 meest recente orders op
        cur.execute("""
            SELECT *
            FROM orders
            ORDER BY created_at DESC
            LIMIT 3
        """)
        
        orders = cur.fetchall()
        
        print(f"\nTotaal aantal orders gevonden: {len(orders)}\n")
        
        for idx, order in enumerate(orders, 1):
            print(f"\n--- ORDER {idx} ---")
            print(f"ID: {order['id']}")
            print(f"Ordernummer: {order.get('ordernummer', 'N/A')}")
            print(f"Created at: {order.get('created_at', 'N/A')}")
            print(f"\nAlle velden:")
            print("-" * 80)
            
            # Toon alle velden met waarden
            for key, value in order.items():
                if value is not None:
                    # Format waarde voor leesbaarheid
                    if isinstance(value, str) and len(value) > 100:
                        value_str = value[:100] + "..."
                    else:
                        value_str = str(value)
                    print(f"  {key:<30} = {value_str}")
            
            print()
        
        cur.close()
        return orders
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()


def analyze_webhook_fields():
    """Analyseer welke velden uit Gravity Forms worden opgeslagen"""
    print("\n" + "=" * 80)
    print("3. GRAVITY FORMS WEBHOOK VELD MAPPING")
    print("=" * 80)
    
    print("\nVelden die worden opgehaald uit Gravity Forms payload:")
    print("-" * 80)
    
    fields_mapping = {
        "Email": "veld '21' -> contacten.email",
        "Telefoon": "veld '24' -> contacten.telefoon",
        "Naam": "veld '1.3' (voornaam) + '1.6' (achternaam) -> contacten.naam",
        "Datum": "veld '48' -> orders.leverdatum",
        "Locatie": "veld '29.3' (stad) -> orders.plaats",
        "Aantal personen": "veld '68' -> orders.aantal_personen",
        "Aantal kinderen": "veld 'aantal_kinderen' -> orders.aantal_kinderen",
        "Opmerkingen": "veld 'opmerkingen' -> orders.opmerkingen",
        "UTM Source": "veld '7' of 'utm_source' -> orders.utm_source",
        "UTM Medium": "veld 'utm_medium' -> orders.utm_medium",
        "UTM Campaign": "veld 'utm_campaign' -> orders.utm_campaign",
        "UTM Content": "veld '10' of 'utm_content' -> orders.utm_content"
    }
    
    for field, mapping in fields_mapping.items():
        print(f"  {field:<25} -> {mapping}")
    
    print("\nVelden die worden opgeslagen in orders tabel:")
    print("-" * 80)
    
    saved_fields = [
        ("ordernummer", "Gegenereerd (GF-YYYYMMDD-HHMMSS-UUID)"),
        ("order_datum", "Huidige datum/tijd"),
        ("leverdatum", "Uit Gravity Forms veld '48'"),
        ("status", "Vast: 'draft'"),
        ("portaal_status", "Vast: 'nieuw'"),
        ("type_naam", "Vast: 'Aanvraag'"),
        ("klant_id", "UUID van aangemaakt/gevonden contact"),
        ("plaats", "Uit Gravity Forms veld '29.3'"),
        ("aantal_personen", "Uit Gravity Forms veld '68'"),
        ("aantal_kinderen", "Uit Gravity Forms veld 'aantal_kinderen'"),
        ("ordertype", "Vast: 'b2c'"),
        ("opmerkingen", "Uit Gravity Forms veld 'opmerkingen'"),
        ("utm_source", "Uit Gravity Forms veld '7' of 'utm_source'"),
        ("utm_medium", "Uit Gravity Forms veld 'utm_medium'"),
        ("utm_campaign", "Uit Gravity Forms veld 'utm_campaign'"),
        ("utm_content", "Uit Gravity Forms veld '10' of 'utm_content'"),
        ("totaal_bedrag", "Vast: 0.00 (nog niet berekend)"),
        ("bedrag_excl_btw", "Vast: 0.00 (nog niet berekend)"),
        ("bedrag_btw", "Vast: 0.00 (nog niet berekend)")
    ]
    
    for field, source in saved_fields:
        print(f"  {field:<30} <- {source}")


def check_missing_fields():
    """Controleer welke velden mogelijk ontbreken"""
    print("\n" + "=" * 80)
    print("4. ONTBREKENDE VELDEN ANALYSE")
    print("=" * 80)
    
    print("\nVelden die mogelijk ontbreken:")
    print("-" * 80)
    
    missing_fields = [
        {
            "veld": "Pakketprijs",
            "status": "[X] NIET OPGESLAGEN",
            "opmerking": "Geen pakket selectie veld in webhook handler gevonden"
        },
        {
            "veld": "Reiskosten",
            "status": "[X] NIET OPGESLAGEN",
            "opmerking": "Geen reiskosten veld in webhook handler gevonden"
        },
        {
            "veld": "Aantal personen",
            "status": "[OK] OPGESLAGEN",
            "opmerking": "Veld '68' wordt opgeslagen in orders.aantal_personen"
        },
        {
            "veld": "Aantal kinderen",
            "status": "[OK] OPGESLAGEN",
            "opmerking": "Veld 'aantal_kinderen' wordt opgeslagen in orders.aantal_kinderen"
        },
        {
            "veld": "Bedragen (totaal, excl BTW, BTW)",
            "status": "[!] VAST WAARDE",
            "opmerking": "Worden op 0.00 gezet - nog niet berekend"
        }
    ]
    
    for field_info in missing_fields:
        print(f"\n  {field_info['veld']}")
        print(f"    Status: {field_info['status']}")
        print(f"    Opmerking: {field_info['opmerking']}")


def main():
    """Hoofdfunctie"""
    print("\n" + "=" * 80)
    print("GRAVITY FORMS WEBHOOK ANALYSE")
    print("=" * 80)
    
    # 1. Analyseer tabel structuur
    columns = analyze_orders_table()
    
    # 2. Haal recente orders op
    orders = get_recent_orders()
    
    # 3. Analyseer webhook veld mapping
    analyze_webhook_fields()
    
    # 4. Controleer ontbrekende velden
    check_missing_fields()
    
    # Samenvatting
    print("\n" + "=" * 80)
    print("SAMENVATTING")
    print("=" * 80)
    print("\n[OK] Wat WEL wordt opgeslagen:")
    print("  - Contact gegevens (email, telefoon, naam)")
    print("  - Order basis info (datum, locatie, aantal personen/kinderen)")
    print("  - Opmerkingen")
    print("  - UTM tracking data")
    print("\n[X] Wat NIET wordt opgeslagen:")
    print("  - Pakketprijs (geen pakket selectie veld)")
    print("  - Reiskosten (geen reiskosten veld)")
    print("\n[!] Wat op 0.00 wordt gezet:")
    print("  - totaal_bedrag")
    print("  - bedrag_excl_btw")
    print("  - bedrag_btw")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
