"""
Script om 10 recente orders + klanten te importeren van Odoo naar PostgreSQL.
Importeert: contacten, orders, en order_artikelen.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Voeg project root toe aan Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Laad environment variabelen
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
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


def parse_date(date_str):
    """Parse Odoo date string naar Python datetime"""
    if not date_str:
        return None
    try:
        # Odoo format: "YYYY-MM-DD HH:MM:SS" of "YYYY-MM-DD"
        if len(date_str) > 10:
            return datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        else:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except Exception as e:
        print(f"  Waarschuwing: Kon datum niet parsen '{date_str}': {e}")
        return None


def calculate_btw_percentage(price_excl, price_incl):
    """Bereken BTW percentage uit prijzen"""
    if not price_excl or price_excl == 0:
        return 9.00  # Default
    btw_amount = price_incl - price_excl
    return round((btw_amount / price_excl) * 100, 2)


def main():
    """Hoofdfunctie voor import"""
    print("=" * 60)
    print("IMPORT ODOO ORDERS + KLANTEN")
    print("=" * 60)
    
    # Connect naar Odoo
    print("\n[1/6] Verbinden met Odoo...")
    try:
        client = get_odoo_client()
        print("  [OK] Odoo verbinding succesvol")
    except Exception as e:
        print(f"  [ERROR] Fout bij Odoo verbinding: {e}")
        return
    
    # Connect naar PostgreSQL
    print("\n[2/6] Verbinden met PostgreSQL...")
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("  [OK] PostgreSQL verbinding succesvol")
    except Exception as e:
        print(f"  [ERROR] Fout bij PostgreSQL verbinding: {e}")
        return
    
    try:
        # Stap 1: Haal 10 recente orders op uit Odoo
        print("\n[3/6] Ophalen 10 recente orders uit Odoo...")
        orders = client.execute_kw(
            "sale.order",
            "search_read",
            [[("state", "in", ["sent", "sale"])]],  # Alleen offertes en verkooporders
            {
                "fields": [
                    "id", "name", "date_order", "state", "partner_id",
                    "commitment_date", "amount_total", "amount_untaxed", "amount_tax",
                    "x_studio_plaats", "x_studio_aantal_personen", "x_studio_aantal_kinderen",
                    "x_studio_ordertype", "payment_term_id", "note",
                    "utm_source", "utm_medium", "utm_campaign", "utm_content",
                    "order_line"
                ],
                "order": "id desc",
                "limit": 10
            }
        )
        print(f"  [OK] {len(orders)} orders gevonden")
        
        if not orders:
            print("  [WARNING] Geen orders gevonden om te importeren")
            return
        
        # Stap 2: Verzamel unieke partner IDs
        partner_ids = []
        for order in orders:
            if order.get("partner_id"):
                partner_id = order["partner_id"][0] if isinstance(order["partner_id"], (list, tuple)) else order["partner_id"]
                if partner_id not in partner_ids:
                    partner_ids.append(partner_id)
        
        print(f"\n[4/6] Ophalen {len(partner_ids)} partners uit Odoo...")
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
        print(f"  [OK] {len(partners)} partners gevonden")
        
        # Stap 3: Import partners in contacten
        print("\n[5/6] Importeren partners in contacten tabel...")
        partner_lookup = {}  # odoo_id -> PostgreSQL UUID
        imported_partners = 0
        
        for partner in partners:
            odoo_id = partner["id"]
            country_code = "NL"
            if partner.get("country_id"):
                country_name = partner["country_id"][1] if isinstance(partner["country_id"], (list, tuple)) else str(partner["country_id"])
                # Extract first 2 chars for country code
                country_code = country_name[:2].upper() if country_name else "NL"
            
            # Map velden
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
            
            # INSERT met ON CONFLICT
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
        print(f"  [OK] {imported_partners} partners geïmporteerd/bijgewerkt")
        
        # Stap 4: Verzamel order_line IDs
        all_line_ids = []
        for order in orders:
            if order.get("order_line"):
                all_line_ids.extend(order["order_line"])
        
        # Haal order_lines op
        order_lines = []
        if all_line_ids:
            print(f"\n[6/6] Ophalen {len(all_line_ids)} order lines uit Odoo...")
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
            print(f"  [OK] {len(order_lines)} order lines gevonden")
        
        # Stap 5: Import orders
        print("\n[7/6] Importeren orders in orders tabel...")
        order_lookup = {}  # odoo_id -> PostgreSQL UUID
        imported_orders = 0
        
        for order in orders:
            odoo_id = order["id"]
            partner_id_tuple = order.get("partner_id")
            partner_odoo_id = partner_id_tuple[0] if partner_id_tuple and isinstance(partner_id_tuple, (list, tuple)) else None
            
            # Zoek klant_id
            klant_id = partner_lookup.get(partner_odoo_id) if partner_odoo_id else None
            
            # Parse datums
            order_datum = parse_date(order.get("date_order"))
            leverdatum = parse_date(order.get("commitment_date"))
            
            # Status mapping
            state = order.get("state", "")
            status = "sent" if state == "sent" else "sale"
            type_naam = "Offerte" if state == "sent" else "Verkooporder"
            
            # Payment term
            payment_term_id = None
            payment_term_naam = None
            if order.get("payment_term_id"):
                payment_term_id = order["payment_term_id"][0] if isinstance(order["payment_term_id"], (list, tuple)) else order["payment_term_id"]
                payment_term_naam = order["payment_term_id"][1] if isinstance(order["payment_term_id"], (list, tuple)) else None
            
            # Map velden
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
                "utm_source": order.get("utm_source"),
                "utm_medium": order.get("utm_medium"),
                "utm_campaign": order.get("utm_campaign"),
                "utm_content": order.get("utm_content")
            }
            
            # INSERT met ON CONFLICT
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
        print(f"  [OK] {imported_orders} orders geïmporteerd/bijgewerkt")
        
        # Stap 6: Import order_artikelen
        print("\n[8/6] Importeren order_artikelen in order_artikelen tabel...")
        imported_lines = 0
        
        for line in order_lines:
            odoo_id = line["id"]
            order_id_tuple = line.get("order_id")
            order_odoo_id = order_id_tuple[0] if order_id_tuple and isinstance(order_id_tuple, (list, tuple)) else None
            
            # Zoek order_id
            order_id = order_lookup.get(order_odoo_id) if order_odoo_id else None
            if not order_id:
                print(f"  [WARNING] Order line {odoo_id} heeft geen bijbehorende order (order_odoo_id: {order_odoo_id})")
                continue
            
            # Zoek artikel_id (optioneel)
            artikel_id = None
            product_id_tuple = line.get("product_id")
            if product_id_tuple:
                product_odoo_id = product_id_tuple[0] if isinstance(product_id_tuple, (list, tuple)) else product_id_tuple
                # Zoek artikel in database
                cur.execute("SELECT id FROM artikelen WHERE odoo_id = %s", (product_odoo_id,))
                artikel_result = cur.fetchone()
                if artikel_result:
                    artikel_id = artikel_result["id"]
            
            # Bereken BTW
            price_excl = float(line.get("price_unit", 0)) if line.get("price_unit") else 0.00
            price_subtotal = float(line.get("price_subtotal", 0)) if line.get("price_subtotal") else 0.00
            price_incl = float(line.get("price_subtotal_incl", 0)) if line.get("price_subtotal_incl") else 0.00
            
            # Als price_incl niet beschikbaar is, bereken uit price_subtotal
            if not price_incl and price_subtotal:
                price_incl = price_subtotal * 1.09  # Default 9% BTW
            
            btw_bedrag = price_incl - price_subtotal if price_incl and price_subtotal else 0.00
            btw_pct = calculate_btw_percentage(price_subtotal, price_incl)
            
            # Map velden
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
            
            # INSERT met ON CONFLICT
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
        print(f"  [OK] {imported_lines} order_artikelen geïmporteerd/bijgewerkt")
        
        # Samenvatting
        print("\n" + "=" * 60)
        print("IMPORT VOLTOOID")
        print("=" * 60)
        print(f"  Partners: {imported_partners}")
        print(f"  Orders: {imported_orders}")
        print(f"  Order artikelen: {imported_lines}")
        print("=" * 60)
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Fout tijdens import: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
