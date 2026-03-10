"""
Webhook endpoints voor externe systemen.
"""
import os
import logging
import uuid
import json
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
        "message": "Webhook endpoint is bereikbaar"
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


def get_or_create_contact(gravity_data: dict, cur, conn) -> str:
    """
    Haal contact op of maak aan op basis van email.
    Retourneert contact UUID.
    """
    # Gravity Forms gebruikt veldnummers als keys
    # Probeer eerst veldnummers, dan fallback naar oude namen
    email = (
        gravity_data.get("21") or  # Email veld
        gravity_data.get("email") or 
        gravity_data.get("Email") or 
        gravity_data.get("email_address")
    )
    
    if not email:
        raise ValueError("Email ontbreekt in Gravity Forms data (veld 21)")
    
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
    # Gravity Forms veld mapping:
    # - Email: veld '21'
    # - Telefoon: veld '24'
    # - Naam: combineer voornaam/achternaam of zoek op naam veld
    # - Locatie: veld '29.3' (stad)
    
    telefoon = (
        gravity_data.get("24") or  # Telefoon veld
        gravity_data.get("phone") or 
        gravity_data.get("Phone") or 
        gravity_data.get("telefoon")
    )
    
    # Probeer naam te vinden (kan verschillende velden zijn)
    naam = (
        gravity_data.get("name") or 
        gravity_data.get("Name") or 
        gravity_data.get("bedrijfsnaam") or
        gravity_data.get("voornaam") or
        gravity_data.get("achternaam") or
        email.split("@")[0]  # Fallback naar email prefix
    )
    
    # Combineer voornaam + achternaam als beide beschikbaar zijn
    voornaam = gravity_data.get("voornaam") or gravity_data.get("Voornaam")
    achternaam = gravity_data.get("achternaam") or gravity_data.get("Achternaam")
    if voornaam and achternaam:
        naam = f"{voornaam} {achternaam}"
    
    # Adres velden (mogelijk niet allemaal beschikbaar)
    straat = (
        gravity_data.get("street") or 
        gravity_data.get("Street") or 
        gravity_data.get("straat") or 
        gravity_data.get("address")
    )
    postcode = (
        gravity_data.get("zip") or 
        gravity_data.get("Zip") or 
        gravity_data.get("postcode") or 
        gravity_data.get("postal_code")
    )
    
    # Stad kan uit locatie veld komen (veld 29.3)
    stad = (
        gravity_data.get("29.3") or  # Locatie stad veld
        gravity_data.get("city") or 
        gravity_data.get("City") or 
        gravity_data.get("stad")
    )
    
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
        # Gravity Forms veld mapping:
        # - Datum: veld '48'
        # - Locatie: veld '29.3' (stad)
        # - Aantal personen: veld '68'
        
        # Parse datum/tijd evenement (veld 48)
        event_date_str = (
            body.get("48") or  # Datum veld
            body.get("event_date") or 
            body.get("Event Date") or 
            body.get("datum") or 
            body.get("Datum")
        )
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
        # Locatie: veld '29.3' (stad)
        plaats = (
            body.get("29.3") or  # Locatie stad veld
            body.get("location") or 
            body.get("Location") or 
            body.get("locatie") or 
            body.get("Locatie") or 
            "Onbekend"
        )
        
        # Aantal personen: veld '68'
        aantal_personen = (
            body.get("68") or  # Aantal personen veld
            body.get("aantal_personen") or 
            body.get("Aantal personen") or 
            body.get("personen") or 
            body.get("Personen") or 
            0
        )
        try:
            aantal_personen = int(aantal_personen)
        except (ValueError, TypeError):
            aantal_personen = 0
        
        aantal_kinderen = (
            body.get("aantal_kinderen") or 
            body.get("Aantal kinderen") or 
            body.get("kinderen") or 
            0
        )
        try:
            aantal_kinderen = int(aantal_kinderen)
        except (ValueError, TypeError):
            aantal_kinderen = 0
        
        opmerkingen = (
            body.get("opmerkingen") or 
            body.get("Opmerkingen") or 
            body.get("notes") or 
            body.get("Notes") or 
            body.get("message") or 
            ""
        )
        
        # Haal UTM tracking data op (AFL UTM Tracker plugin)
        # Veld '7' en '10' bevatten UTM data volgens context
        # Probeer verschillende mogelijke veldnamen/nummers
        utm_source = (
            body.get("utm_source") or
            body.get("7") or  # Mogelijk UTM source veld
            body.get("utm_source_field") or
            None
        )
        utm_medium = (
            body.get("utm_medium") or
            body.get("utm_medium_field") or
            None
        )
        utm_campaign = (
            body.get("utm_campaign") or
            body.get("utm_campaign_field") or
            None
        )
        utm_content = (
            body.get("utm_content") or
            body.get("10") or  # Mogelijk UTM content veld
            body.get("utm_content_field") or
            None
        )
        
        # Als veld '7' of '10' een JSON string is, parse deze
        if isinstance(utm_source, str) and (utm_source.startswith("{") or utm_source.startswith("[")):
            try:
                import json
                utm_data = json.loads(utm_source)
                if isinstance(utm_data, dict):
                    utm_source = utm_data.get("source") or utm_source
                    utm_medium = utm_data.get("medium") or utm_medium
                    utm_campaign = utm_data.get("campaign") or utm_campaign
                    utm_content = utm_data.get("content") or utm_content
            except:
                pass
        
        if isinstance(utm_content, str) and (utm_content.startswith("{") or utm_content.startswith("[")):
            try:
                import json
                utm_data = json.loads(utm_content)
                if isinstance(utm_data, dict):
                    utm_source = utm_data.get("source") or utm_source
                    utm_medium = utm_data.get("medium") or utm_medium
                    utm_campaign = utm_data.get("campaign") or utm_campaign
                    utm_content = utm_data.get("content") or utm_content
            except:
                pass
        
        # Maak order aan
        try:
            cur.execute("""
                INSERT INTO orders (
                    ordernummer, order_datum, leverdatum,
                    status, portaal_status, type_naam,
                    klant_id, plaats, aantal_personen, aantal_kinderen,
                    ordertype, opmerkingen,
                    utm_source, utm_medium, utm_campaign, utm_content,
                    totaal_bedrag, bedrag_excl_btw, bedrag_btw
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                utm_source,  # utm_source
                utm_medium,  # utm_medium
                utm_campaign,  # utm_campaign
                utm_content,  # utm_content
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
