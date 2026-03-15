"""
Admin endpoints voor database setup, import en dashboard.
"""
import os
import logging
import traceback
import uuid
import random
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Header, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from app.odoo_client import get_odoo_client
from app.config import SESSION_SECRET
from app.mail import stuur_mail

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/ping")
async def ping():
    return {"status": "ok"}

# Setup router voor init-db endpoint
setup_router = APIRouter(prefix="/admin/setup", tags=["admin"])


def verify_admin_token(authorization: Optional[str] = Header(None)):
    """Verifieer Bearer token met SESSION_SECRET"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header ontbreekt")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Ongeldig authorization format. Gebruik: Bearer <token>")
    
    token = authorization.replace("Bearer ", "").strip()
    
    if token != SESSION_SECRET:
        raise HTTPException(status_code=403, detail="Ongeldig token")
    
    return True


def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL niet gevonden in environment variabelen")
    return database_url


def parse_date(date_str):
    """Parse Odoo date string naar Python datetime"""
    if not date_str:
        return None
    try:
        if len(date_str) > 10:
            return datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        else:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except Exception as e:
        _LOG.warning(f"Kon datum niet parsen '{date_str}': {e}")
        return None


def calculate_btw_percentage(price_excl, price_incl):
    """Bereken BTW percentage uit prijzen"""
    if not price_excl or price_excl == 0:
        return 9.00  # Default
    btw_amount = price_incl - price_excl
    return round((btw_amount / price_excl) * 100, 2)


def verify_admin_session(request: Request):
    """Verifieer admin sessie via Authorization header of query param"""
    # Check Authorization header (voor API calls)
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        if token == SESSION_SECRET:
            return True
    
    # Check query param (voor GET requests in browser)
    token = request.query_params.get("token")
    if token and token == SESSION_SECRET:
        return True
    
    # Check session (voor toekomstige sessie-based auth)
    if request.session.get("is_admin"):
        return True
    
    raise HTTPException(status_code=401, detail="Admin toegang vereist. Voeg ?token=YOUR_SESSION_SECRET toe aan de URL.")


@setup_router.post("/add-betaal-status-column")
async def add_betaal_status_column(verified: bool = Depends(verify_admin_token)):
    """
    Tijdelijk endpoint om betaal_status kolom toe te voegen aan orders tabel.
    Vereist Bearer token authenticatie met SESSION_SECRET.
    """
    database_url = get_database_url()
    conn = None
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check of kolom al bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders' AND column_name = 'betaal_status'
        """)
        
        if cur.fetchone():
            return JSONResponse({
                "success": True,
                "message": "Kolom betaal_status bestaat al"
            })
        
        # Voeg kolom toe
        cur.execute("""
            ALTER TABLE orders
            ADD COLUMN betaal_status VARCHAR(50) DEFAULT 'onbetaald'
        """)
        
        conn.commit()
        
        return JSONResponse({
            "success": True,
            "message": "Kolom betaal_status succesvol toegevoegd aan orders tabel"
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        error_message = str(e) if str(e) else repr(e)
        error_traceback = traceback.format_exc()
        full_error = f"{error_message}\n\nTraceback:\n{error_traceback}"
        _LOG.error(f"Fout bij toevoegen betaal_status kolom: {full_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij toevoegen kolom: {full_error}")
    finally:
        if conn:
            cur.close()
            conn.close()


@setup_router.post("/add-facturen-mollie-columns")
async def add_facturen_mollie_columns(verified: bool = Depends(verify_admin_token)):
    """
    Tijdelijk endpoint om mollie_payment_id en mollie_checkout_url kolommen toe te voegen aan facturen tabel.
    Vereist Bearer token authenticatie met SESSION_SECRET.
    """
    database_url = get_database_url()
    conn = None
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check mollie_payment_id
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'facturen' AND column_name = 'mollie_payment_id'
        """)
        
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE facturen
                ADD COLUMN mollie_payment_id VARCHAR(100)
            """)
        
        # Check mollie_checkout_url
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'facturen' AND column_name = 'mollie_checkout_url'
        """)
        
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE facturen
                ADD COLUMN mollie_checkout_url TEXT
            """)
        
        conn.commit()
        
        return JSONResponse({
            "success": True,
            "message": "Mollie kolommen succesvol toegevoegd aan facturen tabel"
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        error_message = str(e) if str(e) else repr(e)
        error_traceback = traceback.format_exc()
        full_error = f"{error_message}\n\nTraceback:\n{error_traceback}"
        _LOG.error(f"Fout bij toevoegen Mollie kolommen: {full_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij toevoegen kolommen: {full_error}")
    finally:
        if conn:
            cur.close()
            conn.close()


@setup_router.post("/add-gf-referentie-column")
async def add_gf_referentie_column(verified: bool = Depends(verify_admin_token)):
    """
    Tijdelijk endpoint om gf_referentie kolom toe te voegen aan orders tabel.
    Vereist Bearer token authenticatie met SESSION_SECRET.
    """
    database_url = get_database_url()
    conn = None
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check of kolom al bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders' AND column_name = 'gf_referentie'
        """)
        
        if cur.fetchone():
            return JSONResponse({
                "success": True,
                "message": "Kolom gf_referentie bestaat al"
            })
        
        # Voeg kolom toe
        cur.execute("""
            ALTER TABLE orders
            ADD COLUMN gf_referentie VARCHAR(100)
        """)
        
        conn.commit()
        
        return JSONResponse({
            "success": True,
            "message": "Kolom gf_referentie succesvol toegevoegd aan orders tabel"
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        error_message = str(e) if str(e) else repr(e)
        error_traceback = traceback.format_exc()
        full_error = f"{error_message}\n\nTraceback:\n{error_traceback}"
        _LOG.error(f"Fout bij toevoegen gf_referentie kolom: {full_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij toevoegen kolom: {full_error}")
    finally:
        if conn:
            cur.close()
            conn.close()


@setup_router.post("/add-bevestig-token-column")
async def add_bevestig_token_column(verified: bool = Depends(verify_admin_token)):
    """
    Tijdelijk endpoint om bevestig_token kolom toe te voegen aan orders tabel.
    Vereist Bearer token authenticatie met SESSION_SECRET.
    """
    database_url = get_database_url()
    conn = None
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check of kolom al bestaat
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders' AND column_name = 'bevestig_token'
        """)
        
        if cur.fetchone():
            return JSONResponse({
                "success": True,
                "message": "Kolom bevestig_token bestaat al"
            })
        
        # Voeg kolom toe
        cur.execute("""
            ALTER TABLE orders
            ADD COLUMN bevestig_token VARCHAR(64) UNIQUE
        """)
        
        conn.commit()
        
        return JSONResponse({
            "success": True,
            "message": "Kolom bevestig_token succesvol toegevoegd aan orders tabel"
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        error_message = str(e) if str(e) else repr(e)
        error_traceback = traceback.format_exc()
        full_error = f"{error_message}\n\nTraceback:\n{error_traceback}"
        _LOG.error(f"Fout bij toevoegen bevestig_token kolom: {full_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij toevoegen kolom: {full_error}")
    finally:
        if conn:
            cur.close()
            conn.close()


@setup_router.get("/toon-orders")
async def toon_orders(request: Request):
    """Tijdelijk endpoint om alle orders te tonen"""
    token = request.query_params.get("token")
    if token != SESSION_SECRET:
        raise HTTPException(status_code=403)
    
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                o.id,
                o.ordernummer,
                c.naam as klant_naam,
                o.created_at as aangemaakt_op,
                COALESCE((
                    SELECT SUM(oa.prijs_incl * oa.aantal)
                    FROM order_artikelen oa
                    WHERE oa.order_id = o.id
                ), 0) as totaal_bedrag,
                o.status,
                o.portaal_status
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            ORDER BY o.created_at DESC
        """)
        
        orders = cur.fetchall()
        
        # Converteer naar dict lijst
        result = []
        for order in orders:
            result.append({
                "id": str(order.get("id")),
                "ordernummer": order.get("ordernummer"),
                "klant_naam": order.get("klant_naam"),
                "aangemaakt_op": str(order.get("aangemaakt_op")) if order.get("aangemaakt_op") else None,
                "totaal_bedrag": float(order.get("totaal_bedrag", 0)) if order.get("totaal_bedrag") else 0.0,
                "status": order.get("status"),
                "portaal_status": order.get("portaal_status")
            })
        
        return JSONResponse({"orders": result, "aantal": len(result)})
        
    except Exception as e:
        _LOG.error(f"Fout bij ophalen orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()


@setup_router.get("/toon-order-detail")
async def toon_order_detail(request: Request):
    """Tijdelijk endpoint om alle kolommen van één order te tonen"""
    token = request.query_params.get("token")
    if token != SESSION_SECRET:
        raise HTTPException(status_code=403)
    
    order_id = request.query_params.get("id", "69b29b70-ceb2-4d07-887a-6bf4491e524d")
    
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM orders 
            WHERE id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        
        if not order:
            return JSONResponse({"error": "Order niet gevonden", "order_id": order_id}, status_code=404)
        
        # Converteer naar dict (RealDictCursor geeft al dict terug)
        result = dict(order)
        
        # Converteer UUID en datetime naar strings voor JSON serialisatie
        for key, value in result.items():
            if value is None:
                continue
            if hasattr(value, 'isoformat'):  # datetime/date
                result[key] = value.isoformat()
            elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool)):
                result[key] = str(value)
        
        return JSONResponse({"order": result})
        
    except Exception as e:
        _LOG.error(f"Fout bij ophalen order detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()


@setup_router.post("/init-db")
async def init_database(verified: bool = Depends(verify_admin_token)):
    """
    Tijdelijk endpoint om order_artikelen tabel aan te maken en 10 orders te importeren.
    Vereist Bearer token authenticatie met SESSION_SECRET.
    """
    database_url = get_database_url()
    conn = None
    
    try:
        # Connect naar PostgreSQL
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Stap 1: Maak order_artikelen tabel aan (als die nog niet bestaat)
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'order_artikelen'
            )
        """)
        table_exists = cur.fetchone()["exists"]
        
        if not table_exists:
            _LOG.info("Aanmaken order_artikelen tabel...")
            cur.execute("""
                CREATE TABLE order_artikelen (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Relaties
                    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    artikel_id UUID REFERENCES artikelen(id) ON DELETE SET NULL,
                    
                    -- Orderline informatie
                    naam VARCHAR(500) NOT NULL,
                    aantal DECIMAL(10, 2) NOT NULL DEFAULT 1.00,
                    prijs_excl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                    btw_pct DECIMAL(5, 2) NOT NULL DEFAULT 9.00,
                    btw_bedrag DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                    prijs_incl DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                    
                    -- Odoo sync (tijdelijk)
                    odoo_id INTEGER UNIQUE,
                    
                    CONSTRAINT order_artikelen_order_id_fk FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    CONSTRAINT order_artikelen_artikel_id_fk FOREIGN KEY (artikel_id) REFERENCES artikelen(id) ON DELETE SET NULL
                );
            """)
            
            cur.execute("CREATE INDEX idx_order_artikelen_order_id ON order_artikelen(order_id);")
            cur.execute("CREATE INDEX idx_order_artikelen_artikel_id ON order_artikelen(artikel_id);")
            cur.execute("CREATE INDEX idx_order_artikelen_odoo_id ON order_artikelen(odoo_id);")
            cur.execute("COMMENT ON TABLE order_artikelen IS 'Order regels (artikelen per order)';")
            
            conn.commit()
            table_created = True
        else:
            _LOG.info("Tabel order_artikelen bestaat al")
            table_created = False
        
        # Stap 2: Connect naar Odoo
        client = get_odoo_client()
        
        # Stap 3: Haal 10 recente orders op (alleen essentiële velden)
        orders = client.execute_kw(
            "sale.order",
            "search_read",
            [[("state", "in", ["sent", "sale"])]],
            {
                "fields": [
                    "id", "name", "date_order", "state", "partner_id",
                    "commitment_date", "amount_total", "amount_untaxed", 
                    "amount_tax", "order_line"
                ],
                "order": "id desc",
                "limit": 10
            }
        )
        
        if not orders:
            return JSONResponse({
                "success": True,
                "table_created": table_created,
                "message": "Geen orders gevonden om te importeren",
                "imported": {
                    "partners": 0,
                    "orders": 0,
                    "order_artikelen": 0
                }
            })
        
        # Stap 4: Verzamel partner IDs en haal partners op
        partner_ids = []
        for order in orders:
            if order.get("partner_id"):
                partner_id = order["partner_id"][0] if isinstance(order["partner_id"], (list, tuple)) else order["partner_id"]
                if partner_id not in partner_ids:
                    partner_ids.append(partner_id)
        
        partners = []
        if partner_ids:
            partners = client.execute_kw(
                "res.partner",
                "read",
                partner_ids,
                {
                    "fields": [
                        "id", "name", "email", "phone", "street", "zip", "city", "country_id",
                        "vat", "is_company", "x_studio_portaal_partner", "x_studio_partner_commissie"
                    ]
                }
            )
        
        # Stap 5: Import partners
        partner_lookup = {}
        imported_partners = 0
        
        for partner in partners:
            odoo_id = partner["id"]
            country_code = "NL"
            if partner.get("country_id"):
                country_name = partner["country_id"][1] if isinstance(partner["country_id"], (list, tuple)) else str(partner["country_id"])
                country_code = country_name[:2].upper() if country_name else "NL"
            
            partner_data = {
                "odoo_id": odoo_id,
                "naam": partner.get("name", ""),
                "email": partner.get("email"),
                "telefoon": partner.get("phone"),
                "straat": partner.get("street"),
                "postcode": partner.get("zip"),
                "stad": partner.get("city"),
                "land_code": country_code,
                "btw_nummer": partner.get("vat"),
                "bedrijfstype": "company" if partner.get("is_company") else "person",
                "is_portaal_partner": bool(partner.get("x_studio_portaal_partner", False)),
                "partner_commissie": float(partner.get("x_studio_partner_commissie", 0)) if partner.get("x_studio_partner_commissie") else 0.00
            }
            
            cur.execute("""
                INSERT INTO contacten (
                    odoo_id, naam, email, telefoon, straat, postcode, stad, land_code,
                    btw_nummer, bedrijfstype, is_portaal_partner, partner_commissie
                ) VALUES (
                    %(odoo_id)s, %(naam)s, %(email)s, %(telefoon)s, %(straat)s, %(postcode)s,
                    %(stad)s, %(land_code)s, %(btw_nummer)s, %(bedrijfstype)s,
                    %(is_portaal_partner)s, %(partner_commissie)s
                )
                ON CONFLICT (odoo_id) DO UPDATE SET
                    naam = EXCLUDED.naam,
                    email = EXCLUDED.email,
                    telefoon = EXCLUDED.telefoon,
                    straat = EXCLUDED.straat,
                    postcode = EXCLUDED.postcode,
                    stad = EXCLUDED.stad,
                    land_code = EXCLUDED.land_code,
                    btw_nummer = EXCLUDED.btw_nummer,
                    bedrijfstype = EXCLUDED.bedrijfstype,
                    is_portaal_partner = EXCLUDED.is_portaal_partner,
                    partner_commissie = EXCLUDED.partner_commissie,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, odoo_id
            """, partner_data)
            
            result = cur.fetchone()
            if result:
                partner_lookup[odoo_id] = result["id"]
                imported_partners += 1
        
        conn.commit()
        
        # Stap 6: Verzamel order_line IDs
        all_line_ids = []
        for order in orders:
            if order.get("order_line"):
                all_line_ids.extend(order["order_line"])
        
        # Haal order_lines op
        order_lines = []
        if all_line_ids:
            order_lines = client.execute_kw(
                "sale.order.line",
                "read",
                all_line_ids,
                {
                    "fields": [
                        "id", "order_id", "product_id", "name", "product_uom_qty",
                        "price_unit", "price_subtotal", "price_subtotal_incl", "tax_id"
                    ]
                }
            )
        
        # Stap 7: Import orders
        order_lookup = {}
        imported_orders = 0
        
        for order in orders:
            odoo_id = order["id"]
            partner_id_tuple = order.get("partner_id")
            partner_odoo_id = partner_id_tuple[0] if partner_id_tuple and isinstance(partner_id_tuple, (list, tuple)) else None
            
            klant_id = partner_lookup.get(partner_odoo_id) if partner_odoo_id else None
            
            order_datum = parse_date(order.get("date_order"))
            leverdatum = parse_date(order.get("commitment_date"))
            
            state = order.get("state", "")
            status = "sent" if state == "sent" else "sale"
            type_naam = "Offerte" if state == "sent" else "Verkooporder"
            
            order_data = {
                "odoo_id": odoo_id,
                "ordernummer": order.get("name", ""),
                "order_datum": order_datum,
                "leverdatum": leverdatum,
                "status": status,
                "portaal_status": "nieuw",
                "type_naam": type_naam,
                "klant_id": klant_id,
                "totaal_bedrag": float(order.get("amount_total", 0)) if order.get("amount_total") else 0.00,
                "bedrag_excl_btw": float(order.get("amount_untaxed", 0)) if order.get("amount_untaxed") else 0.00,
                "bedrag_btw": float(order.get("amount_tax", 0)) if order.get("amount_tax") else 0.00,
                "plaats": None,
                "aantal_personen": 0,
                "aantal_kinderen": 0,
                "ordertype": None,
                "betaaltermijn_id": None,
                "betaaltermijn_naam": None,
                "opmerkingen": None,
                "utm_source": None,
                "utm_medium": None,
                "utm_campaign": None,
                "utm_content": None
            }
            
            cur.execute("""
                INSERT INTO orders (
                    odoo_id, ordernummer, order_datum, leverdatum, status, portaal_status,
                    type_naam, klant_id, totaal_bedrag, bedrag_excl_btw, bedrag_btw,
                    plaats, aantal_personen, aantal_kinderen, ordertype, betaaltermijn_id,
                    betaaltermijn_naam, opmerkingen, utm_source, utm_medium, utm_campaign, utm_content
                ) VALUES (
                    %(odoo_id)s, %(ordernummer)s, %(order_datum)s, %(leverdatum)s, %(status)s,
                    %(portaal_status)s, %(type_naam)s, %(klant_id)s, %(totaal_bedrag)s,
                    %(bedrag_excl_btw)s, %(bedrag_btw)s, %(plaats)s, %(aantal_personen)s,
                    %(aantal_kinderen)s, %(ordertype)s, %(betaaltermijn_id)s, %(betaaltermijn_naam)s,
                    %(opmerkingen)s, %(utm_source)s, %(utm_medium)s, %(utm_campaign)s, %(utm_content)s
                )
                ON CONFLICT (odoo_id) DO UPDATE SET
                    ordernummer = EXCLUDED.ordernummer,
                    order_datum = EXCLUDED.order_datum,
                    leverdatum = EXCLUDED.leverdatum,
                    status = EXCLUDED.status,
                    type_naam = EXCLUDED.type_naam,
                    klant_id = EXCLUDED.klant_id,
                    totaal_bedrag = EXCLUDED.totaal_bedrag,
                    bedrag_excl_btw = EXCLUDED.bedrag_excl_btw,
                    bedrag_btw = EXCLUDED.bedrag_btw,
                    plaats = EXCLUDED.plaats,
                    aantal_personen = EXCLUDED.aantal_personen,
                    aantal_kinderen = EXCLUDED.aantal_kinderen,
                    ordertype = EXCLUDED.ordertype,
                    betaaltermijn_id = EXCLUDED.betaaltermijn_id,
                    betaaltermijn_naam = EXCLUDED.betaaltermijn_naam,
                    opmerkingen = EXCLUDED.opmerkingen,
                    utm_source = EXCLUDED.utm_source,
                    utm_medium = EXCLUDED.utm_medium,
                    utm_campaign = EXCLUDED.utm_campaign,
                    utm_content = EXCLUDED.utm_content,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, odoo_id
            """, order_data)
            
            result = cur.fetchone()
            if result:
                order_lookup[odoo_id] = result["id"]
                imported_orders += 1
        
        conn.commit()
        
        # Stap 8: Import order_artikelen
        imported_lines = 0
        
        for line in order_lines:
            odoo_id = line["id"]
            order_id_tuple = line.get("order_id")
            order_odoo_id = order_id_tuple[0] if order_id_tuple and isinstance(order_id_tuple, (list, tuple)) else None
            
            order_id = order_lookup.get(order_odoo_id) if order_odoo_id else None
            if not order_id:
                continue
            
            artikel_id = None
            product_id_tuple = line.get("product_id")
            if product_id_tuple:
                product_odoo_id = product_id_tuple[0] if isinstance(product_id_tuple, (list, tuple)) else product_id_tuple
                cur.execute("SELECT id FROM artikelen WHERE odoo_id = %s", (product_odoo_id,))
                artikel_result = cur.fetchone()
                if artikel_result:
                    artikel_id = artikel_result["id"]
            
            price_excl = float(line.get("price_unit", 0)) if line.get("price_unit") else 0.00
            price_subtotal = float(line.get("price_subtotal", 0)) if line.get("price_subtotal") else 0.00
            price_incl = float(line.get("price_subtotal_incl", 0)) if line.get("price_subtotal_incl") else 0.00
            
            if not price_incl and price_subtotal:
                price_incl = price_subtotal * 1.09
            
            btw_bedrag = price_incl - price_subtotal if price_incl and price_subtotal else 0.00
            btw_pct = calculate_btw_percentage(price_subtotal, price_incl)
            
            line_data = {
                "odoo_id": odoo_id,
                "order_id": order_id,
                "artikel_id": artikel_id,
                "naam": line.get("name", ""),
                "aantal": float(line.get("product_uom_qty", 1)) if line.get("product_uom_qty") else 1.00,
                "prijs_excl": price_excl,
                "btw_pct": btw_pct,
                "btw_bedrag": btw_bedrag,
                "prijs_incl": price_incl
            }
            
            cur.execute("""
                INSERT INTO order_artikelen (
                    odoo_id, order_id, artikel_id, naam, aantal, prijs_excl, btw_pct,
                    btw_bedrag, prijs_incl
                ) VALUES (
                    %(odoo_id)s, %(order_id)s, %(artikel_id)s, %(naam)s, %(aantal)s,
                    %(prijs_excl)s, %(btw_pct)s, %(btw_bedrag)s, %(prijs_incl)s
                )
                ON CONFLICT (odoo_id) DO UPDATE SET
                    order_id = EXCLUDED.order_id,
                    artikel_id = EXCLUDED.artikel_id,
                    naam = EXCLUDED.naam,
                    aantal = EXCLUDED.aantal,
                    prijs_excl = EXCLUDED.prijs_excl,
                    btw_pct = EXCLUDED.btw_pct,
                    btw_bedrag = EXCLUDED.btw_bedrag,
                    prijs_incl = EXCLUDED.prijs_incl
            """, line_data)
            
            imported_lines += 1
        
        conn.commit()
        
        return JSONResponse({
            "success": True,
            "table_created": table_created,
            "message": "Database setup en import voltooid",
            "imported": {
                "partners": imported_partners,
                "orders": imported_orders,
                "order_artikelen": imported_lines
            }
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        error_message = str(e) if str(e) else repr(e)
        error_traceback = traceback.format_exc()
        full_error = f"{error_message}\n\nTraceback:\n{error_traceback}"
        _LOG.error(f"Fout tijdens database setup: {full_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout tijdens database setup: {full_error}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, verified: bool = Depends(verify_admin_session)):
    """Admin dashboard met aanvragen lijst"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal orders op met contact informatie en partner
        # Totaal wordt berekend uit order_artikelen via subquery
        cur.execute("""
            SELECT 
                o.id,
                o.ordernummer,
                o.order_datum,
                o.leverdatum,
                o.status,
                o.portaal_status,
                o.betaal_status,
                CASE WHEN o.status = 'sale' 
                     AND o.portaal_status IN ('claimed','transfer') 
                     THEN 'definitief'
                     ELSE o.status END as offerte_status_label,
                COALESCE((
                    SELECT SUM(oa.prijs_incl * oa.aantal)
                    FROM order_artikelen oa
                    WHERE oa.order_id = o.id
                ), 0) as totaal_bedrag,
                o.plaats,
                o.aantal_personen,
                o.aantal_kinderen,
                o.ordertype,
                o.opmerkingen,
                c.id as klant_id,
                c.naam as klant_naam,
                c.email as klant_email,
                c.telefoon as klant_telefoon,
                p.naam as partner_naam
            FROM orders o
            LEFT JOIN contacten c ON o.klant_id = c.id
            LEFT JOIN contacten p ON o.contractor_id = p.id
            ORDER BY o.created_at DESC
            LIMIT 100
        """)
        
        orders = cur.fetchall()
        
        # Format leverdatum
        def format_datetime(dt):
            if not dt:
                return "-"
            if isinstance(dt, str):
                return dt[:16]  # YYYY-MM-DD HH:MM
            return dt.strftime("%Y-%m-%d %H:%M")
        
        # Format status
        def format_portaal_status(status):
            status_map = {
                "nieuw": ("Nieuw", "#3498db"),
                "beschikbaar": ("Beschikbaar", "#27ae60"),
                "claimed": ("Geclaimd", "#e67e22"),
                "transfer": ("Transfer", "#9b59b6")
            }
            return status_map.get(status, (status, "#999"))
        
        def format_order_status(status):
            status_map = {
                "sent": ("Offerte", "#3498db"),
                "sale": ("Verkooporder", "#27ae60"),
                "definitief": ("Definitief", "#27ae60"),  # Groen voor definitief
                "draft": ("Concept", "#999"),
                "cancel": ("Geannuleerd", "#dc3545")
            }
            return status_map.get(status, (status, "#999"))
        
        def format_betaal_status(status):
            if status == "betaald":
                return ('<span style="background:#27ae60;color:white;padding:4px 8px;border-radius:4px;font-size:12px;">Betaald ✓</span>', "#27ae60")
            elif status == "factuur_verstuurd":
                return ('<span style="background:#e67e22;color:white;padding:4px 8px;border-radius:4px;font-size:12px;">Factuur verstuurd</span>', "#e67e22")
            elif status == "link_verlopen":
                return ('<span style="background:#95a5a6;color:white;padding:4px 8px;border-radius:4px;font-size:12px;">Link verlopen</span>', "#95a5a6")
            else:
                return ('<span style="color:#999;">-</span>', "#999")
        
        # Build HTML table rows
        table_rows = ""
        for order in orders:
            portaal_status_text, portaal_status_color = format_portaal_status(order.get("portaal_status", "nieuw"))
            # Gebruik offerte_status_label (kan 'definitief' zijn) in plaats van status
            offerte_status_label = order.get("offerte_status_label", order.get("status", "draft"))
            order_status_text, order_status_color = format_order_status(offerte_status_label)
            
            ordernummer = order.get("ordernummer") or "-"
            klant_naam = order.get("klant_naam") or "-"
            klant_id = order.get("klant_id")
            plaats = order.get("plaats") or "-"
            leverdatum = format_datetime(order.get("leverdatum"))
            personen = order.get("aantal_personen", 0)
            kinderen = order.get("aantal_kinderen", 0)
            totaal = float(order.get("totaal_bedrag", 0)) if order.get("totaal_bedrag") else 0.0
            partner_naam = order.get("partner_naam") or "-"
            
            # Bereken BTW (9%): BTW = totaal - (totaal / 1.09)
            btw_bedrag = round(totaal - (totaal / 1.09), 2) if totaal > 0 else 0.0
            
            # Bereken partnerprijs: commissie over totaal (15% tot 575, daarna 20%)
            # Geen ordertype filter - altijd dezelfde berekening
            commissie_deel_1 = min(totaal, 575) * 0.15
            commissie_deel_2 = max(totaal - 575, 0) * 0.20
            commissie_totaal = commissie_deel_1 + commissie_deel_2
            prijs_partner = round(totaal - commissie_totaal, 2)
            
            order_id = str(order.get("id"))
            klant_link = f"/admin/klant/{klant_id}?token={SESSION_SECRET}" if klant_id else "#"
            betaal_status_html, _ = format_betaal_status(order.get("betaal_status"))
            table_rows += f"""
            <tr>
                <td><a href="/admin/order/{order_id}?token={SESSION_SECRET}" style="color:#333;text-decoration:none;font-weight:500;">{ordernummer}</a></td>
                <td><a href="{klant_link}" style="color:#333;text-decoration:none;font-weight:500;">{klant_naam}</a></td>
                <td>{plaats}</td>
                <td>{leverdatum}</td>
                <td>{personen} / {kinderen}</td>
                <td>€ {totaal:,.2f}</td>
                <td>€ {btw_bedrag:,.2f}</td>
                <td>€ {prijs_partner:,.2f}</td>
                <td><span style="color:{portaal_status_color};">{portaal_status_text}</span></td>
                <td><span style="color:{order_status_color};">{order_status_text}</span></td>
                <td>{partner_naam}</td>
                <td>{betaal_status_html}</td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Admin - Aanvragen</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #fffdf2;
                    padding: 20px;
                }}
                .header {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                h1 {{
                    color: #333333;
                    font-size: 24px;
                }}
                .btn {{
                    padding: 12px 24px;
                    background: #fec82a;
                    color: #333333;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 700;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                }}
                .btn:hover {{
                    background: #e2af13;
                }}
                .table-container {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow-x: auto;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th {{
                    text-align: left;
                    padding: 12px;
                    background: #f5f5f5;
                    font-weight: 600;
                    color: #333;
                    border-bottom: 2px solid #e0e0e0;
                }}
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #e0e0e0;
                }}
                tr:hover {{
                    background: #f9f9f9;
                }}
                .inbox-widget {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    margin-bottom: 20px;
                }}
                .inbox-header {{
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #e0e0e0;
                }}
                .inbox-header h2 {{
                    color: #333333;
                    font-size: 20px;
                    margin: 0;
                    display: inline-block;
                }}
                .inbox-toggle-btn {{
                    font-size: 14px;
                    padding: 6px 12px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    background: white;
                    cursor: pointer;
                    margin-left: 10px;
                }}
                .inbox-toggle-btn:hover {{
                    background: #f5f5f5;
                }}
                .inbox-item.gearchiveerd {{
                    background: #f9f9f9;
                    opacity: 0.6;
                }}
                .inbox-list {{
                    max-height: 400px;
                    overflow-y: auto;
                    list-style: none;
                }}
                .inbox-item {{
                    padding: 12px;
                    border-bottom: 1px solid #e0e0e0;
                    cursor: pointer;
                    transition: background-color 0.2s;
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                }}
                .inbox-item:hover {{
                    background: #f9f9f9;
                }}
                .inbox-item:last-child {{
                    border-bottom: none;
                }}
                .inbox-item-content {{
                    flex: 1;
                    min-width: 0;
                }}
                .inbox-item-contact {{
                    font-weight: 600;
                    color: #333333;
                    margin-bottom: 4px;
                }}
                .inbox-item-preview {{
                    color: #666;
                    font-size: 14px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}
                .inbox-item-time {{
                    color: #999;
                    font-size: 12px;
                    margin-left: 15px;
                    white-space: nowrap;
                }}
                .inbox-item-actions {{
                    display: flex;
                    gap: 6px;
                    margin-left: 15px;
                    align-items: center;
                }}
                .inbox-btn {{
                    font-size: 11px;
                    padding: 3px 8px;
                    border-radius: 6px;
                    border: 1px solid #ddd;
                    background: white;
                    cursor: pointer;
                    text-decoration: none;
                    color: #333;
                    white-space: nowrap;
                }}
                .inbox-btn:hover {{
                    background: #f5f5f5;
                    border-color: #999;
                }}
                .inbox-archive-btn {{
                    font-size: 13px;
                    color: #999;
                    background: none;
                    border: none;
                    cursor: pointer;
                    padding: 0 4px;
                    line-height: 1;
                }}
                .inbox-archive-btn:hover {{
                    color: #e74c3c;
                }}
                .inbox-loading {{
                    text-align: center;
                    padding: 20px;
                    color: #666;
                }}
                .inbox-empty {{
                    text-align: center;
                    padding: 40px;
                    color: #999;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Admin Dashboard - Aanvragen</h1>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <a href="/admin/nieuw?token={SESSION_SECRET}" class="btn">Nieuwe aanvraag</a>
                    <a href="/admin/artikelen?token={SESSION_SECRET}" class="btn" style="background: #3498db; color: white;">Artikelen</a>
                </div>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Ordernummer</th>
                            <th>Naam klant</th>
                            <th>Plaats</th>
                            <th>Leverdatum + tijd</th>
                            <th>Aantal personen / kinderen</th>
                            <th>Totaalprijs incl. BTW</th>
                            <th>BTW</th>
                            <th>Prijs partner</th>
                            <th>Status portaal</th>
                            <th>Status offerte</th>
                            <th>Partner</th>
                            <th>Status betaling</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows if table_rows else '<tr><td colspan="12" style="text-align:center;padding:40px;">Geen aanvragen gevonden</td></tr>'}
                    </tbody>
                </table>
            </div>
            <div class="inbox-widget">
                <div class="inbox-header">
                    <h2>Inkomende berichten</h2>
                    <button class="inbox-toggle-btn" id="inbox-toggle-btn">📁 Archief</button>
                </div>
                <div class="inbox-list" id="inbox-list">
                    <div class="inbox-loading">Laden...</div>
                </div>
            </div>
            <script>
                (function() {{
                    const inboxList = document.getElementById('inbox-list');
                    const toggleBtn = document.getElementById('inbox-toggle-btn');
                    const token = new URLSearchParams(window.location.search).get('token');
                    let toonArchief = false;
                    
                    if (!token) {{
                        inboxList.innerHTML = '<div class="inbox-empty">Geen toegang</div>';
                        return;
                    }}
                    
                    function escapeHtml(text) {{
                        if (!text) return '';
                        const div = document.createElement('div');
                        div.textContent = text;
                        return div.innerHTML;
                    }}
                    
                    function formatTime(dateString) {{
                        if (!dateString) return '';
                        const date = new Date(dateString);
                        const now = new Date();
                        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                        const yesterday = new Date(today);
                        yesterday.setDate(yesterday.getDate() - 1);
                        const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
                        
                        const hours = String(date.getHours()).padStart(2, '0');
                        const minutes = String(date.getMinutes()).padStart(2, '0');
                        const timeStr = hours + ':' + minutes;
                        
                        if (messageDate.getTime() === today.getTime()) {{
                            return 'vandaag ' + timeStr;
                        }} else if (messageDate.getTime() === yesterday.getTime()) {{
                            return 'gisteren ' + timeStr;
                        }} else {{
                            const day = String(date.getDate()).padStart(2, '0');
                            const month = String(date.getMonth() + 1).padStart(2, '0');
                            const year = date.getFullYear();
                            return day + '-' + month + '-' + year + ' ' + timeStr;
                        }}
                    }}
                    
                    function laadInbox(archief) {{
                        inboxList.innerHTML = '<div class="inbox-loading">Laden...</div>';
                        const archiefParam = archief ? '&archief=true' : '';
                        fetch('/admin/communicatie/inbox?token=' + encodeURIComponent(token) + archiefParam)
                            .then(response => response.json())
                            .then(data => {{
                                if (!data.mails || data.mails.length === 0) {{
                                    inboxList.innerHTML = '<div class="inbox-empty">Geen inkomende berichten</div>';
                                    return;
                                }}
                                
                                const mails = data.mails.slice(0, 8);
                                let html = '';
                                
                                mails.forEach(mail => {{
                                    const contactId = mail.contact_id || '';
                                    const contactNaam = mail.contact_naam || mail.email || 'Onbekend';
                                    const preview = mail.bericht_preview || mail.onderwerp || '(Geen preview)';
                                    const tijd = formatTime(mail.verzonden_op);
                                    const link = contactId ? '/admin/klant/' + contactId + '?token=' + encodeURIComponent(token) + '#chatvenster' : '#';
                                    const isGearchiveerd = mail.gearchiveerd || false;
                                    const itemClass = isGearchiveerd ? 'inbox-item gearchieveerd' : 'inbox-item';
                                    
                                    html += '<div class="' + itemClass + '" onclick="window.location.href=\\'' + link + '\\'">';
                                    html += '<div class="inbox-item-content">';
                                    html += '<div class="inbox-item-contact">' + escapeHtml(contactNaam) + '</div>';
                                    html += '<div class="inbox-item-preview">' + escapeHtml(preview) + '</div>';
                                    html += '<div class="inbox-item-time">' + escapeHtml(tijd) + '</div>';
                                    html += '</div>';
                                    html += '<div style="display: flex; align-items: center; gap: 10px;">';
                                    html += '<div class="inbox-item-actions" onclick="event.stopPropagation()">';
                                    if (contactId) {{
                                        const klantLink = '/admin/klant/' + contactId + '?token=' + encodeURIComponent(token);
                                        html += '<a href="' + klantLink + '" class="inbox-btn">Klant</a>';
                                    }}
                                    if (mail.order_id) {{
                                        const orderLink = '/admin/order/' + mail.order_id + '?token=' + encodeURIComponent(token);
                                        html += '<a href="' + orderLink + '" class="inbox-btn">Order</a>';
                                    }}
                                    html += '<button class="inbox-archive-btn" onclick="event.stopPropagation(); window.archiveerMail(\\'' + mail.id + '\\', this)">×</button>';
                                    html += '</div>';
                                    html += '</div>';
                                    html += '</div>';
                                }});
                                
                                inboxList.innerHTML = html;
                            }})
                            .catch(error => {{
                                console.error('Fout bij ophalen inbox:', error);
                                inboxList.innerHTML = '<div class="inbox-empty">Fout bij laden berichten</div>';
                            }});
                    }}
                    
                    window.archiveerMail = function(mailId, button) {{
                        const token = new URLSearchParams(window.location.search).get('token');
                        if (!token) return;
                        
                        fetch('/admin/communicatie/inbox/' + mailId + '/archiveer?token=' + encodeURIComponent(token), {{
                            method: 'POST'
                        }})
                        .then(response => response.json())
                        .then(data => {{
                            // Herlaad inbox met huidige archief status
                            laadInbox(toonArchief);
                        }})
                        .catch(error => {{
                            console.error('Fout bij archiveren:', error);
                            alert('Fout bij archiveren');
                        }});
                    }};
                    
                    // Toggle knop event listener
                    toggleBtn.addEventListener('click', function() {{
                        toonArchief = !toonArchief;
                        toggleBtn.textContent = toonArchief ? '📥 Inbox' : '📁 Archief';
                        laadInbox(toonArchief);
                    }});
                    
                    // Laad initieel inbox
                    laadInbox(false);
                }})();
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        _LOG.error(f"Fout bij ophalen admin dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen dashboard: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.get("/nieuw", response_class=HTMLResponse)
async def nieuwe_aanvraag_form(request: Request, verified: bool = Depends(verify_admin_session)):
    """Formulier voor nieuwe aanvraag"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="nl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FTH Admin - Nieuwe Aanvraag</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #fffdf2;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333333;
                margin-bottom: 30px;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 500;
            }}
            input[type="text"],
            input[type="email"],
            input[type="tel"],
            input[type="datetime-local"],
            input[type="number"],
            textarea,
            select {{
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
            }}
            textarea {{
                min-height: 100px;
                resize: vertical;
            }}
            .btn {{
                padding: 12px 24px;
                background: #fec82a;
                color: #333333;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
            }}
            .btn:hover {{
                background: #e2af13;
            }}
            .btn-secondary {{
                background: #ccc;
                margin-left: 10px;
            }}
            .btn-secondary:hover {{
                background: #999;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Nieuwe Aanvraag</h1>
            <form method="post" action="/admin/nieuw?token={SESSION_SECRET}">
                <div class="form-group">
                    <label for="klant_naam">Naam klant *</label>
                    <input type="text" id="klant_naam" name="klant_naam" required>
                </div>
                <div class="form-group">
                    <label for="klant_email">Email klant *</label>
                    <input type="email" id="klant_email" name="klant_email" required>
                </div>
                <div class="form-group">
                    <label for="klant_telefoon">Telefoon klant</label>
                    <input type="tel" id="klant_telefoon" name="klant_telefoon">
                </div>
                <div class="form-group">
                    <label for="plaats">Plaats evenement *</label>
                    <input type="text" id="plaats" name="plaats" required>
                </div>
                <div class="form-group">
                    <label for="leverdatum">Leverdatum + tijd *</label>
                    <input type="datetime-local" id="leverdatum" name="leverdatum" required>
                </div>
                <div class="form-group">
                    <label for="aantal_personen">Aantal personen *</label>
                    <input type="number" id="aantal_personen" name="aantal_personen" min="0" value="0" required>
                </div>
                <div class="form-group">
                    <label for="aantal_kinderen">Aantal kinderen</label>
                    <input type="number" id="aantal_kinderen" name="aantal_kinderen" min="0" value="0">
                </div>
                <div class="form-group">
                    <label for="ordertype">Ordertype</label>
                    <select id="ordertype" name="ordertype">
                        <option value="b2b">B2B (Zakelijk)</option>
                        <option value="b2c">B2C (Particulier)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="opmerkingen">Opmerkingen</label>
                    <textarea id="opmerkingen" name="opmerkingen"></textarea>
                </div>
                <div>
                    <button type="submit" class="btn">Opslaan</button>
                    <a href="/admin?token={SESSION_SECRET}" class="btn btn-secondary">Annuleren</a>
                </div>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/nieuw", response_class=RedirectResponse)
async def verwerk_nieuwe_aanvraag(
    request: Request,
    verified: bool = Depends(verify_admin_session),
    klant_naam: str = Form(...),
    klant_email: str = Form(...),
    klant_telefoon: str = Form(None),
    plaats: str = Form(...),
    leverdatum: str = Form(...),
    aantal_personen: int = Form(...),
    aantal_kinderen: int = Form(0),
    ordertype: str = Form("b2b"),
    opmerkingen: str = Form(None)
):
    """Verwerk nieuwe aanvraag"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Parse leverdatum
        leverdatum_dt = datetime.strptime(leverdatum, "%Y-%m-%dT%H:%M")
        
        # Genereer ordernummer: FTHYYYYMMDDXXXX (zonder streepjes)
        ordernummer = "FTH" + datetime.now().strftime("%Y%m%d") + str(random.randint(1000, 9999))
        
        # Check of contact al bestaat op email
        cur.execute("SELECT id FROM contacten WHERE email = %s LIMIT 1", (klant_email,))
        existing_contact = cur.fetchone()
        
        if existing_contact:
            klant_id = existing_contact["id"]
            # Update contact gegevens
            cur.execute("""
                UPDATE contacten 
                SET naam = %s, telefoon = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (klant_naam, klant_telefoon, klant_id))
        else:
            # Maak nieuw contact
            cur.execute("""
                INSERT INTO contacten (naam, email, telefoon)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (klant_naam, klant_email, klant_telefoon))
            klant_id = cur.fetchone()["id"]
        
        # Maak nieuwe order
        cur.execute("""
            INSERT INTO orders (
                ordernummer, order_datum, leverdatum, status, portaal_status,
                type_naam, klant_id, totaal_bedrag, bedrag_excl_btw, bedrag_btw,
                plaats, aantal_personen, aantal_kinderen, ordertype, opmerkingen
            ) VALUES (
                %s, CURRENT_TIMESTAMP, %s, 'sent', 'nieuw',
                'Offerte', %s, 0.00, 0.00, 0.00,
                %s, %s, %s, %s, %s
            )
        """, (
            ordernummer, leverdatum_dt, klant_id,
            plaats, aantal_personen, aantal_kinderen, ordertype, opmerkingen
        ))
        
        conn.commit()
        
        return RedirectResponse(url=f"/admin?token={SESSION_SECRET}", status_code=303)
        
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij aanmaken nieuwe aanvraag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij aanmaken aanvraag: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.get("/communicatie/inbox")
async def communicatie_inbox(
    request: Request,
    archief: bool = False,
    verified: bool = Depends(verify_admin_session)
):
    """Haal inbox overzicht op: alle inkomende mails"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Bepaal WHERE clause op basis van archief parameter
        if archief:
            archiveer_filter = "ml.gearchiveerd = TRUE"
        else:
            archiveer_filter = "(ml.gearchiveerd = FALSE OR ml.gearchiveerd IS NULL)"
        
        cur.execute(f"""
            SELECT
                ml.id,
                COALESCE(ml.ontvanger_id, o.klant_id) as contact_id,
                COALESCE(c.naam, ml.email_van, ml.naar) as contact_naam,
                COALESCE(c.email, ml.email_van, ml.naar) as email,
                ml.preview as bericht_preview,
                ml.onderwerp,
                ml.verzonden_op,
                ml.order_id,
                ml.gearchiveerd
            FROM mail_logs ml
            LEFT JOIN contacten c ON ml.ontvanger_id = c.id
            LEFT JOIN orders o ON ml.order_id = o.id
            WHERE ml.richting = 'inkomend'
              AND {archiveer_filter}
              AND ml.verzonden_op IS NOT NULL
            ORDER BY ml.verzonden_op DESC NULLS LAST, ml.created_at DESC
            LIMIT 100
        """)
        
        mails = cur.fetchall()
        
        # Converteer naar dict lijst
        result = []
        for mail in mails:
            result.append({
                "id": str(mail.get("id")),
                "contact_id": str(mail.get("contact_id")) if mail.get("contact_id") else None,
                "contact_naam": mail.get("contact_naam"),
                "email": mail.get("email"),
                "bericht_preview": mail.get("bericht_preview"),
                "onderwerp": mail.get("onderwerp"),
                "verzonden_op": mail.get("verzonden_op").isoformat() if mail.get("verzonden_op") else None,
                "order_id": str(mail.get("order_id")) if mail.get("order_id") else None,
                "gearchiveerd": mail.get("gearchiveerd") or False
            })
        
        return JSONResponse({"mails": result, "aantal": len(result)})
        
    except Exception as e:
        _LOG.error(f"Fout bij ophalen inbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/communicatie/inbox/{mail_id}/archiveer")
async def archiveer_mail(
    request: Request,
    mail_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Archiveer een mail log"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE mail_logs
            SET gearchiveerd = TRUE
            WHERE id = %s
        """, (mail_id,))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Mail niet gevonden")
        
        conn.commit()
        return JSONResponse({"status": "ok"})
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij archiveren mail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            cur.close()
            conn.close()