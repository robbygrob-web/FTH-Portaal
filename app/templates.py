"""
Template beheer endpoints voor mail templates.
"""
import json
import logging
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from typing import Dict, Any

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])

# Bestandspaden
PROJECT_ROOT = Path(__file__).parent.parent
ODOO_TEMPLATES_FILE = PROJECT_ROOT / "docs" / "odoo_mail_templates.json"
TEMPLATES_FILE = PROJECT_ROOT / "docs" / "templates.json"

# FTH template namen die behouden moeten worden (ID: 32, 38, 41, 42, 43, 47, 48, 99)
FTH_TEMPLATE_NAMES = {
    "1e herinnering offerte Friettruck huren",
    "Orderkopie voor partner",
    "Verkoop: Nog",
    "Verkoop: Nog drie dagen tot uw friettruck-feest",
    "Verkoop: Nog één dag tot uw friettruck-feest",
    "Verkoop: Offerte aanpassing verzenden",
    "Verkoop: Offerte verzenden test 2.0",
    "Verkoop: Nog acht dagen tot uw friettruck-feest"
}


def migrate_templates_if_needed():
    """
    Migreer odoo_mail_templates.json naar templates.json als templates.json nog niet bestaat,
    of voeg ontbrekende FTH templates toe als templates.json al bestaat.
    """
    if not ODOO_TEMPLATES_FILE.exists():
        _LOG.warning("odoo_mail_templates.json niet gevonden, kan niet migreren")
        return
    
    try:
        # Lees oude structuur
        with open(ODOO_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            odoo_templates = json.load(f)
        
        # Lees bestaande templates als die al bestaan
        existing_templates: Dict[str, Dict[str, str]] = {}
        if TEMPLATES_FILE.exists():
            try:
                with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                    existing_templates = json.load(f)
                _LOG.info(f"Bestaande templates.json geladen: {len(existing_templates)} templates")
            except Exception as e:
                _LOG.warning(f"Kon bestaande templates.json niet laden: {e}")
        
        # Converteer FTH templates uit odoo_mail_templates.json
        fth_templates_from_odoo: Dict[str, Dict[str, str]] = {}
        for template in odoo_templates:
            naam = template.get("naam", "")
            body_html = template.get("body_html", "")
            
            # Alleen FTH templates migreren
            if naam and naam in FTH_TEMPLATE_NAMES:
                fth_templates_from_odoo[naam] = {
                    "original": body_html,
                    "revised": body_html  # Start met kopie van original
                }
        
        # Merge: behoud bestaande templates, update/voeg toe FTH templates
        # Als template al bestaat, behoud revised versie als die bestaat
        for naam, versions in fth_templates_from_odoo.items():
            if naam in existing_templates:
                # Behoud bestaande revised versie als die bestaat
                existing_revised = existing_templates[naam].get("revised")
                if existing_revised:
                    versions["revised"] = existing_revised
            existing_templates[naam] = versions
        
        # Sla op
        TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_templates, f, indent=2, ensure_ascii=False)
        
        _LOG.info(f"Migratie voltooid: {len(fth_templates_from_odoo)} FTH templates verwerkt")
        
    except Exception as e:
        _LOG.error(f"Fout bij migratie templates: {e}")
        raise


def load_templates() -> Dict[str, Dict[str, str]]:
    """Laad templates uit JSON bestand - alleen FTH templates"""
    if not TEMPLATES_FILE.exists():
        # Probeer migratie
        migrate_templates_if_needed()
    
    if not TEMPLATES_FILE.exists():
        return {}
    
    try:
        with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            all_templates = json.load(f)
        
        # Filter alleen FTH templates
        fth_templates = {
            naam: versions 
            for naam, versions in all_templates.items() 
            if naam in FTH_TEMPLATE_NAMES
        }
        
        return fth_templates
    except Exception as e:
        _LOG.error(f"Fout bij laden templates: {e}")
        raise HTTPException(status_code=500, detail=f"Kon templates niet laden: {str(e)}")


