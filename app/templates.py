"""
Template beheer endpoints voor mail templates.
"""
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from typing import Dict, Any

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])

# Bestandspaden
PROJECT_ROOT = Path(__file__).parent.parent
ODOO_TEMPLATES_FILE = PROJECT_ROOT / "docs" / "odoo_mail_templates.json"
TEMPLATES_FILE = PROJECT_ROOT / "docs" / "templates.json"


def migrate_templates_if_needed():
    """
    Migreer odoo_mail_templates.json naar templates.json als templates.json nog niet bestaat.
    """
    if TEMPLATES_FILE.exists():
        _LOG.info("templates.json bestaat al, geen migratie nodig")
        return
    
    if not ODOO_TEMPLATES_FILE.exists():
        _LOG.warning("odoo_mail_templates.json niet gevonden, kan niet migreren")
        return
    
    try:
        # Lees oude structuur
        with open(ODOO_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            odoo_templates = json.load(f)
        
        # Converteer naar nieuwe structuur
        new_structure: Dict[str, Dict[str, str]] = {}
        
        for template in odoo_templates:
            naam = template.get("naam", "")
            body_html = template.get("body_html", "")
            
            if naam:
                new_structure[naam] = {
                    "original": body_html,
                    "revised": body_html  # Start met kopie van original
                }
        
        # Sla nieuwe structuur op
        TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_structure, f, indent=2, ensure_ascii=False)
        
        _LOG.info(f"Migratie voltooid: {len(new_structure)} templates gemigreerd naar templates.json")
        
    except Exception as e:
        _LOG.error(f"Fout bij migratie templates: {e}")
        raise


def load_templates() -> Dict[str, Dict[str, str]]:
    """Laad templates uit JSON bestand"""
    if not TEMPLATES_FILE.exists():
        # Probeer migratie
        migrate_templates_if_needed()
    
    if not TEMPLATES_FILE.exists():
        return {}
    
    try:
        with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        _LOG.error(f"Fout bij laden templates: {e}")
        raise HTTPException(status_code=500, detail=f"Kon templates niet laden: {str(e)}")


def save_templates(templates: Dict[str, Dict[str, str]]):
    """Sla templates op in JSON bestand"""
    try:
        TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=2, ensure_ascii=False)
        _LOG.info("Templates opgeslagen")
    except Exception as e:
        _LOG.error(f"Fout bij opslaan templates: {e}")
        raise HTTPException(status_code=500, detail=f"Kon templates niet opslaan: {str(e)}")


