"""
Schema review: Vergelijk Odoo velden met onze database structuur.
"""
import json

# Odoo sale.order velden uit de JSON
odoo_fields = {
    # Identificatie
    "id": 874,
    "name": "S00877",
    "display_name": "S00877",
    
    # Datums
    "date_order": "2026-03-11 16:10:29",
    "commitment_date": "2026-03-28 12:00:00",
    "expected_date": "2026-03-11 16:11:19",
    "validity_date": "2026-03-18",
    "create_date": "2026-03-11 16:10:29",
    "write_date": "2026-03-11 16:10:29",
    
    # Status
    "state": "draft",
    "type_name": "Offerte",
    
    # Relaties
    "partner_id": [1, "4444"],
    "partner_invoice_id": [1, "4444"],
    "partner_shipping_id": [1, "4444"],
    "user_id": [2, "e e"],
    "team_id": [1, "Verkoop"],
    
    # Bedragen
    "amount_total": 575,
    "amount_untaxed": 527.53,
    "amount_tax": 47.47,
    "amount_invoiced": 0,
    "amount_paid": 0,
    "amount_to_invoice": 575,
    "amount_undiscounted": 527.53,
    
    # Valuta
    "currency_id": [125, "EUR"],
    "currency_rate": 1,
    
    # Order details (custom fields)
    "x_studio_aantal_personen": 44,
    "x_studio_aantal_kinderen": 0,
    "x_studio_plaats": "Den Haag",
    "x_studio_ordertype": "b2c",
    "x_studio_contractor": [87, "De Aardappeltuin"],
    "x_studio_inkoop_partner_incl_btw": 0,
    "x_studio_selection_field_67u_1jj77rtf7": False,  # Portaal status
    "x_studio_notes": " ",
    
    # UTM tracking
    "x_studio_wp_source": "",
    "x_studio_wp_medium": "",
    "x_studio_wp_campaign": "",
    "x_studio_gclid": "",
    
    # Betaling
    "payment_term_id": False,
    "prepayment_percent": 1,
    
    # Overig
    "note": "<h4>...",  # HTML notities
    "origin": False,
    "reference": False,
    "client_order_ref": False,
}

# Onze database kolommen (uit schema.sql)
our_columns = {
    # Identificatie
    "id": "UUID PRIMARY KEY",
    "ordernummer": "VARCHAR(50) NOT NULL UNIQUE",
    
    # Datums
    "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
    "order_datum": "TIMESTAMP WITH TIME ZONE NOT NULL",
    "leverdatum": "TIMESTAMP WITH TIME ZONE",
    "vervaldatum": "DATE",
    
    # Status
    "status": "VARCHAR(20) NOT NULL",  # sent, sale, draft, cancel
    "portaal_status": "VARCHAR(20) DEFAULT 'nieuw'",  # nieuw, beschikbaar, claimed, transfer
    "type_naam": "VARCHAR(50)",  # Offerte / Verkooporder
    
    # Relaties
    "klant_id": "UUID REFERENCES contacten(id)",
    "contractor_id": "UUID REFERENCES contacten(id)",
    
    # Bedragen
    "totaal_bedrag": "DECIMAL(10, 2) NOT NULL DEFAULT 0.00",
    "bedrag_excl_btw": "DECIMAL(10, 2) NOT NULL DEFAULT 0.00",
    "bedrag_btw": "DECIMAL(10, 2) NOT NULL DEFAULT 0.00",
    "inkoop_partner_incl_btw": "DECIMAL(10, 2) DEFAULT 0.00",
    
    # Order details
    "plaats": "VARCHAR(255)",
    "aantal_personen": "INTEGER DEFAULT 0",
    "aantal_kinderen": "INTEGER DEFAULT 0",
    "ordertype": "VARCHAR(10)",  # b2b, b2c
    
    # Betaling
    "betaaltermijn_id": "INTEGER",
    "betaaltermijn_naam": "VARCHAR(100)",
    
    # Extra
    "opmerkingen": "TEXT",
    
    # UTM Tracking
    "utm_source": "VARCHAR(255)",
    "utm_medium": "VARCHAR(255)",
    "utm_campaign": "VARCHAR(255)",
    "utm_content": "VARCHAR(255)",
    
    # Odoo sync
    "odoo_id": "INTEGER UNIQUE",
}

