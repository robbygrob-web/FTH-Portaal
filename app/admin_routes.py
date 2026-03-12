"""
Tijdelijk admin endpoint voor database setup en import.
Wordt verwijderd na succesvolle import.
"""
import os
import logging
import traceback
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from app.odoo_client import get_odoo_client
from app.config import SESSION_SECRET

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/setup", tags=["admin"])


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


@router.post("/init-db")
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
        
        # Stap 3: Haal 10 recente orders op (alleen veilige standaard velden)
        orders = client.execute_kw(
            "sale.order",
            "search_read",
            [[("state", "in", ["sent", "sale"])]],
            {
                "fields": [
                    "id", "name", "date_order", "state", "partner_id",
                    "commitment_date", "amount_total", "amount_untaxed", "amount_tax",
                    "note", "order_line",
                    "utm_source_id", "utm_medium_id", "utm_campaign_id",
                    "payment_term_id"
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
        
        # Stap 3b: Haal x_studio velden op per order (met try/except voor veiligheid)
        order_ids = [order["id"] for order in orders]
        x_studio_data = {}
        if order_ids:
            try:
                x_studio_orders = client.execute_kw(
                    "sale.order",
                    "read",
                    order_ids,
                    {
                        "fields": [
                            "id", "x_studio_plaats", "x_studio_aantal_personen",
                            "x_studio_aantal_kinderen", "x_studio_ordertype"
                        ]
                    }
                )
                for x_order in x_studio_orders:
                    x_studio_data[x_order["id"]] = {
                        "x_studio_plaats": x_order.get("x_studio_plaats"),
                        "x_studio_aantal_personen": x_order.get("x_studio_aantal_personen"),
                        "x_studio_aantal_kinderen": x_order.get("x_studio_aantal_kinderen"),
                        "x_studio_ordertype": x_order.get("x_studio_ordertype")
                    }
            except Exception as e:
                _LOG.warning(f"Kon x_studio velden niet ophalen: {e}. Gebruik None als default.")
                # Maak lege dict voor alle orders
                for order_id in order_ids:
                    x_studio_data[order_id] = {
                        "x_studio_plaats": None,
                        "x_studio_aantal_personen": None,
                        "x_studio_aantal_kinderen": None,
                        "x_studio_ordertype": None
                    }
        
        # Voeg x_studio velden toe aan orders
        for order in orders:
            order_id = order["id"]
            if order_id in x_studio_data:
                order.update(x_studio_data[order_id])
            else:
                order["x_studio_plaats"] = None
                order["x_studio_aantal_personen"] = None
                order["x_studio_aantal_kinderen"] = None
                order["x_studio_ordertype"] = None
        
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
            
            payment_term_id = None
            payment_term_naam = None
            if order.get("payment_term_id"):
                payment_term_id = order["payment_term_id"][0] if isinstance(order["payment_term_id"], (list, tuple)) else order["payment_term_id"]
                payment_term_naam = order["payment_term_id"][1] if isinstance(order["payment_term_id"], (list, tuple)) else None
            
            # Extract UTM values from many2one fields
            utm_source = None
            utm_medium = None
            utm_campaign = None
            utm_content = None
            
            if order.get("utm_source_id"):
                utm_source_tuple = order["utm_source_id"]
                utm_source = utm_source_tuple[1] if isinstance(utm_source_tuple, (list, tuple)) and len(utm_source_tuple) > 1 else None
            
            if order.get("utm_medium_id"):
                utm_medium_tuple = order["utm_medium_id"]
                utm_medium = utm_medium_tuple[1] if isinstance(utm_medium_tuple, (list, tuple)) and len(utm_medium_tuple) > 1 else None
            
            if order.get("utm_campaign_id"):
                utm_campaign_tuple = order["utm_campaign_id"]
                utm_campaign = utm_campaign_tuple[1] if isinstance(utm_campaign_tuple, (list, tuple)) and len(utm_campaign_tuple) > 1 else None
            
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
                "plaats": order.get("x_studio_plaats"),
                "aantal_personen": int(order.get("x_studio_aantal_personen", 0)) if order.get("x_studio_aantal_personen") else 0,
                "aantal_kinderen": int(order.get("x_studio_aantal_kinderen", 0)) if order.get("x_studio_aantal_kinderen") else 0,
                "ordertype": order.get("x_studio_ordertype"),
                "betaaltermijn_id": payment_term_id,
                "betaaltermijn_naam": payment_term_naam,
                "opmerkingen": order.get("note"),
                "utm_source": utm_source,
                "utm_medium": utm_medium,
                "utm_campaign": utm_campaign,
                "utm_content": utm_content
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
