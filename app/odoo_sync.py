"""
Synchronisatie functies voor eigen DB → Odoo.
FLOW 2: eigen DB → Odoo
"""
import os
import logging
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from app.odoo_client import get_odoo_client

_LOG = logging.getLogger(__name__)


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def map_postgres_to_odoo(contact_data: dict) -> dict:
    """Map PostgreSQL contacten data naar Odoo res.partner structuur"""
    # Bepaal company_type en is_company op basis van bedrijfstype
    bedrijfstype = contact_data.get("bedrijfstype", "company")
    if bedrijfstype == "company":
        company_type = "company"
        is_company = True
    elif bedrijfstype == "person":
        company_type = "person"
        is_company = False
    else:
        company_type = "contact"
        is_company = False
    
    odoo_data = {
        "name": contact_data.get("naam", ""),
        "email": contact_data.get("email") or False,
        "phone": contact_data.get("telefoon") or False,
        "street": contact_data.get("straat") or False,
        "zip": contact_data.get("postcode") or False,
        "city": contact_data.get("stad") or False,
        "country_code": contact_data.get("land_code", "NL") or "NL",
        "vat": contact_data.get("btw_nummer") or False,
        "company_type": company_type,
        "is_company": is_company,
        "x_studio_portaal_partner": contact_data.get("is_portaal_partner", False),
        "x_studio_partner_commission": float(contact_data.get("partner_commissie", 0) or 0),
        "x_studio_self_owned": contact_data.get("heeft_eigen_truck", False),
        "x_studio_wordpress_id": contact_data.get("wordpress_id") or 0,
        "peppol_endpoint": contact_data.get("peppol_endpoint") or False,
        "peppol_eas": contact_data.get("peppol_eas") or False,
        "peppol_verification_state": contact_data.get("peppol_verificatie_status", "not_verified") or "not_verified",
        "active": contact_data.get("actief", True)
    }
    
    # Verwijder False waarden (Odoo verwacht deze niet)
    return {k: v for k, v in odoo_data.items() if v is not False}


def sync_contact_naar_odoo(contact_id: str, skip_webhook: bool = True) -> Optional[int]:
    """
    Synchroniseer een contact van eigen DB naar Odoo.
    
    Args:
        contact_id: UUID van het contact in eigen DB
        skip_webhook: Als True, voorkomt dat Odoo webhook terug triggert (standaard True)
    
    Returns:
        Odoo ID als succesvol, None bij fout
    
    Note:
        Deze functie triggert GEEN webhook terug naar eigen DB om loops te voorkomen.
        Odoo moet geconfigureerd worden om webhooks alleen te triggeren bij handmatige wijzigingen.
    """
    try:
        # Haal contact op uit eigen DB
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            "SELECT * FROM contacten WHERE id = %s",
            (contact_id,)
        )
        contact = cur.fetchone()
        
        if not contact:
            _LOG.warning(f"Contact niet gevonden: id={contact_id}")
            cur.close()
            conn.close()
            return None
        
        contact_dict = dict(contact)
        odoo_id = contact_dict.get("odoo_id")
        
        # Map naar Odoo structuur
        odoo_data = map_postgres_to_odoo(contact_dict)
        
        # Synchroniseer naar Odoo
        client = get_odoo_client()
        
        if odoo_id:
            # Update bestaand contact in Odoo
            client.execute_kw(
                "res.partner",
                "write",
                [odoo_id],
                odoo_data
            )
            _LOG.info(f"Contact bijgewerkt in Odoo: odoo_id={odoo_id}, contact_id={contact_id}")
            cur.close()
            conn.close()
            return odoo_id
        else:
            # Maak nieuw contact aan in Odoo
            # execute_kw verwacht voor create: [values_dict] als domain
            result = client.execute_kw(
                "res.partner",
                "create",
                [odoo_data],
                None
            )
            
            # Odoo geeft een lijst terug met het nieuwe ID
            new_odoo_id = result[0] if isinstance(result, list) else result
            
            # Sla odoo_id op in eigen DB
            cur.execute(
                "UPDATE contacten SET odoo_id = %s WHERE id = %s",
                (new_odoo_id, contact_id)
            )
            conn.commit()
            
            _LOG.info(f"Contact aangemaakt in Odoo: odoo_id={new_odoo_id}, contact_id={contact_id}")
            cur.close()
            conn.close()
            return new_odoo_id
            
    except Exception as e:
        _LOG.error(f"Fout bij synchronisatie naar Odoo: {e}", exc_info=True)
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return None


def sync_bank_naar_odoo(contact_id: str) -> bool:
    """
    Synchroniseer bankgegevens van eigen DB naar Odoo.
    
    Args:
        contact_id: UUID van het contact in eigen DB
    
    Returns:
        True als succesvol, False bij fout
    """
    try:
        # Haal contact op uit eigen DB
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            "SELECT odoo_id, iban, bank_tenaamstelling FROM contacten WHERE id = %s",
            (contact_id,)
        )
        contact = cur.fetchone()
        
        if not contact:
            _LOG.warning(f"Contact niet gevonden: id={contact_id}")
            cur.close()
            conn.close()
            return False
        
        odoo_id = contact.get("odoo_id")
        iban = contact.get("iban")
        bank_tenaamstelling = contact.get("bank_tenaamstelling")
        
        if not odoo_id:
            _LOG.warning(f"Contact heeft geen odoo_id: id={contact_id}")
            cur.close()
            conn.close()
            return False
        
        if not iban:
            # Geen IBAN, verwijder bestaande bankrekeningen
            client = get_odoo_client()
            # Zoek bestaande bankrekeningen
            banks = client.execute_kw(
                "res.partner.bank",
                "search_read",
                [("partner_id", "=", odoo_id)],
                {"fields": ["id"], "limit": 100}
            )
            
            if banks:
                bank_ids = [b["id"] for b in banks]
                client.execute_kw(
                    "res.partner.bank",
                    "unlink",
                    bank_ids,
                    None
                )
                _LOG.info(f"Bankrekeningen verwijderd voor odoo_id={odoo_id}")
            
            cur.close()
            conn.close()
            return True
        
        # Update of maak bankrekening aan
        client = get_odoo_client()
        
        # Zoek bestaande bankrekening
        banks = client.execute_kw(
            "res.partner.bank",
            "search_read",
            [("partner_id", "=", odoo_id)],
            {"fields": ["id"], "limit": 1}
        )
        
        bank_values = {
            "partner_id": odoo_id,
            "acc_number": iban,
            "acc_holder_name": bank_tenaamstelling or ""
        }
        
        if banks:
            # Update bestaande bankrekening
            bank_id = banks[0]["id"]
            client.execute_kw(
                "res.partner.bank",
                "write",
                [bank_id],
                bank_values
            )
            _LOG.info(f"Bankrekening bijgewerkt voor odoo_id={odoo_id}")
        else:
            # Maak nieuwe bankrekening aan
            client.execute_kw(
                "res.partner.bank",
                "create",
                [bank_values],
                None
            )
            _LOG.info(f"Bankrekening aangemaakt voor odoo_id={odoo_id}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        _LOG.error(f"Fout bij bank synchronisatie naar Odoo: {e}", exc_info=True)
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return False
