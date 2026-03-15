"""
Designer preview routes voor mail templates.
Toegankelijk via /designer/{token} met token: fth-doreen-2026
"""
import logging
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import templates as templates_module

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/designer", tags=["designer"])

# Jinja2 templates directory - lazy initialization met directory check
def get_templates():
    """Lazy initialization van Jinja2Templates met directory check"""
    templates_dir = Path(__file__).parent / "templates_dir"
    templates_dir.mkdir(exist_ok=True)
    
    template_file = templates_dir / "designer_preview.html"
    if not template_file.exists():
        raise FileNotFoundError(
            f"Template bestand niet gevonden: {template_file}. "
            f"Zorg dat app/templates_dir/designer_preview.html bestaat."
        )
    
    return Jinja2Templates(directory=str(templates_dir))

# Initialiseer templates (kan nu crashen met duidelijke error)
templates = get_templates()

# Token voor toegang
DESIGNER_TOKEN = "fth-doreen-2026"

# Dummy data voor alle templates
DUMMY_DATA = {
    "voornaam": "Emma",
    "datum": "zaterdag 20 juni 2026",
    "datum_str": "zaterdag 20 juni 2026",
    "tijdstip": "17:00",
    "locatie": "Amsterdam",
    "pakket": "Verse Friet & Snacks",
    "pakket_naam": "Verse Friet & Snacks",
    "aantal_personen": 50,
    "aantal_kinderen": 8,
    "totaal": "€ 875,00",
    "totaal_str": "875,00",
    "factuurnummer": "FTH-2026-042",
    "betaallink": "#betaallink-voorbeeld",
    "bevestig_url": "#bevestiglink-voorbeeld",
    "afmeldlink": "#afmeldlink-voorbeeld",
    "partner_telefoon": "06-12345678",
    "notitie_klant": ""
}

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "email_templates"


def check_token(token: str) -> None:
    """Check of token geldig is, anders 404"""
    if token != DESIGNER_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")


def detect_categorie(bestandsnaam: str) -> str:
    """Detecteer categorie op basis van bestandsnaam prefix"""
    if bestandsnaam.startswith("offerte_"):
        return "Offerte"
    elif bestandsnaam.startswith("bevestiging_"):
        return "Bevestiging"
    elif bestandsnaam.startswith("herinnering_"):
        return "Herinnering"
    elif bestandsnaam.startswith("planning_"):
        return "Planning"
    else:
        return "Overig"


def render_template_with_dummy_data(template_key: str, render_func) -> str | None:
    """
    Roep render functie aan met dummy data.
    Expliciete mapping voor bekende functies, try/except voor overige.
    """
    try:
        if template_key == "offerte_v10":
            return render_func(
                voornaam=DUMMY_DATA["voornaam"],
                aantal_personen=DUMMY_DATA["aantal_personen"],
                aantal_kinderen=DUMMY_DATA["aantal_kinderen"],
                datum_str=DUMMY_DATA["datum_str"],
                tijdstip=DUMMY_DATA["tijdstip"],
                locatie=DUMMY_DATA["locatie"],
                pakket_naam=DUMMY_DATA["pakket_naam"],
                totaal_str=DUMMY_DATA["totaal_str"],
                bevestig_url=DUMMY_DATA["bevestig_url"],
                notitie_klant=DUMMY_DATA.get("notitie_klant", "")
            )
        elif template_key == "bevestiging_a":
            result = render_func(voornaam=DUMMY_DATA["voornaam"])
            return result[1]  # HTML is tweede element in tuple
        elif template_key == "bevestiging_b":
            result = render_func(voornaam=DUMMY_DATA["voornaam"])
            return result[1]  # HTML is tweede element in tuple
        else:
            # Voor toekomstige functies: probeer met **DUMMY_DATA
            try:
                result = render_func(**DUMMY_DATA)
                # Als result een tuple is, pak het tweede element
                if isinstance(result, tuple):
                    return result[1]
                return result
            except Exception as e:
                _LOG.warning(f"Kon template {template_key} niet renderen: {e}")
                return None
    except Exception as e:
        _LOG.warning(f"Fout bij renderen template {template_key}: {e}")
        return None


