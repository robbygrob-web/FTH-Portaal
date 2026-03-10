"""
Webhook endpoints voor Odoo synchronisatie.
FLOW 1: Odoo → eigen DB
"""
import os
import logging
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def get_webhook_secret():
    """Haal WEBHOOK_SECRET op uit environment"""
    secret = os.getenv("WEBHOOK_SECRET")
    if not secret:
        raise ValueError("WEBHOOK_SECRET niet gevonden in environment variabelen")
    return secret


def verify_webhook_token(token: str) -> bool:
    """Verifieer webhook token"""
    expected_secret = get_webhook_secret()
    return token == expected_secret


def map_odoo_to_postgres(odoo_data: dict) -> dict:
    """Map Odoo partner data naar PostgreSQL contacten structuur"""
    # Extract BTW nummer
    vat = odoo_data.get("vat", "")
    if isinstance(vat, list):
        vat = vat[0] if vat else ""
    btw_nummer = vat if vat else None
    
    # Extract Peppol EAS
    peppol_eas = odoo_data.get("peppol_eas", "")
    if isinstance(peppol_eas, list):
        peppol_eas = peppol_eas[0] if peppol_eas else ""
    peppol_eas = peppol_eas if peppol_eas else None
    
    # Extract Peppol verificatie status
    peppol_status = odoo_data.get("peppol_verification_state", "not_verified")
    if isinstance(peppol_status, list):
        peppol_status = peppol_status[0] if peppol_status else "not_verified"
    
    # Bepaal bedrijfstype
    company_type = odoo_data.get("company_type", "person")
    is_company = odoo_data.get("is_company", False)
    if company_type == "company" or is_company:
        bedrijfstype = "company"
    elif company_type == "person":
        bedrijfstype = "person"
    else:
        bedrijfstype = "contact"
    
    return {
        "odoo_id": odoo_data["id"],
        "naam": odoo_data.get("name", ""),
        "email": odoo_data.get("email") or None,
        "telefoon": odoo_data.get("phone") or None,
        "straat": odoo_data.get("street") or None,
        "postcode": odoo_data.get("zip") or None,
        "stad": odoo_data.get("city") or None,
        "land_code": odoo_data.get("country_code", "NL") or "NL",
        "btw_nummer": btw_nummer,
        "kvk_nummer": None,  # Niet beschikbaar in Odoo
        "bedrijfstype": bedrijfstype,
        "is_portaal_partner": odoo_data.get("x_studio_portaal_partner", False),
        "partner_commissie": float(odoo_data.get("x_studio_partner_commission", 0) or 0),
        "heeft_eigen_truck": odoo_data.get("x_studio_self_owned", False),
        "wordpress_id": odoo_data.get("x_studio_wordpress_id") or None,
        "peppol_endpoint": odoo_data.get("peppol_endpoint") or None,
        "peppol_eas": peppol_eas,
        "peppol_verificatie_status": peppol_status or "not_verified",
        "iban": odoo_data.get("iban") or None,
        "bank_tenaamstelling": odoo_data.get("bank_tenaamstelling") or None,
        "actief": odoo_data.get("active", True)
    }


@router.post("/odoo/contact")
async def odoo_contact_webhook(
    request: Request,
    x_odoo_webhook_token: str = Header(..., alias="X-Odoo-Webhook-Token")
):
    """
    Webhook endpoint voor Odoo contact synchronisatie.
    Ontvangt create/update/delete events van Odoo en synchroniseert naar eigen DB.
    
    Headers:
        X-Odoo-Webhook-Token: Webhook secret voor verificatie
    
    Body:
        {
            "event": "create" | "update" | "delete",
            "data": { ... }  # res.partner data
        }
    """
    # Verifieer token
    if not verify_webhook_token(x_odoo_webhook_token):
        _LOG.warning("Webhook call met ongeldige token")
        raise HTTPException(status_code=401, detail="Ongeldige webhook token")
    
    try:
        # Parse request body
        body = await request.json()
        event = body.get("event")
        odoo_data = body.get("data", {})
        
        if not event:
            raise HTTPException(status_code=400, detail="Event type ontbreekt")
        
        if not odoo_data:
            raise HTTPException(status_code=400, detail="Data ontbreekt")
        
        odoo_id = odoo_data.get("id")
        if not odoo_id:
            raise HTTPException(status_code=400, detail="Odoo ID ontbreekt")
        
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        if event == "delete":
            # Verwijder contact uit eigen DB
            cur.execute(
                "DELETE FROM contacten WHERE odoo_id = %s",
                (odoo_id,)
            )
            conn.commit()
            _LOG.info(f"Contact verwijderd: odoo_id={odoo_id}")
            
        elif event in ("create", "update"):
            # Upsert contact
            mapped_data = map_odoo_to_postgres(odoo_data)
            
            # Check of contact al bestaat
            cur.execute(
                "SELECT id FROM contacten WHERE odoo_id = %s",
                (odoo_id,)
            )
            existing = cur.fetchone()
            
            if existing:
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
                    WHERE odoo_id = %s
                """, (
                    mapped_data["naam"],
                    mapped_data["email"],
                    mapped_data["telefoon"],
                    mapped_data["straat"],
                    mapped_data["postcode"],
                    mapped_data["stad"],
                    mapped_data["land_code"],
                    mapped_data["btw_nummer"],
                    mapped_data["bedrijfstype"],
                    mapped_data["is_portaal_partner"],
                    mapped_data["partner_commissie"],
                    mapped_data["heeft_eigen_truck"],
                    mapped_data["wordpress_id"],
                    mapped_data["peppol_endpoint"],
                    mapped_data["peppol_eas"],
                    mapped_data["peppol_verificatie_status"],
                    mapped_data["iban"],
                    mapped_data["bank_tenaamstelling"],
                    mapped_data["actief"],
                    odoo_id
                ))
                _LOG.info(f"Contact bijgewerkt: odoo_id={odoo_id}")
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
                    mapped_data["odoo_id"],
                    mapped_data["naam"],
                    mapped_data["email"],
                    mapped_data["telefoon"],
                    mapped_data["straat"],
                    mapped_data["postcode"],
                    mapped_data["stad"],
                    mapped_data["land_code"],
                    mapped_data["btw_nummer"],
                    mapped_data["bedrijfstype"],
                    mapped_data["is_portaal_partner"],
                    mapped_data["partner_commissie"],
                    mapped_data["heeft_eigen_truck"],
                    mapped_data["wordpress_id"],
                    mapped_data["peppol_endpoint"],
                    mapped_data["peppol_eas"],
                    mapped_data["peppol_verificatie_status"],
                    mapped_data["iban"],
                    mapped_data["bank_tenaamstelling"],
                    mapped_data["actief"]
                ))
                _LOG.info(f"Contact aangemaakt: odoo_id={odoo_id}")
            
            conn.commit()
        
        cur.close()
        conn.close()
        
        return JSONResponse({
            "status": "success",
            "event": event,
            "odoo_id": odoo_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error(f"Fout bij webhook verwerking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Interne server fout: {str(e)}")
