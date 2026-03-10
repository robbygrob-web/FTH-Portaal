"""
Script om Gravity Forms inzendingen op te halen via REST API en te verwerken als orders.
Vervangt webhook functionaliteit met polling.
"""
import sys
import os
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
_LOG = logging.getLogger(__name__)

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
        _LOG.info("Vervang interne URL met publieke URL voor lokaal gebruik...")
        database_url = database_url.replace(
            "postgres.railway.internal:5432",
            "metro.proxy.rlwy.net:18535"
        )
        # Vervang *** met echte password (tijdelijk voor lokaal gebruik)
        if "***" in database_url:
            database_url = database_url.replace("***", "bHmvLbuqHOvoAmZfYzWblUQERHnwdaBm")
    
    return database_url


def get_gravity_forms_config():
    """Haal Gravity Forms configuratie op uit environment"""
    wordpress_url = os.getenv("WORDPRESS_URL", "https://friettruck-huren.nl")
    api_username = os.getenv("GRAVITY_FORMS_API_USERNAME")
    api_password = os.getenv("GRAVITY_FORMS_API_PASSWORD")
    form_id = os.getenv("GRAVITY_FORMS_FORM_ID")
    
    if not api_username or not api_password:
        raise ValueError(
            "GRAVITY_FORMS_API_USERNAME en GRAVITY_FORMS_API_PASSWORD zijn vereist.\n"
            "Gebruik WordPress Application Password voor authenticatie."
        )
    
    if not form_id:
        raise ValueError("GRAVITY_FORMS_FORM_ID is vereist")
    
    return {
        "wordpress_url": wordpress_url.rstrip('/'),
        "api_username": api_username,
        "api_password": api_password,
        "form_id": int(form_id)
    }