@router.get("/", response_class=HTMLResponse)
async def templates_overview(request: Request):
    """
    Simpele HTML pagina met tabel van template namen en URLs voor Figma plugin.
    """
    # Migreer indien nodig bij eerste start
    migrate_templates_if_needed()
    
    templates = load_templates()
    
    # Bepaal base URL uit request
    base_url = str(request.base_url).rstrip('/')
    
    html_content = """
    <!DOCTYPE html>
    <html lang="nl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mail Templates - FTH Portaal</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background-color: #f5f5f5;
                padding: 20px;
                color: #333;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                padding: 30px;
            }
            h1 {
                color: #2c3e50;
                margin-bottom: 30px;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #f8f9fa;
                font-weight: 600;
                color: #2c3e50;
            }
            tr:hover {
                background-color: #f8f9fa;
            }
            a {
                color: #3498db;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            .empty-state {
                text-align: center;
                padding: 40px;
                color: #999;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📧 Mail Templates</h1>
    """
    
    if not templates:
        html_content += '<div class="empty-state"><p>Geen templates gevonden.</p></div>'
    else:
        html_content += '<table><thead><tr><th>Template Naam</th><th>URL</th></tr></thead><tbody>'
        
        for template_naam in sorted(templates.keys()):
            # URL encoderen voor gebruik in URL
            encoded_naam = quote(template_naam, safe='')
            template_url = f"{base_url}/templates/{encoded_naam}/original"
            
            html_content += f"""
                <tr>
                    <td>{template_naam}</td>
                    <td><a href="{template_url}" target="_blank">{template_url}</a></td>
                </tr>
            """
        
        html_content += '</tbody></table>'
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.get("/{naam}/original")
async def get_template_original(naam: str):
    """
    Haal de original versie van een template op.
    Retourneert HTML voor preview (Figma plugin).
    """
    templates = load_templates()
    
    if naam not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{naam}' niet gevonden")
    
    html_content = templates[naam].get("original", "")
    
    return Response(content=html_content, media_type="text/html")


def load_email_template(naam: str) -> str:
    path = Path(__file__).parent / "email_templates" / naam
    return path.read_text(encoding="utf-8")


def format_dutch_date(dt) -> str:
    if not dt:
        return ""
    maanden = ["januari","februari","maart","april","mei","juni",
               "juli","augustus","september","oktober","november","december"]
    return f"{dt.day} {maanden[dt.month - 1]} {dt.year}"


def format_time(dt) -> str:
    if not dt:
        return ""
    return dt.strftime("%H:%M")


def format_currency(amount) -> str:
    if not amount:
        return "0,00"
    return f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def render_offerte_v10(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    datum_str: str,
    tijdstip: str,
    locatie: str,
    pakket_naam: str,
    totaal_str: str,
    bevestig_url: str,
    notitie_klant: str = ""
) -> str:
    html = load_email_template("offerte_v10.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{datum_str}", datum_str)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{pakket_naam}", pakket_naam)
    html = html.replace("{totaal_str}", totaal_str)
    html = html.replace("{bevestig_url}", bevestig_url)
    html = html.replace("{notitie_klant}", notitie_klant or "")
    return html


def render_bevestiging_a(voornaam: str) -> tuple:
    onderwerp = "Bedankt voor uw bevestiging — Friettruck-huren.nl"
    html = load_email_template("bevestiging_a.html")
    html = html.replace("{voornaam}", voornaam)
    return onderwerp, html


def render_bevestiging_b(voornaam: str) -> tuple:
    onderwerp = "Wij komen voor u bakken! — Friettruck-huren.nl"
    html = load_email_template("bevestiging_b.html")
    html = html.replace("{voornaam}", voornaam)
    return onderwerp, html


def render_planning_9dagen(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    broodjes_ja_nee: str,
    drankjes_ja_nee: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_9dagen.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{broodjes_ja_nee}", broodjes_ja_nee)
    html = html.replace("{drankjes_ja_nee}", drankjes_ja_nee)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    return html


def render_planning_7dagen(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    betaallink: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_7dagen.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    html = html.replace("{betaallink}", betaallink)
    return html


def render_planning_5dagen_betaald(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    afmeldlink: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_5dagen_betaald.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    html = html.replace("{afmeldlink}", afmeldlink)
    return html


def render_planning_5dagen_onbetaald(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    betaallink: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_5dagen_onbetaald.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    html = html.replace("{betaallink}", betaallink)
    return html


def render_planning_3dagen_betaald(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    afmeldlink: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_3dagen_betaald.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    html = html.replace("{afmeldlink}", afmeldlink)
    return html


def render_planning_3dagen_onbetaald(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    betaallink: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_3dagen_onbetaald.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    html = html.replace("{betaallink}", betaallink)
    return html


def render_planning_1dag_betaald(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    afmeldlink: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_1dag_betaald.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    html = html.replace("{afmeldlink}", afmeldlink)
    return html


def render_planning_1dag_onbetaald(
    voornaam: str,
    aantal_personen: int,
    aantal_kinderen: int,
    pakket: str,
    locatie: str,
    datum: str,
    tijdstip: str,
    totaal: str,
    partner_telefoon: str,
    betaallink: str,
    klant_adres: str = ""
) -> str:
    html = load_email_template("planning_1dag_onbetaald.html")
    html = html.replace("{voornaam}", voornaam)
    html = html.replace("{aantal_personen}", str(aantal_personen))
    html = html.replace("{aantal_kinderen}", str(aantal_kinderen))
    html = html.replace("{pakket}", pakket)
    html = html.replace("{locatie}", locatie)
    html = html.replace("{klant_adres}", klant_adres or "")
    html = html.replace("{datum}", datum)
    html = html.replace("{tijdstip}", tijdstip)
    html = html.replace("{totaal}", totaal)
    html = html.replace("{partner_telefoon}", partner_telefoon)
    html = html.replace("{betaallink}", betaallink)
    return html