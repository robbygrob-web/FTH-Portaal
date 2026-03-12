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
        cur.execute("""
            SELECT 
                o.id,
                o.ordernummer,
                o.order_datum,
                o.leverdatum,
                o.status,
                o.portaal_status,
                o.totaal_bedrag,
                o.bedrag_excl_btw,
                o.bedrag_btw,
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
                "draft": ("Concept", "#999")
            }
            return status_map.get(status, (status, "#999"))
        
        # Build HTML table rows
        table_rows = ""
        for order in orders:
            portaal_status_text, portaal_status_color = format_portaal_status(order.get("portaal_status", "nieuw"))
            order_status_text, order_status_color = format_order_status(order.get("status", "draft"))
            
            ordernummer = order.get("ordernummer") or "-"
            klant_naam = order.get("klant_naam") or "-"
            klant_id = order.get("klant_id")
            plaats = order.get("plaats") or "-"
            leverdatum = format_datetime(order.get("leverdatum"))
            personen = order.get("aantal_personen", 0)
            kinderen = order.get("aantal_kinderen", 0)
            totaal = float(order.get("totaal_bedrag", 0))
            partner_naam = order.get("partner_naam") or "-"
            
            order_id = str(order.get("id"))
            klant_link = f"/admin/klant/{klant_id}?token={SESSION_SECRET}" if klant_id else "#"
            table_rows += f"""
            <tr>
                <td><a href="/admin/order/{order_id}?token={SESSION_SECRET}" style="color:#333;text-decoration:none;font-weight:500;">{ordernummer}</a></td>
                <td><a href="{klant_link}" style="color:#333;text-decoration:none;font-weight:500;">{klant_naam}</a></td>
                <td>{plaats}</td>
                <td>{leverdatum}</td>
                <td>{personen} / {kinderen}</td>
                <td>€ {totaal:,.2f}</td>
                <td><span style="color:{portaal_status_color};">{portaal_status_text}</span></td>
                <td><span style="color:{order_status_color};">{order_status_text}</span></td>
                <td>{partner_naam}</td>
                <td>-</td>
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
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Admin Dashboard - Aanvragen</h1>
                <a href="/admin/nieuw?token={SESSION_SECRET}" class="btn">Nieuwe aanvraag</a>
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
                            <th>Status portaal</th>
                            <th>Status offerte</th>
                            <th>Partner</th>
                            <th>Status betaling</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows if table_rows else '<tr><td colspan="10" style="text-align:center;padding:40px;">Geen aanvragen gevonden</td></tr>'}
                    </tbody>
                </table>
            </div>
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
        today = datetime.now()
        random_suffix = random.randint(1000, 9999)
        ordernummer = f"FTH{today.strftime('%Y%m%d')}{random_suffix:04d}"
        
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
