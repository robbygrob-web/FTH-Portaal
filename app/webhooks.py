"""
Webhook endpoints voor Odoo synchronisatie.
FLOW 1: Odoo → eigen DB
"""
import os
import logging
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Header, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/test")
async def test_webhook():
    """
    Test endpoint om te controleren of webhook connectie werkt.
    Retourneert basis informatie zonder authenticatie.
    """
    return JSONResponse({
        "status": "success",
        "message": "Webhook endpoint is bereikbaar",
        "endpoint": "/webhooks/odoo/contact",
        "method": "POST",
        "required_header": "X-Odoo-Webhook-Token"
    })


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


def get_or_create_contact(gravity_data: dict, cur, conn) -> str:
    """
    Haal contact op of maak aan op basis van email.
    Retourneert contact UUID.
    """
    email = gravity_data.get("email") or gravity_data.get("Email") or gravity_data.get("email_address")
    
    if not email:
        raise ValueError("Email ontbreekt in Gravity Forms data")
    
    # Check of contact al bestaat
    try:
        cur.execute(
            "SELECT id FROM contacten WHERE email = %s",
            (email,)
        )
        existing = cur.fetchone()
        
        if existing:
            contact_id = existing[0]
            _LOG.info(f"Bestaand contact gevonden: {contact_id} (email: {email})")
            return contact_id
    except psycopg2.Error as e:
        _LOG.error(f"Database fout bij zoeken contact: {e}")
        raise
    
    # Maak nieuw contact aan
    naam = gravity_data.get("name") or gravity_data.get("Name") or gravity_data.get("bedrijfsnaam") or email.split("@")[0]
    telefoon = gravity_data.get("phone") or gravity_data.get("Phone") or gravity_data.get("telefoon")
    straat = gravity_data.get("street") or gravity_data.get("Street") or gravity_data.get("straat") or gravity_data.get("address")
    postcode = gravity_data.get("zip") or gravity_data.get("Zip") or gravity_data.get("postcode") or gravity_data.get("postal_code")
    stad = gravity_data.get("city") or gravity_data.get("City") or gravity_data.get("stad")
    
    # Bepaal bedrijfstype (standaard 'company' voor nieuwe aanvragen)
    bedrijfstype = "company"
    
    try:
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
        
        result = cur.fetchone()
        if not result:
            raise ValueError("Kon contact ID niet ophalen na insert")
        
        contact_id = result[0]
        conn.commit()
        _LOG.info(f"Nieuw contact aangemaakt: {contact_id} (email: {email})")
        return contact_id
    except psycopg2.IntegrityError as e:
        # Mogelijk duplicate email, probeer opnieuw op te halen
        conn.rollback()
        _LOG.warning(f"Integriteit fout bij contact aanmaken (mogelijk duplicate): {e}, probeer opnieuw op te halen...")
        cur.execute(
            "SELECT id FROM contacten WHERE email = %s",
            (email,)
        )
        existing = cur.fetchone()
        if existing:
            contact_id = existing[0]
            _LOG.info(f"Contact gevonden na duplicate error: {contact_id} (email: {email})")
            return contact_id
        raise


def generate_ordernummer() -> str:
    """Genereer uniek ordernummer"""
    # Format: GF-YYYYMMDD-HHMMSS-UUID(8)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_uuid = str(uuid.uuid4())[:8].upper()
    return f"GF-{timestamp}-{short_uuid}"