def main():
    print("=" * 80)
    print("SCHEMA REVIEW: ODOO vs EIGEN DATABASE")
    print("=" * 80)
    
    print("\n1. VELDMAPPING ANALYSE")
    print("-" * 80)
    
    # Mapping tussen Odoo en onze DB
    mappings = {
        "id": ("odoo_id", "INTEGER"),
        "name": ("ordernummer", "VARCHAR(50)"),
        "date_order": ("order_datum", "TIMESTAMP WITH TIME ZONE"),
        "commitment_date": ("leverdatum", "TIMESTAMP WITH TIME ZONE"),
        "validity_date": ("vervaldatum", "DATE"),
        "state": ("status", "VARCHAR(20)"),
        "type_name": ("type_naam", "VARCHAR(50)"),
        "x_studio_selection_field_67u_1jj77rtf7": ("portaal_status", "VARCHAR(20)"),
        "partner_id": ("klant_id", "UUID"),
        "x_studio_contractor": ("contractor_id", "UUID"),
        "amount_total": ("totaal_bedrag", "DECIMAL(10, 2)"),
        "amount_untaxed": ("bedrag_excl_btw", "DECIMAL(10, 2)"),
        "amount_tax": ("bedrag_btw", "DECIMAL(10, 2)"),
        "x_studio_inkoop_partner_incl_btw": ("inkoop_partner_incl_btw", "DECIMAL(10, 2)"),
        "x_studio_plaats": ("plaats", "VARCHAR(255)"),
        "x_studio_aantal_personen": ("aantal_personen", "INTEGER"),
        "x_studio_aantal_kinderen": ("aantal_kinderen", "INTEGER"),
        "x_studio_ordertype": ("ordertype", "VARCHAR(10)"),
        "payment_term_id": ("betaaltermijn_id", "INTEGER"),
        "x_studio_notes": ("opmerkingen", "TEXT"),
        "x_studio_wp_source": ("utm_source", "VARCHAR(255)"),
        "x_studio_wp_medium": ("utm_medium", "VARCHAR(255)"),
        "x_studio_wp_campaign": ("utm_campaign", "VARCHAR(255)"),
    }
    
    print("\nBestaande mappings:")
    for odoo_field, (our_field, our_type) in mappings.items():
        print(f"  {odoo_field:<40} -> {our_field:<30} ({our_type})")
    
    print("\n\n2. ONTBREKENDE KOLOMMEN IN EIGEN DB")
    print("-" * 80)
    
    missing_fields = {
        "amount_invoiced": "DECIMAL(10, 2) - Hoeveel er al gefactureerd is",
        "amount_paid": "DECIMAL(10, 2) - Hoeveel er al betaald is",
        "amount_to_invoice": "DECIMAL(10, 2) - Hoeveel er nog gefactureerd moet worden",
        "amount_undiscounted": "DECIMAL(10, 2) - Bedrag zonder korting",
        "currency_id": "INTEGER - Valuta ID (nu hardcoded EUR)",
        "currency_rate": "DECIMAL(10, 6) - Wisselkoers",
        "expected_date": "TIMESTAMP WITH TIME ZONE - Verwacht leverdatum",
        "write_date": "TIMESTAMP WITH TIME ZONE - Laatste wijziging datum",
        "write_uid": "INTEGER - Laatste wijziging gebruiker ID",
        "create_uid": "INTEGER - Aanmaker gebruiker ID",
        "user_id": "INTEGER - Verantwoordelijke verkoper ID",
        "team_id": "INTEGER - Verkoopteam ID",
        "partner_invoice_id": "UUID - Factuuradres (kan verschillen van klant_id)",
        "partner_shipping_id": "UUID - Leveradres (kan verschillen van klant_id)",
        "origin": "VARCHAR(255) - Herkomst (bijv. website, telefoon)",
        "reference": "VARCHAR(255) - Interne referentie",
        "client_order_ref": "VARCHAR(255) - Klant referentie",
        "note": "TEXT - HTML notities (verschilt van opmerkingen)",
        "x_studio_aantal_personen_origineel": "INTEGER - Origineel aantal personen",
        "x_studio_flexible_time": "VARCHAR(10) - Flexibele tijd",
        "x_studio_halal": "BOOLEAN - Halal optie",
        "x_studio_gclid": "VARCHAR(255) - Google Click ID",
    }
    
    for field, description in missing_fields.items():
        print(f"  {field:<40} - {description}")
    
    print("\n\n3. VELDEN DIE WE HEBBEN MAAR ODOO NIET")
    print("-" * 80)
    
    # Alle onze kolommen die niet in Odoo voorkomen
    our_only_fields = {
        "created_at": "Automatisch timestamp (Odoo heeft create_date)",
        "updated_at": "Automatisch timestamp (Odoo heeft write_date)",
        "utm_content": "UTM content (Odoo heeft alleen source/medium/campaign)",
    }
    
    for field, description in our_only_fields.items():
        print(f"  {field:<40} - {description}")
    
    print("\n\n4. TYPE VERSCHILLEN")
    print("-" * 80)
    
    type_differences = {
        "odoo_id": ("INTEGER", "Odoo gebruikt INTEGER, wij ook - OK"),
        "ordernummer": ("VARCHAR(50)", "Odoo gebruikt 'name' (S00877), wij VARCHAR - OK"),
        "status": ("VARCHAR(20)", "Odoo: draft/sent/sale, wij: draft/sent/sale/cancel - OK"),
        "portaal_status": ("VARCHAR(20)", "Odoo: x_studio_selection_field_67u_1jj77rtf7 (False/claimed/transfer), wij: nieuw/beschikbaar/claimed/transfer - MOGELIJK PROBLEEM"),
        "klant_id": ("UUID", "Odoo: partner_id (INTEGER), wij: UUID - CONVERSIE NODIG"),
        "contractor_id": ("UUID", "Odoo: x_studio_contractor (INTEGER), wij: UUID - CONVERSIE NODIG"),
    }
    
    for field, (our_type, note) in type_differences.items():
        print(f"  {field:<30} {our_type:<20} - {note}")
    
    print("\n\n5. VOORGESTELDE CORRECTIES")
    print("-" * 80)
    
    corrections = [
        {
            "type": "TOEVOEGEN",
            "kolom": "amount_invoiced DECIMAL(10, 2) DEFAULT 0.00",
            "reden": "Track hoeveel er al gefactureerd is"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "amount_paid DECIMAL(10, 2) DEFAULT 0.00",
            "reden": "Track hoeveel er al betaald is"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "amount_to_invoice DECIMAL(10, 2) DEFAULT 0.00",
            "reden": "Track hoeveel er nog gefactureerd moet worden"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "currency_id INTEGER",
            "reden": "Support voor andere valuta's (nu hardcoded EUR)"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "currency_rate DECIMAL(10, 6) DEFAULT 1.0",
            "reden": "Wisselkoers support"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "expected_date TIMESTAMP WITH TIME ZONE",
            "reden": "Verwachte leverdatum (kan verschillen van commitment_date)"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "origin VARCHAR(255)",
            "reden": "Herkomst van order (website, telefoon, etc.)"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "reference VARCHAR(255)",
            "reden": "Interne referentie"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "client_order_ref VARCHAR(255)",
            "reden": "Klant referentie nummer"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "note TEXT",
            "reden": "HTML notities (verschilt van opmerkingen die voor klant zijn)"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "partner_invoice_id UUID REFERENCES contacten(id)",
            "reden": "Factuuradres kan verschillen van klant_id"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "partner_shipping_id UUID REFERENCES contacten(id)",
            "reden": "Leveradres kan verschillen van klant_id"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "user_id INTEGER",
            "reden": "Verantwoordelijke verkoper (Odoo user ID)"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "team_id INTEGER",
            "reden": "Verkoopteam (Odoo team ID)"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "aantal_personen_origineel INTEGER",
            "reden": "Origineel aantal personen (voor wijzigingen tracking)"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "flexible_time VARCHAR(10)",
            "reden": "Flexibele tijd optie"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "halal BOOLEAN DEFAULT FALSE",
            "reden": "Halal optie"
        },
        {
            "type": "TOEVOEGEN",
            "kolom": "gclid VARCHAR(255)",
            "reden": "Google Click ID voor tracking"
        },
        {
            "type": "AANPASSEN",
            "kolom": "portaal_status",
            "huidig": "VARCHAR(20) met waarden: nieuw, beschikbaar, claimed, transfer",
            "nieuw": "VARCHAR(20) met waarden: False (of NULL), claimed, transfer",
            "reden": "Odoo gebruikt False voor 'nieuw', niet 'nieuw' string"
        },
        {
            "type": "OPMERKING",
            "kolom": "klant_id / contractor_id",
            "opmerking": "Odoo gebruikt INTEGER IDs, wij gebruiken UUID. Conversie nodig bij sync.",
            "reden": "Type mismatch tussen Odoo en eigen DB"
        },
    ]
    
    for idx, correction in enumerate(corrections, 1):
        print(f"\n{idx}. [{correction['type']}] {correction['kolom']}")
        if 'huidig' in correction:
            print(f"   Huidig: {correction['huidig']}")
            print(f"   Nieuw: {correction['nieuw']}")
        if 'opmerking' in correction:
            print(f"   Opmerking: {correction['opmerking']}")
        print(f"   Reden: {correction['reden']}")
    
    print("\n\n6. REDUNDANTIE ANALYSE")
    print("-" * 80)
    
    redundancy = [
        {
            "veld": "opmerkingen vs note",
            "analyse": "Odoo heeft zowel 'note' (HTML, voor klant) als 'x_studio_notes' (interne notities). Wij hebben alleen 'opmerkingen'. Mogelijk splitsen in 'opmerkingen_klant' en 'opmerkingen_intern'."
        },
        {
            "veld": "created_at vs create_date",
            "analyse": "Beide bestaan. created_at is automatisch, create_date komt uit Odoo. Mogelijk alleen created_at gebruiken."
        },
        {
            "veld": "updated_at vs write_date",
            "analyse": "Beide bestaan. updated_at is automatisch via trigger, write_date komt uit Odoo. Mogelijk alleen updated_at gebruiken."
        },
    ]
    
    for idx, item in enumerate(redundancy, 1):
        print(f"\n{idx}. {item['veld']}")
        print(f"   {item['analyse']}")
    
    print("\n" + "=" * 80)
    print("EINDE SCHEMA REVIEW")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