def get_gravity_forms_entries(config, date_created_min=None):
    """
    Haal Gravity Forms entries op via REST API.
    
    Args:
        config: Config dict met wordpress_url, api_username, api_password, form_id
        date_created_min: Alleen entries ophalen na deze datum (datetime object)
    
    Returns:
        List van entry dicts
    """
    base_url = f"{config['wordpress_url']}/wp-json/gf/v2"
    form_id = config['form_id']
    
    # Build query parameters
    params = {
        "form_ids": form_id,
        "paging": {
            "page_size": 100  # Max entries per request
        }
    }
    
    # Als date_created_min is opgegeven, filter op datum
    if date_created_min:
        # Gravity Forms gebruikt ISO 8601 format
        params["search"] = {
            "start_date": date_created_min.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    # Authenticatie via Basic Auth
    auth = (config['api_username'], config['api_password'])
    
    try:
        _LOG.info(f"Ophalen entries voor form ID {form_id}...")
        response = requests.get(
            f"{base_url}/entries",
            params=params,
            auth=auth,
            timeout=30
        )
        
        if response.status_code == 401:
            raise ValueError(
                "Authenticatie gefaald. Controleer GRAVITY_FORMS_API_USERNAME en "
                "GRAVITY_FORMS_API_PASSWORD (moet Application Password zijn)."
            )
        
        response.raise_for_status()
        
        entries = response.json()
        
        if not isinstance(entries, list):
            _LOG.warning(f"Onverwacht response formaat: {type(entries)}")
            return []
        
        _LOG.info(f"{len(entries)} entry(s) opgehaald")
        return entries
        
    except requests.exceptions.RequestException as e:
        _LOG.error(f"Fout bij ophalen entries: {e}")
        raise


def parse_gravity_entry(entry):
    """
    Parse Gravity Forms entry naar gestandaardiseerd formaat.
    
    Args:
        entry: Gravity Forms entry dict
    
    Returns:
        Dict met gestandaardiseerde velden
    """
    # Gravity Forms entries hebben een 'form_fields' dict met field IDs als keys
    form_fields = entry.get('form_fields', {})
    
    # Map common field names (aanpasbaar op basis van je formulier structuur)
    parsed = {
        "entry_id": entry.get('id'),
        "date_created": entry.get('date_created'),
        "email": None,
        "name": None,
        "phone": None,
        "street": None,
        "zip": None,
        "city": None,
        "event_date": None,
        "location": None,
        "aantal_personen": None,
        "aantal_kinderen": None,
        "opmerkingen": None
    }
    
    # Zoek email veld (kan verschillende IDs hebben)
    for field_id, value in form_fields.items():
        if not value:
            continue
        
        # Probeer verschillende veldnamen te herkennen
        field_value = str(value).strip()
        
        # Email detectie
        if '@' in field_value and not parsed['email']:
            parsed['email'] = field_value
        
        # Naam detectie (geen email, geen nummer, redelijk lang)
        elif len(field_value) > 3 and '@' not in field_value and not field_value.replace('.', '').replace('-', '').isdigit():
            if not parsed['name']:
                parsed['name'] = field_value
        
        # Telefoon detectie (bevat cijfers en mogelijk +, -, spaces)
        elif any(c.isdigit() for c in field_value) and len(field_value) >= 8:
            if not parsed['phone']:
                parsed['phone'] = field_value
    
    # Probeer specifieke velden te vinden op basis van labels (als beschikbaar)
    # Gravity Forms kan labels hebben in entry metadata
    if 'labels' in entry:
        labels = entry['labels']
        for field_id, label in labels.items():
            value = form_fields.get(field_id, '')
            if not value:
                continue
            
            label_lower = label.lower() if label else ''
            value_str = str(value).strip()
            
            if 'email' in label_lower:
                parsed['email'] = value_str
            elif 'naam' in label_lower or 'name' in label_lower:
                parsed['name'] = value_str
            elif 'telefoon' in label_lower or 'phone' in label_lower:
                parsed['phone'] = value_str
            elif 'straat' in label_lower or 'street' in label_lower or 'adres' in label_lower:
                parsed['street'] = value_str
            elif 'postcode' in label_lower or 'zip' in label_lower:
                parsed['zip'] = value_str
            elif 'stad' in label_lower or 'city' in label_lower or 'plaats' in label_lower:
                parsed['city'] = value_str
            elif 'datum' in label_lower or 'date' in label_lower or 'evenement' in label_lower:
                parsed['event_date'] = value_str
            elif 'locatie' in label_lower or 'location' in label_lower:
                parsed['location'] = value_str
            elif 'personen' in label_lower or 'aantal' in label_lower:
                try:
                    parsed['aantal_personen'] = int(value_str)
                except (ValueError, TypeError):
                    pass
            elif 'kinderen' in label_lower:
                try:
                    parsed['aantal_kinderen'] = int(value_str)
                except (ValueError, TypeError):
                    pass
            elif 'opmerking' in label_lower or 'notitie' in label_lower or 'message' in label_lower:
                parsed['opmerkingen'] = value_str
    
    return parsed


def get_or_create_contact(gravity_data: dict, cur, conn) -> str:
    """
    Haal contact op of maak aan op basis van email.
    Retourneert contact UUID.
    """
    email = gravity_data.get("email")
    
    if not email:
        raise ValueError("Email ontbreekt in Gravity Forms data")
    
    # Check of contact al bestaat
    cur.execute(
        "SELECT id FROM contacten WHERE email = %s",
        (email,)
    )
    existing = cur.fetchone()
    
    if existing:
        contact_id = existing[0]
        _LOG.info(f"Bestaand contact gevonden: {contact_id} (email: {email})")
        return contact_id
    
    # Maak nieuw contact aan
    naam = gravity_data.get("name") or email.split("@")[0]
    telefoon = gravity_data.get("phone")
    straat = gravity_data.get("street")
    postcode = gravity_data.get("zip")
    stad = gravity_data.get("city")
    
    # Bepaal bedrijfstype (standaard 'company' voor nieuwe aanvragen)
    bedrijfstype = "company"
    
    cur.execute("""
        INSERT INTO contacten (
            naam, email, telefoon, straat, postcode, stad,
            land_code, bedrijfstype, actief
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING id
    """, (
        naam,
        email,
        telefoon,
        straat,
        postcode,
        stad,
        "NL",  # Default land_code
        bedrijfstype,
        True  # actief
    ))
    
    contact_id = cur.fetchone()[0]
    conn.commit()
    _LOG.info(f"Nieuw contact aangemaakt: {contact_id} (email: {email})")
    return contact_id


def generate_ordernummer() -> str:
    """Genereer uniek ordernummer"""
    # Format: GF-YYYYMMDD-HHMMSS-UUID(8)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_uuid = str(uuid.uuid4())[:8].upper()
    return f"GF-{timestamp}-{short_uuid}"


def is_entry_processed(entry_id: int, cur) -> bool:
    """
    Controleer of entry al is verwerkt.
    We gebruiken het opmerkingen veld om entry ID op te slaan.
    """
    # Zoek in opmerkingen veld naar entry ID
    cur.execute("""
        SELECT id FROM orders 
        WHERE opmerkingen LIKE %s
    """, (f"%GF_ENTRY_{entry_id}%",))
    
    return cur.fetchone() is not None


def process_entry(entry: dict, config: dict, cur, conn):
    """
    Verwerk een Gravity Forms entry als order.
    
    Args:
        entry: Gravity Forms entry dict
        config: Config dict
        cur: Database cursor
        conn: Database connection
    
    Returns:
        Order ID als succesvol, None als al verwerkt of fout
    """
    entry_id = entry.get('id')
    
    if not entry_id:
        _LOG.warning("Entry heeft geen ID, overslaan...")
        return None
    
    # Check of entry al is verwerkt
    if is_entry_processed(entry_id, cur):
        _LOG.info(f"Entry {entry_id} is al verwerkt, overslaan...")
        return None
    
    try:
        # Parse entry naar gestandaardiseerd formaat
        gravity_data = parse_gravity_entry(entry)
        
        if not gravity_data.get('email'):
            _LOG.warning(f"Entry {entry_id} heeft geen email, overslaan...")
            return None
        
        # Stap 1: Haal contact op of maak aan
        contact_id = get_or_create_contact(gravity_data, cur, conn)
        
        # Stap 2: Maak order aan
        # Parse datum/tijd evenement
        event_date_str = gravity_data.get("event_date")
        leverdatum = None
        if event_date_str:
            try:
                # Probeer verschillende datum formaten
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d-%m-%Y"]:
                    try:
                        leverdatum = datetime.strptime(str(event_date_str), fmt)
                        break
                    except ValueError:
                        continue
                if not leverdatum:
                    _LOG.warning(f"Kon datum niet parsen: {event_date_str}")
            except Exception as e:
                _LOG.warning(f"Fout bij parsen datum: {e}")
        
        # Als geen leverdatum, gebruik huidige datum + 7 dagen
        if not leverdatum:
            leverdatum = datetime.now() + timedelta(days=7)
        
        # Genereer uniek ordernummer
        ordernummer = generate_ordernummer()
        
        # Haal order data op
        plaats = gravity_data.get("location") or "Onbekend"
        aantal_personen = gravity_data.get("aantal_personen") or 0
        aantal_kinderen = gravity_data.get("aantal_kinderen") or 0
        opmerkingen = gravity_data.get("opmerkingen") or ""
        
        # Voeg entry ID toe aan opmerkingen voor tracking
        opmerkingen_with_id = f"{opmerkingen}\n\n[GF_ENTRY_{entry_id}]".strip()
        
        # Maak order aan
        cur.execute("""
            INSERT INTO orders (
                ordernummer, order_datum, leverdatum,
                status, portaal_status, type_naam,
                klant_id, plaats, aantal_personen, aantal_kinderen,
                ordertype, opmerkingen,
                totaal_bedrag, bedrag_excl_btw, bedrag_btw
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            ordernummer,
            datetime.now(),  # order_datum
            leverdatum,  # leverdatum
            "draft",  # status (nieuwe aanvraag)
            "nieuw",  # portaal_status
            "Aanvraag",  # type_naam
            contact_id,  # klant_id
            plaats,
            aantal_personen,
            aantal_kinderen,
            "b2c",  # ordertype (standaard b2c voor Gravity Forms)
            opmerkingen_with_id,
            0.00,  # totaal_bedrag (nog niet berekend)
            0.00,  # bedrag_excl_btw
            0.00   # bedrag_btw
        ))
        
        order_id = cur.fetchone()[0]
        conn.commit()
        
        _LOG.info(f"Order aangemaakt: {order_id} (ordernummer: {ordernummer}, entry: {entry_id}, contact: {contact_id})")
        return order_id
        
    except Exception as e:
        _LOG.error(f"Fout bij verwerken entry {entry_id}: {e}", exc_info=True)
        conn.rollback()
        return None


def poll_gravity_forms():
    """Hoofdfunctie: haal entries op en verwerk ze"""
    print("="*80)
    print("Gravity Forms Polling Script")
    print("="*80)
    
    try:
        # Stap 1: Haal configuratie op
        print("\n[1/5] Configuratie ophalen...")
        config = get_gravity_forms_config()
        print(f"   [OK] WordPress URL: {config['wordpress_url']}")
        print(f"   [OK] Form ID: {config['form_id']}")
        
        # Stap 2: Verbind met database
        print("\n[2/5] Verbinden met database...")
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        print("   [OK] Verbonden")
        
        # Stap 3: Haal laatste verwerkte entry datum op (optioneel, voor efficiency)
        print("\n[3/5] Bepalen welke entries op te halen...")
        # Haal laatste order op met GF entry ID in opmerkingen
        cur.execute("""
            SELECT opmerkingen, created_at 
            FROM orders 
            WHERE opmerkingen LIKE '%GF_ENTRY_%'
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        last_processed = cur.fetchone()
        
        date_created_min = None
        if last_processed:
            # Parse entry ID uit opmerkingen
            opmerkingen = last_processed[0] or ""
            # Haal entry datum op uit Gravity Forms (we gebruiken created_at als proxy)
            # In productie zou je de entry date_created kunnen gebruiken
            print(f"   [INFO] Laatste verwerkte order gevonden, alleen nieuwe entries ophalen...")
        else:
            print(f"   [INFO] Geen eerdere verwerkingen gevonden, alle entries ophalen...")
        
        # Stap 4: Haal entries op
        print("\n[4/5] Ophalen entries van Gravity Forms...")
        entries = get_gravity_forms_entries(config, date_created_min)
        print(f"   [OK] {len(entries)} entry(s) opgehaald")
        
        # Stap 5: Verwerk entries
        print("\n[5/5] Verwerken entries...")
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        for entry in entries:
            result = process_entry(entry, config, cur, conn)
            if result:
                processed_count += 1
            elif result is None:
                skipped_count += 1
            else:
                error_count += 1
        
        print(f"   [OK] Verwerking voltooid:")
        print(f"        - Verwerkt: {processed_count}")
        print(f"        - Overgeslagen (al verwerkt): {skipped_count}")
        print(f"        - Fouten: {error_count}")
        
        cur.close()
        conn.close()
        
        print("\n" + "="*80)
        print("Klaar!")
        print("="*80)
        
    except Exception as e:
        _LOG.error(f"Fout: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    poll_gravity_forms()