@router.get("/", response_class=HTMLResponse)
async def templates_overview(request: Request):
    """
    HTML pagina met overzicht van alle templates.
    """
    # Migreer indien nodig bij eerste start
    migrate_templates_if_needed()
    
    templates = load_templates()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="nl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Template Beheer - FTH Portaal</title>
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
            .template-item {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 20px;
                margin-bottom: 20px;
                background: #fafafa;
            }
            .template-item h2 {
                color: #2c3e50;
                margin-bottom: 15px;
                font-size: 1.3em;
            }
            .template-actions {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            button {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                transition: background-color 0.2s;
            }
            .btn-preview {
                background-color: #3498db;
                color: white;
            }
            .btn-preview:hover {
                background-color: #2980b9;
            }
            .btn-save {
                background-color: #27ae60;
                color: white;
            }
            .btn-save:hover {
                background-color: #229954;
            }
            .btn-reset {
                background-color: #e74c3c;
                color: white;
            }
            .btn-reset:hover {
                background-color: #c0392b;
            }
            textarea {
                width: 100%;
                min-height: 300px;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                resize: vertical;
            }
            .message {
                padding: 10px;
                border-radius: 4px;
                margin-bottom: 15px;
                display: none;
            }
            .message.success {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .message.error {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
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
            <h1>📧 Mail Template Beheer</h1>
            <div id="templates-container">
    """
    
    if not templates:
        html_content += '<div class="empty-state"><p>Geen templates gevonden.</p></div>'
    else:
        for template_naam, versions in templates.items():
            # Escape template naam voor gebruik in JavaScript
            safe_naam = template_naam.replace('"', '&quot;').replace("'", "&#39;")
            original_html = versions.get("original", "")
            revised_html = versions.get("revised", original_html)
            
            html_content += f"""
                <div class="template-item">
                    <h2>{template_naam}</h2>
                    <div class="message" id="message-{safe_naam}"></div>
                    <div class="template-actions">
                        <button class="btn-preview" onclick="preview('{safe_naam}', 'original')">👁️ Preview Original</button>
                        <button class="btn-preview" onclick="preview('{safe_naam}', 'revised')">👁️ Preview Revised</button>
                        <button class="btn-save" onclick="save('{safe_naam}')">💾 Opslaan</button>
                        <button class="btn-reset" onclick="reset('{safe_naam}')">🔄 Reset naar Original</button>
                    </div>
                    <textarea id="editor-{safe_naam}" name="revised">{revised_html}</textarea>
                </div>
            """
    
    html_content += """
            </div>
        </div>
        <script>
            function preview(naam, versie) {
                const url = `/templates/${encodeURIComponent(naam)}/${versie}`;
                window.open(url, '_blank');
            }
            
            async function save(naam) {
                const editor = document.getElementById(`editor-${naam}`);
                const html = editor.value;
                const messageDiv = document.getElementById(`message-${naam}`);
                
                try {
                    const response = await fetch(`/templates/${encodeURIComponent(naam)}/revised`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ html: html })
                    });
                    
                    if (response.ok) {
                        showMessage(naam, 'Template opgeslagen!', 'success');
                    } else {
                        const error = await response.json();
                        showMessage(naam, 'Fout: ' + (error.detail || 'Onbekende fout'), 'error');
                    }
                } catch (error) {
                    showMessage(naam, 'Fout: ' + error.message, 'error');
                }
            }
            
            async function reset(naam) {
                if (!confirm('Weet je zeker dat je de revised versie wilt resetten naar original?')) {
                    return;
                }
                
                try {
                    const response = await fetch(`/templates/${encodeURIComponent(naam)}/original`);
                    if (response.ok) {
                        const html = await response.text();
                        const editor = document.getElementById(`editor-${naam}`);
                        editor.value = html;
                        showMessage(naam, 'Reset naar original!', 'success');
                    } else {
                        showMessage(naam, 'Fout bij ophalen original', 'error');
                    }
                } catch (error) {
                    showMessage(naam, 'Fout: ' + error.message, 'error');
                }
            }
            
            function showMessage(naam, text, type) {
                const messageDiv = document.getElementById(`message-${naam}`);
                messageDiv.textContent = text;
                messageDiv.className = `message ${type}`;
                messageDiv.style.display = 'block';
                
                setTimeout(() => {
                    messageDiv.style.display = 'none';
                }, 3000);
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@router.get("/{naam}/{versie}")
async def get_template_version(naam: str, versie: str):
    """
    Haal een specifieke versie van een template op (original of revised).
    Retourneert HTML voor preview.
    """
    if versie not in ["original", "revised"]:
        raise HTTPException(status_code=400, detail="Versie moet 'original' of 'revised' zijn")
    
    templates = load_templates()
    
    if naam not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{naam}' niet gevonden")
    
    html_content = templates[naam].get(versie, "")
    
    return Response(content=html_content, media_type="text/html")


@router.put("/{naam}/revised")
async def update_revised_template(naam: str, request: Request):
    """
    Update de revised versie van een template.
    Body: { "html": "..." }
    """
    templates = load_templates()
    
    if naam not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{naam}' niet gevonden")
    
    try:
        body = await request.json()
        html = body.get("html", "")
        
        if not html:
            raise HTTPException(status_code=400, detail="html veld is verplicht")
        
        templates[naam]["revised"] = html
        save_templates(templates)
        
        return {"status": "success", "message": f"Template '{naam}' bijgewerkt"}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ongeldig JSON formaat")
    except Exception as e:
        _LOG.error(f"Fout bij updaten template: {e}")
        raise HTTPException(status_code=500, detail=f"Fout bij opslaan: {str(e)}")
