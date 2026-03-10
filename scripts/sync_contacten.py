"""
Script om contacten te synchroniseren van Odoo naar eigen PostgreSQL database.
Gebruikt bestaande Odoo connectie en DATABASE_URL uit .env.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad environment variabelen
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values
from app.odoo_client import get_odoo_client


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL niet gevonden in environment variabelen.\n"
            "Zorg ervoor dat DATABASE_URL is ingesteld in .env of als environment variabele."
        )
    return database_url


def get_odoo_partners():
    """Haal alle actieve contacten op uit Odoo"""
    client = get_odoo_client()
    
    # Haal alle actieve partners op
    print("[1/4] Ophalen contacten uit Odoo...")
    partners = client.execute_kw(
        "res.partner",
        "search_read",
        [("active", "=", True)],
        {
            "fields": [
                "id",
                "name",
                "email",
                "phone",
                "street",
                "zip",
                "city",
                "country_code",
                "vat",
                "company_type",
                "is_company",
                "x_studio_portaal_partner",
                "x_studio_partner_commission",
                "x_studio_self_owned",
                "x_studio_wordpress_id",
                "peppol_endpoint",
                "peppol_eas",
                "peppol_verification_state",
                "active"
            ],
            "limit": 10000  # Haal alle actieve partners op
        }
    )
    
    print(f"   [OK] {len(partners)} contacten gevonden in Odoo")
    return partners


def get_bank_accounts(client, partner_ids):
    """Haal bankgegevens op voor partners"""
    if not partner_ids:
        return {}
    
    print("[2/4] Ophalen bankgegevens uit Odoo...")
    bank_accounts = client.execute_kw(
        "res.partner.bank",
        "search_read",
        [("partner_id", "in", partner_ids)],
        {
            "fields": ["partner_id", "acc_number", "acc_holder_name"],
            "limit": 10000
        }
    )
    
    # Groepeer per partner_id
    bank_dict = {}
    for bank in bank_accounts:
        partner_id = bank["partner_id"][0] if isinstance(bank["partner_id"], list) else bank["partner_id"]
        # Neem de eerste IBAN (meestal de belangrijkste)
        if partner_id not in bank_dict:
            bank_dict[partner_id] = {
                "iban": bank.get("acc_number", ""),
                "bank_tenaamstelling": bank.get("acc_holder_name", "")
            }
    
    print(f"   [OK] {len(bank_dict)} bankrekeningen gevonden")
    return bank_dict


def map_odoo_to_postgres(partner, bank_data=None):
    """Map Odoo partner data naar PostgreSQL contacten structuur"""
    bank_data = bank_data or {}
    
    # Bepaal bedrijfstype
    company_type = partner.get("company_type", "person")
    if company_type == "company" or partner.get("is_company", False):
        bedrijfstype = "company"
    elif company_type == "person":
        bedrijfstype = "person"
    else:
        bedrijfstype = "contact"
    
    # Extract BTW nummer (vat kan een lijst zijn of string)
    vat = partner.get("vat", "")
    if isinstance(vat, list):
        vat = vat[0] if vat else ""
    btw_nummer = vat if vat else None
    
    # Extract Peppol EAS (kan een lijst zijn)
    peppol_eas = partner.get("peppol_eas", "")
    if isinstance(peppol_eas, list):
        peppol_eas = peppol_eas[0] if peppol_eas else ""
    peppol_eas = peppol_eas if peppol_eas else None
    
    # Extract Peppol verificatie status
    peppol_status = partner.get("peppol_verification_state", "not_verified")
    if isinstance(peppol_status, list):
        peppol_status = peppol_status[0] if peppol_status else "not_verified"
    
    return {
        "odoo_id": partner["id"],
        "naam": partner.get("name", ""),
        "email": partner.get("email") or None,
        "telefoon": partner.get("phone") or None,
        "straat": partner.get("street") or None,
        "postcode": partner.get("zip") or None,
        "stad": partner.get("city") or None,
        "land_code": partner.get("country_code", "NL") or "NL",
        "btw_nummer": btw_nummer,
        "kvk_nummer": None,  # Niet beschikbaar in Odoo
        "bedrijfstype": bedrijfstype,
        "is_portaal_partner": partner.get("x_studio_portaal_partner", False),
        "partner_commissie": float(partner.get("x_studio_partner_commission", 0) or 0),
        "heeft_eigen_truck": partner.get("x_studio_self_owned", False),
        "wordpress_id": partner.get("x_studio_wordpress_id") or None,
        "peppol_endpoint": partner.get("peppol_endpoint") or None,
        "peppol_eas": peppol_eas,
        "peppol_verificatie_status": peppol_status or "not_verified",
        "iban": bank_data.get("iban") or None,
        "bank_tenaamstelling": bank_data.get("bank_tenaamstelling") or None,
        "actief": partner.get("active", True)
    }


def sync_contacten():
    """Synchroniseer contacten van Odoo naar PostgreSQL"""
    print("="*80)
    print("Contacten Synchronisatie")
    print("="*80)
    
    try:
        # Haal Odoo partners op
        partners = get_odoo_partners()
        
        if not partners:
            print("\n[WAARSCHUWING] Geen contacten gevonden in Odoo")
            return
        
        # Haal bankgegevens op
        partner_ids = [p["id"] for p in partners]
        client = get_odoo_client()
        bank_data = get_bank_accounts(client, partner_ids)
        
        # Map naar PostgreSQL structuur
        print("[3/4] Mappen van Odoo data naar PostgreSQL structuur...")
        mapped_partners = []
        for partner in partners:
            partner_bank = bank_data.get(partner["id"], {})
            mapped = map_odoo_to_postgres(partner, partner_bank)
            mapped_partners.append(mapped)
        
        print(f"   [OK] {len(mapped_partners)} contacten gemapt")
        
        # Sla op in PostgreSQL (upsert op odoo_id)
        print("[4/4] Opslaan in PostgreSQL database...")
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        inserted_count = 0
        updated_count = 0
        
        for partner_data in mapped_partners:
            # Check of contact al bestaat (op odoo_id of email als odoo_id niet uniek is)
            cur.execute(
                "SELECT id, odoo_id FROM contacten WHERE odoo_id = %s OR (email = %s AND email IS NOT NULL)",
                (partner_data["odoo_id"], partner_data["email"])
            )
            existing = cur.fetchone()
            
            if existing:
                # Update bestaand contact (gebruik het gevonden ID)
                contact_id = existing[0]
                # Update bestaand contact
                cur.execute("""
                    UPDATE contacten SET
                        naam = %s,
                        email = %s,
                        telefoon = %s,
                        straat = %s,
                        postcode = %s,
                        stad = %s,
                        land_code = %s,
                        btw_nummer = %s,
                        bedrijfstype = %s,
                        is_portaal_partner = %s,
                        partner_commissie = %s,
                        heeft_eigen_truck = %s,
                        wordpress_id = %s,
                        peppol_endpoint = %s,
                        peppol_eas = %s,
                        peppol_verificatie_status = %s,
                        iban = %s,
                        bank_tenaamstelling = %s,
                        actief = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    partner_data["naam"],
                    partner_data["email"],
                    partner_data["telefoon"],
                    partner_data["straat"],
                    partner_data["postcode"],
                    partner_data["stad"],
                    partner_data["land_code"],
                    partner_data["btw_nummer"],
                    partner_data["bedrijfstype"],
                    partner_data["is_portaal_partner"],
                    partner_data["partner_commissie"],
                    partner_data["heeft_eigen_truck"],
                    partner_data["wordpress_id"],
                    partner_data["peppol_endpoint"],
                    partner_data["peppol_eas"],
                    partner_data["peppol_verificatie_status"],
                    partner_data["iban"],
                    partner_data["bank_tenaamstelling"],
                    partner_data["actief"],
                    contact_id
                ))
                updated_count += 1
            else:
                # Insert nieuw contact
                cur.execute("""
                    INSERT INTO contacten (
                        odoo_id, naam, email, telefoon, straat, postcode, stad,
                        land_code, btw_nummer, bedrijfstype, is_portaal_partner,
                        partner_commissie, heeft_eigen_truck, wordpress_id,
                        peppol_endpoint, peppol_eas, peppol_verificatie_status,
                        iban, bank_tenaamstelling, actief
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    partner_data["odoo_id"],
                    partner_data["naam"],
                    partner_data["email"],
                    partner_data["telefoon"],
                    partner_data["straat"],
                    partner_data["postcode"],
                    partner_data["stad"],
                    partner_data["land_code"],
                    partner_data["btw_nummer"],
                    partner_data["bedrijfstype"],
                    partner_data["is_portaal_partner"],
                    partner_data["partner_commissie"],
                    partner_data["heeft_eigen_truck"],
                    partner_data["wordpress_id"],
                    partner_data["peppol_endpoint"],
                    partner_data["peppol_eas"],
                    partner_data["peppol_verificatie_status"],
                    partner_data["iban"],
                    partner_data["bank_tenaamstelling"],
                    partner_data["actief"]
                ))
                inserted_count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Resultaat
        print("\n" + "="*80)
        print("Synchronisatie voltooid!")
        print("="*80)
        print(f"\nTotaal contacten verwerkt: {len(mapped_partners)}")
        print(f"  - Nieuw toegevoegd: {inserted_count}")
        print(f"  - Bijgewerkt: {updated_count}")
        print(f"\nKlaar!")
        
    except Exception as e:
        print(f"\n[FOUT] Fout tijdens synchronisatie: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sync_contacten()