@router.post("/gravity/aanvraag")
async def gravity_aanvraag_webhook(request: Request, token: str = Query(..., description="Webhook secret token")):
    """
    Webhook endpoint voor Gravity Forms aanvragen.
    Ontvangt nieuwe aanvragen van Gravity Forms en maakt contact + order aan in eigen DB.
    
    Query Parameters:
        token: Webhook secret voor verificatie (verplicht)
    
    Body:
        Gravity Forms webhook data (formulier specifiek)
        Verwacht minimaal:
        - email (of Email of email_address)
        - name (of Name of bedrijfsnaam)
        - event_date (datum/tijd evenement)
        - location (locatie)
        - aantal_personen (aantal personen)
        - opmerkingen (opmerkingen/notities)
    """
    # Verifieer token uit query parameter
    if not token:
        _LOG.warning("Gravity Forms webhook call zonder token")
        raise HTTPException(status_code=401, detail="Token parameter ontbreekt")
    
    if not verify_webhook_token(token):
        _LOG.warning("Gravity Forms webhook call met ongeldige token")
        raise HTTPException(status_code=401, detail="Ongeldige webhook token")
    
    conn = None
    cur = None
    
    try:
        # Parse request body
        try:
            body = await request.json()
        except Exception as e:
            _LOG.error(f"Fout bij parsen JSON body: {e}")
            raise HTTPException(status_code=400, detail=f"Ongeldig JSON formaat: {str(e)}")
        
        _LOG.info(f"Gravity Forms webhook ontvangen: {body}")
        
        # Haal database connectie
        try:
            database_url = get_database_url()
        except ValueError as e:
            _LOG.error(f"DATABASE_URL niet gevonden: {e}")
            raise HTTPException(status_code=500, detail="Database configuratie ontbreekt")
        
        try:
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
        except psycopg2.Error as e:
            _LOG.error(f"Database connectie fout: {e}")
            raise HTTPException(status_code=500, detail=f"Database verbinding gefaald: {str(e)}")
        
        # Stap 1: Haal contact op of maak aan
        try:
            contact_id = get_or_create_contact(body, cur, conn)
        except ValueError as e:
            if cur:
                cur.close()
            if conn:
                conn.close()
            _LOG.error(f"Contact validatie fout: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            if cur:
                cur.close()
            if conn:
                conn.close()
            _LOG.error(f"Database fout bij contact aanmaken: {e}")
            raise HTTPException(status_code=500, detail=f"Database fout: {str(e)}")
        
        # Stap 2: Maak order aan
        # Parse datum/tijd evenement
        event_date_str = body.get("event_date") or body.get("Event Date") or body.get("datum") or body.get("Datum")
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
        plaats = body.get("location") or body.get("Location") or body.get("locatie") or body.get("Locatie") or "Onbekend"
        aantal_personen = body.get("aantal_personen") or body.get("Aantal personen") or body.get("personen") or body.get("Personen") or 0
        try:
            aantal_personen = int(aantal_personen)
        except (ValueError, TypeError):
            aantal_personen = 0
        
        aantal_kinderen = body.get("aantal_kinderen") or body.get("Aantal kinderen") or body.get("kinderen") or 0
        try:
            aantal_kinderen = int(aantal_kinderen)
        except (ValueError, TypeError):
            aantal_kinderen = 0
        
        opmerkingen = body.get("opmerkingen") or body.get("Opmerkingen") or body.get("notes") or body.get("Notes") or body.get("message") or ""
        
        # Maak order aan
        try:
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
                opmerkingen,
                0.00,  # totaal_bedrag (nog niet berekend)
                0.00,  # bedrag_excl_btw
                0.00   # bedrag_btw
            ))
            
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=500, detail="Kon order ID niet ophalen na insert")
            
            order_id = result[0]
            conn.commit()
            
            _LOG.info(f"Order aangemaakt: {order_id} (ordernummer: {ordernummer}, contact: {contact_id})")
            
        except psycopg2.IntegrityError as e:
            if conn:
                conn.rollback()
            _LOG.error(f"Database integriteit fout bij order aanmaken: {e}")
            raise HTTPException(status_code=400, detail=f"Order kon niet worden aangemaakt: {str(e)}")
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            _LOG.error(f"Database fout bij order aanmaken: {e}")
            raise HTTPException(status_code=500, detail=f"Database fout: {str(e)}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
        
        return JSONResponse({
            "status": "success",
            "message": "Aanvraag verwerkt",
            "contact_id": str(contact_id),
            "order_id": str(order_id),
            "ordernummer": ordernummer
        })
        
    except HTTPException:
        raise
    except Exception as e:
        # Cleanup bij onverwachte fouten
        if cur:
            try:
                cur.close()
            except:
                pass
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        _LOG.error(f"Fout bij Gravity Forms webhook verwerking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Interne server fout: {str(e)}")
