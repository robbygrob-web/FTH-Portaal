"""
Webhook endpoints voor externe systemen.
"""
import os
import logging
import uuid
import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Request, HTTPException, Header, Query
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
    # Format: FTHYYYYMMDDXXXX (zonder streepjes)
    return "FTH" + datetime.now().strftime("%Y%m%d") + str(random.randint(1000, 9999))


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
    body = await request.body()
    print(f"GRAVITY RAW PAYLOAD: {body.decode()}")
    
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
        
        # Haal Gravity Forms referentie op (entry_id of entryId)
        gf_referentie = (
            body.get("entry_id") or
            body.get("entryId") or
            body.get("entry") or
            body.get("id") or
            None
        )
        if gf_referentie:
            _LOG.info(f"Gravity Forms referentie gevonden: {gf_referentie}")
        
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
        
        # Update contact adresvelden
        try:
            adres = body.get("29.1") or None
            postcode = body.get("29.5") or None
            land = body.get("29.6") or None
            
            if adres or postcode or land:
                cur.execute("""
                    UPDATE contacten 
                    SET adres = COALESCE(%s, adres),
                        postcode = COALESCE(%s, postcode),
                        land = COALESCE(%s, land)
                    WHERE id = %s
                """, (adres, postcode, land, contact_id))
                conn.commit()
                _LOG.info(f"Contact adresvelden bijgewerkt voor contact {contact_id}")
        except psycopg2.Error as e:
            _LOG.warning(f"Fout bij updaten contact adresvelden: {e}")
            # Niet kritiek, doorgaan met order aanmaken
        
        # Stap 2: Maak order aan
        # Gravity Forms veld mapping:
        # - Datum: veld '48'
        # - Locatie: veld '29.3' (stad)
        # - Aantal personen: veld '68'
        
        # Parse datum/tijd evenement (veld 48 + 63)
        event_date_str = body.get("48")  # Datum veld
        event_time_str = body.get("63")  # Tijd veld
        
        leverdatum = None
        if event_date_str:
            try:
                # Combineer datum en tijd
                if event_time_str:
                    # Combineer datum en tijd
                    combined_datetime = f"{event_date_str} {event_time_str}"
                    # Probeer verschillende datum/tijd formaten
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M"]:
                        try:
                            leverdatum = datetime.strptime(combined_datetime, fmt)
                            break
                        except ValueError:
                            continue
                
                # Als alleen datum, probeer datum formaten
                if not leverdatum:
                    for fmt in ["%Y-%m-%d", "%d-%m-%Y"]:
                        try:
                            leverdatum = datetime.strptime(str(event_date_str), fmt)
                            break
                        except ValueError:
                            continue
                
                if not leverdatum:
                    _LOG.warning(f"Kon datum niet parsen: {event_date_str} / {event_time_str}")
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
        
        aantal_kinderen = body.get("80") or 0
        try:
            aantal_kinderen = int(aantal_kinderen)
        except (ValueError, TypeError):
            aantal_kinderen = 0
        
        opmerkingen = body.get("31") or ""
        
        # Haal prijsbedragen op (veld '7' en '10' bevatten prijsdata)
        # Probeer verschillende mogelijke veldnamen voor totaal bedrag
        totaal_bedrag_raw = (
            body.get("7") or  # Veld '7' bevat totaal bedrag
            body.get("totaal_bedrag") or
            body.get("Totaal bedrag") or
            body.get("total") or
            body.get("Total") or
            0
        )
        
        # Probeer prijsbedrag te converteren naar float
        try:
            totaal_bedrag = float(totaal_bedrag_raw)
        except (ValueError, TypeError):
            totaal_bedrag = 0.00
        
        # Als veld '10' ook een prijs is, gebruik de hoogste waarde
        prijs_veld_10 = (
            body.get("10") or  # Veld '10' bevat mogelijk ook prijs
            0
        )
        try:
            prijs_veld_10_float = float(prijs_veld_10)
            # Gebruik de hoogste waarde als beide gevuld zijn
            if prijs_veld_10_float > totaal_bedrag:
                totaal_bedrag = prijs_veld_10_float
        except (ValueError, TypeError):
            pass
        
        # Prijs wordt berekend na het toevoegen van artikelen
        # Initieel op 0, wordt geupdate na artikel toevoeging
        bedrag_excl_btw = 0.00
        bedrag_btw = 0.00
        totaal_bedrag_calc = 0.00
        
        # Haal UTM tracking data op (AFL UTM Tracker plugin)
        # UTM data komt uit directe veldnamen, niet uit veldnummers
        utm_source = (
            body.get("utm_source") or
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
            body.get("utm_content_field") or
            None
        )
        
        # Als UTM velden JSON strings zijn, parse deze
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
                totaal_bedrag, bedrag_excl_btw, bedrag_btw,
                gf_referentie
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                "b2b" if body.get("81", "").lower() == "zakelijk" else "b2c",  # ordertype
                opmerkingen,
                utm_source,  # utm_source (echte UTM tracking data)
                utm_medium,  # utm_medium
                utm_campaign,  # utm_campaign
                utm_content,  # utm_content
                totaal_bedrag_calc,  # totaal_bedrag (berekend uit veld '7' of '10')
                bedrag_excl_btw,  # bedrag_excl_btw (berekend)
                bedrag_btw,  # bedrag_btw (berekend)
                gf_referentie  # gf_referentie (Gravity Forms entry ID)
            ))
            
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=500, detail="Kon order ID niet ophalen na insert")
            
            order_id = result[0]
            conn.commit()
            
            # Stap 3: Voeg artikelen toe aan order_artikelen
            try:
                # Helper functie om artikel op te halen op basis van naam
                def get_artikel_by_naam(naam):
                    cur.execute("""
                        SELECT id, naam, prijs_incl
                        FROM artikelen
                        WHERE naam = %s AND actief = TRUE
                        LIMIT 1
                    """, (naam,))
                    return cur.fetchone()
                
                # Helper functie om order_artikel regel toe te voegen
                def add_order_artikel(artikel_id, naam, aantal, prijs_incl):
                    cur.execute("""
                        INSERT INTO order_artikelen (
                            order_id, artikel_id, naam, aantal, prijs_incl
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (order_id, artikel_id, naam, aantal, float(prijs_incl)))
                    conn.commit()
                    _LOG.info(f"Order artikel toegevoegd: {naam} (aantal: {aantal}, prijs_incl: {prijs_incl})")
                
                # 1. Hoofdartikel (pakket) uit veld "69" (prioriteit) of "57.1"
                # Aantal = aantal_personen, prijs_incl = prijs per persoon
                artikel_naam = body.get("69", "").split("|")[0].strip()
                if not artikel_naam:
                    artikel_naam = body.get("57.1") or ""
                if artikel_naam:
                    artikel = get_artikel_by_naam(artikel_naam)
                    if artikel:
                        # Gebruik aantal_personen als aantal, prijs_incl uit artikel
                        pakket_aantal = Decimal(str(aantal_personen)) if aantal_personen > 0 else Decimal("1")
                        pakket_prijs_incl = Decimal(str(artikel[2]))  # prijs_incl per persoon
                        
                        add_order_artikel(
                            artikel[0],  # artikel_id
                            artikel[1],  # naam
                            pakket_aantal,  # aantal = aantal_personen
                            pakket_prijs_incl  # prijs_incl per persoon
                        )
                    else:
                        _LOG.warning(f"Artikel niet gevonden in artikelen tabel: {artikel_naam}")
                
                # 1b. Kinderpakket toevoegen als aantal_kinderen > 0
                if aantal_kinderen > 0:
                    kinderpakket_prijs_incl = Decimal("6.50")
                    add_order_artikel(
                        None,  # artikel_id (geen artikel in tabel)
                        "Kinderpakket",  # naam
                        Decimal(str(aantal_kinderen)),  # aantal
                        kinderpakket_prijs_incl  # prijs_incl per stuk
                    )
                
                # 2. Reiskosten altijd toevoegen
                reiskosten_artikel = get_artikel_by_naam("Reiskosten")
                reiskosten_prijs_incl = Decimal("75.00")
                if reiskosten_artikel:
                    reiskosten_prijs_incl = Decimal(str(reiskosten_artikel[2]))  # prijs_incl uit artikel
                    add_order_artikel(
                        reiskosten_artikel[0],  # artikel_id
                        reiskosten_artikel[1],  # naam
                        Decimal("1"),  # altijd 1 stuk
                        reiskosten_prijs_incl  # prijs_incl
                    )
                else:
                    # Als artikel niet gevonden: maak direct order_artikel regel aan
                    _LOG.warning("Reiskosten artikel niet gevonden in artikelen tabel, voeg direct toe aan order")
                    add_order_artikel(
                        None,  # artikel_id (NULL omdat artikel niet bestaat)
                        "Reiskosten",  # naam
                        Decimal("1"),  # aantal
                        reiskosten_prijs_incl  # prijs_incl
                    )
                
                # 3. Broodjes toevoegen als veld "79" gevuld is
                broodjes_veld = body.get("79")
                if broodjes_veld and broodjes_veld.strip() and broodjes_veld != "0":
                    # Als gevuld: aantal = aantal_personen
                    broodjes_artikel = get_artikel_by_naam("Broodjes")
                    if broodjes_artikel:
                        broodjes_prijs_incl = Decimal(str(broodjes_artikel[2]))  # prijs_incl uit artikel
                        broodjes_aantal = Decimal(str(aantal_personen)) if aantal_personen > 0 else Decimal("1")
                        add_order_artikel(
                            broodjes_artikel[0],  # artikel_id
                            broodjes_artikel[1],  # naam
                            broodjes_aantal,  # aantal = aantal_personen
                            broodjes_prijs_incl  # prijs_incl
                        )
                    else:
                        _LOG.warning("Broodjes artikel niet gevonden in artikelen tabel")
                
                # 4. Drankjes toevoegen als veld "44" gevuld is
                drankjes_veld = body.get("44")
                if drankjes_veld and drankjes_veld.strip() and drankjes_veld != "0":
                    # Als gevuld: aantal = aantal_personen
                    drankjes_artikel = get_artikel_by_naam("Drankjes")
                    if drankjes_artikel:
                        drankjes_prijs_incl = Decimal(str(drankjes_artikel[2]))  # prijs_incl uit artikel
                        drankjes_aantal = Decimal(str(aantal_personen)) if aantal_personen > 0 else Decimal("1")
                        add_order_artikel(
                            drankjes_artikel[0],  # artikel_id
                            drankjes_artikel[1],  # naam
                            drankjes_aantal,  # aantal = aantal_personen
                            drankjes_prijs_incl  # prijs_incl
                        )
                    else:
                        _LOG.warning("Drankjes artikel niet gevonden in artikelen tabel")
                
                # Webhook slaat alleen artikelen op, geen totaal berekeningen
                _LOG.info(f"[WEBHOOK] Order {ordernummer} aangemaakt met artikelen")
                _LOG.info(f"  Aantal personen: {aantal_personen}")
                _LOG.info(f"  Aantal kinderen: {aantal_kinderen}")
                _LOG.info(f"  Artikelen opgeslagen in order_artikelen")
                        
            except psycopg2.Error as e:
                _LOG.warning(f"Fout bij toevoegen order artikelen: {e}")
                # Niet kritiek, doorgaan met order
            
            # Verbeterde logging voor nieuwe orders
            _LOG.info("=" * 60)
            _LOG.info(f"[GRAVITY WEBHOOK] Nieuwe order ontvangen en opgeslagen!")
            _LOG.info(f"  Order ID: {order_id}")
            _LOG.info(f"  Ordernummer: {ordernummer}")
            _LOG.info(f"  Contact ID: {contact_id}")
            _LOG.info(f"  Plaats: {plaats}")
            _LOG.info(f"  Aantal personen: {aantal_personen}")
            _LOG.info(f"  Aantal kinderen: {aantal_kinderen}")
            _LOG.info(f"  Leverdatum: {leverdatum}")
            # Totaal bedrag wordt getoond in prijsberekening sectie hierboven
            # Haal laatste waarden op uit database
            cur.execute("SELECT totaal_bedrag, bedrag_excl_btw, bedrag_btw FROM orders WHERE id = %s", (order_id,))
            order_totals = cur.fetchone()
            if order_totals:
                _LOG.info(f"  Totaal bedrag: €{float(order_totals[0]):,.2f}")
                _LOG.info(f"  Bedrag excl BTW: €{float(order_totals[1]):,.2f}")
                _LOG.info(f"  BTW bedrag: €{float(order_totals[2]):,.2f}")
            _LOG.info(f"  UTM Source: {utm_source or 'Geen'}")
            _LOG.info(f"  UTM Medium: {utm_medium or 'Geen'}")
            _LOG.info(f"  UTM Campaign: {utm_campaign or 'Geen'}")
            _LOG.info(f"  UTM Content: {utm_content or 'Geen'}")
            _LOG.info("=" * 60)
            
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


@router.post("/mollie")
async def mollie_webhook(request: Request):
    """Mollie betaling webhook - ontvangt betaling bevestigingen"""
    conn = None
    try:
        # Mollie stuurt form-encoded data (id=tr_xxxx), niet JSON
        form = await request.form()
        payment_id = form.get("id")
        
        # Fallback: probeer body direct te parsen als form data niet werkt
        if not payment_id:
            body = await request.body()
            body_str = body.decode()
            if "=" in body_str:
                payment_id = body_str.split("=")[1]
        
        if not payment_id:
            _LOG.warning("Mollie webhook zonder payment ID")
            raise HTTPException(status_code=400, detail="Payment ID ontbreekt")
        
        _LOG.info(f"Mollie webhook ontvangen voor payment: {payment_id}")
        
        # Haal payment op van Mollie
        from app.mollie_client import get_payment
        payment = get_payment(payment_id)
        
        payment_status = payment.get("status")
        
        # Connect naar database
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Als status = 'paid', controleer of payment ID matcht met actieve factuur
        if payment_status == "paid":
            # Zoek factuur op via payment ID
            cur.execute("""
                SELECT f.id, f.order_id, o.betaal_status
                FROM facturen f
                JOIN orders o ON o.id = f.order_id
                WHERE f.mollie_payment_id = %s
            """, (payment_id,))
            
            factuur = cur.fetchone()
            
            if not factuur:
                # Geen factuur gevonden met dit payment ID
                print(f"ONBEKEND PAYMENT: {payment_id} - geen factuur gevonden")
                _LOG.warning(f"ONBEKEND PAYMENT: {payment_id} - geen factuur gevonden")
                return JSONResponse({"status": "ok", "message": "Payment ID niet gevonden in facturen"})
            
            # Factuur gevonden - update betaalstatus
            order_id = factuur.get("order_id")
            factuur_id = factuur.get("id")
            
            cur.execute("""
                UPDATE orders
                SET betaal_status = 'betaald', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (order_id,))
            
            # Update factuur betalingsstatus
            cur.execute("""
                UPDATE facturen
                SET betalingsstatus = 'paid', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (factuur_id,))
            
            conn.commit()
            
            # Log in mail_logs
            cur.execute("""
                INSERT INTO mail_logs (order_id, onderwerp, status, foutmelding)
                VALUES (%s, %s, %s, %s)
            """, (
                order_id,
                f"Mollie betaling bevestigd - Payment {payment_id}",
                "success",
                None
            ))
            conn.commit()
            
            print(f"BETAALD: {payment_id} matched factuur {factuur_id} voor order {order_id}")
            _LOG.info(f"Betaling bevestigd voor order {order_id} - Payment {payment_id} matched factuur {factuur_id}")
        
        return JSONResponse({"status": "ok"})
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Mollie webhook fout: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        if conn:
            cur.close()
            conn.close()