def scan_templates() -> list:
    """
    Scan email_templates directory en retourneer lijst van template data.
    """
    template_list = []
    
    if not TEMPLATES_DIR.exists():
        _LOG.warning(f"Templates directory niet gevonden: {TEMPLATES_DIR}")
        return template_list
    
    # Scan alle .html bestanden
    for html_file in sorted(TEMPLATES_DIR.glob("*.html")):
        template_key = html_file.stem  # bestandsnaam zonder .html
        categorie = detect_categorie(html_file.name)
        
        # Lees raw HTML
        try:
            raw_html = html_file.read_text(encoding="utf-8")
        except Exception as e:
            _LOG.error(f"Kon {html_file.name} niet lezen: {e}")
            raw_html = ""
        
        # Zoek render functie
        render_func_name = f"render_{template_key}"
        render_func = getattr(templates_module, render_func_name, None)
        
        # Render met dummy data als functie bestaat
        rendered_html = None
        status = "niet_gebouwd"
        
        if render_func is not None:
            rendered_html = render_template_with_dummy_data(template_key, render_func)
            if rendered_html is not None:
                status = "gebouwd"
        
        # Display naam: vervang underscores met spaties en capitalize
        display_naam = template_key.replace("_", " ").title()
        
        template_list.append({
            "key": template_key,
            "display_naam": display_naam,
            "categorie": categorie,
            "status": status,
            "rendered_html": rendered_html,
            "raw_html": raw_html
        })
    
    return template_list


@router.get("/{token}")
async def get_designer_preview(token: str, request: Request):
    """
    Designer preview pagina met alle templates.
    """
    check_token(token)
    
    # Scan templates directory
    template_list = scan_templates()
    
    # Check voor upload success query parameter
    uploaded_key = request.query_params.get("uploaded")
    
    # Render Jinja2 template
    return templates.TemplateResponse(
        "designer_preview.html",
        {
            "request": request,
            "templates": template_list,
            "token": token,
            "uploaded_key": uploaded_key
        }
    )


@router.post("/{token}/upload/{template_naam}")
async def upload_template(
    token: str,
    template_naam: str,
    file: UploadFile = File(...)
):
    """
    Upload een HTML template bestand.
    """
    check_token(token)
    
    # Valideer bestandsnaam (alleen alphanumeric, underscore, koppelteken, .html extensie)
    if not re.match(r'^[a-zA-Z0-9_-]+\.html$', template_naam):
        raise HTTPException(
            status_code=400,
            detail="Ongeldige bestandsnaam. Alleen letters, cijfers, underscores en koppeltekens toegestaan."
        )
    
    # Valideer bestandsgrootte (max 500kb)
    content = await file.read()
    if len(content) > 500 * 1024:  # 500kb
        raise HTTPException(
            status_code=400,
            detail="Bestand te groot. Maximum 500KB toegestaan."
        )
    
    # Valideer dat bestand eindigt op .html
    if not template_naam.endswith(".html"):
        raise HTTPException(
            status_code=400,
            detail="Alleen .html bestanden toegestaan."
        )
    
    # Sla bestand op
    target_path = TEMPLATES_DIR / template_naam
    
    try:
        target_path.write_text(content.decode("utf-8"), encoding="utf-8")
        _LOG.info(f"Template {template_naam} succesvol geüpload")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Bestand bevat geen geldige UTF-8 tekst."
        )
    except Exception as e:
        _LOG.error(f"Fout bij opslaan {template_naam}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Fout bij opslaan bestand: {str(e)}"
        )
    
    # Redirect terug naar designer pagina met success indicator
    template_key = template_naam.replace(".html", "")
    return RedirectResponse(
        url=f"/designer/{token}?uploaded={template_key}",
        status_code=303
    )
