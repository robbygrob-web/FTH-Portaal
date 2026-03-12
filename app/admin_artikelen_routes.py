"""
Admin artikelen beheer endpoints.
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import SESSION_SECRET
from app.admin_routes import verify_admin_session, get_database_url

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/artikelen", tags=["admin"])


@router.get("", response_class=HTMLResponse)
async def artikelen_overzicht(request: Request, verified: bool = Depends(verify_admin_session)):
    """Overzichtspagina voor artikelen beheer"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Haal alle artikelen op
        cur.execute("""
            SELECT id, naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl, actief
            FROM artikelen
            ORDER BY naam
        """)
        
        artikelen = cur.fetchall()
        
        # Build artikelen tabel rows
        artikelen_rows = ""
        for artikel in artikelen:
            artikel_id = str(artikel.get("id"))
            naam = artikel.get("naam") or ""
            prijs_excl = float(artikel.get("prijs_excl", 0))
            btw_pct = float(artikel.get("btw_pct", 9))
            btw_bedrag = float(artikel.get("btw_bedrag", 0))
            prijs_incl = float(artikel.get("prijs_incl", 0))
            actief = artikel.get("actief", True)
            
            artikelen_rows += f"""
            <tr data-artikel-id="{artikel_id}">
                <td><input type="text" class="artikel-naam" value="{naam}" data-artikel-id="{artikel_id}" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;"></td>
                <td><input type="number" class="artikel-prijs-excl" value="{prijs_excl:.2f}" step="0.01" data-artikel-id="{artikel_id}" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;"></td>
                <td><input type="number" class="artikel-btw-pct" value="{btw_pct:.2f}" step="0.01" data-artikel-id="{artikel_id}" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;"></td>
                <td><input type="number" class="artikel-btw-bedrag" value="{btw_bedrag:.2f}" step="0.01" data-artikel-id="{artikel_id}" readonly style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;background:#f5f5f5;"></td>
                <td><input type="number" class="artikel-prijs-incl" value="{prijs_incl:.2f}" step="0.01" data-artikel-id="{artikel_id}" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;"></td>
                <td>
                    <label style="display:flex;align-items:center;gap:8px;">
                        <input type="checkbox" class="artikel-actief" {"checked" if actief else ""} data-artikel-id="{artikel_id}">
                        <span>Actief</span>
                    </label>
                </td>
                <td>
                    <button type="button" class="btn-save-artikel" data-artikel-id="{artikel_id}" style="padding:6px 12px;background:#28a745;color:white;border:none;border-radius:4px;cursor:pointer;">Opslaan</button>
                </td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Admin - Artikelen</title>
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
                }}
                .header h1 {{
                    color: #333333;
                    margin-bottom: 10px;
                }}
                .back-link {{
                    color: #666;
                    text-decoration: none;
                    margin-bottom: 20px;
                    display: inline-block;
                }}
                .section {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .section h2 {{
                    color: #333333;
                    margin-bottom: 15px;
                    font-size: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
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
                    padding: 8px 12px;
                    border-bottom: 1px solid #e0e0e0;
                }}
                tr:hover {{
                    background: #f9f9f9;
                }}
                .btn {{
                    padding: 10px 20px;
                    background: #fec82a;
                    color: #333333;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 700;
                    cursor: pointer;
                }}
                .btn:hover {{
                    background: #e2af13;
                }}
                .add-artikel-form {{
                    display: grid;
                    grid-template-columns: 2fr 1fr 1fr 1fr auto;
                    gap: 10px;
                    align-items: end;
                    margin-top: 20px;
                }}
                .add-artikel-form input {{
                    padding: 10px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 14px;
                }}
                .add-artikel-form input:focus {{
                    outline: none;
                    border-color: #fec82a;
                }}
                .message {{
                    padding: 12px;
                    border-radius: 8px;
                    margin-bottom: 15px;
                    display: none;
                }}
                .message.success {{
                    background: #d4edda;
                    color: #155724;
                    border: 1px solid #c3e6cb;
                }}
                .message.error {{
                    background: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <a href="/admin?token={SESSION_SECRET}" class="back-link">← Terug naar dashboard</a>
                <h1>Artikelen Beheer</h1>
            </div>
            
            <div class="section">
                <h2>Bestaande Artikelen</h2>
                <div id="message" class="message"></div>
                <table>
                    <thead>
                        <tr>
                            <th>Naam</th>
                            <th>Prijs excl. BTW</th>
                            <th>BTW%</th>
                            <th>BTW bedrag</th>
                            <th>Prijs incl. BTW</th>
                            <th>Actief</th>
                            <th>Actie</th>
                        </tr>
                    </thead>
                    <tbody>
                        {artikelen_rows if artikelen_rows else '<tr><td colspan="7" style="text-align:center;padding:20px;">Geen artikelen gevonden</td></tr>'}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2>Nieuw Artikel Toevoegen</h2>
                <form id="add-artikel-form" class="add-artikel-form">
                    <input type="text" id="nieuwe-naam" placeholder="Artikel naam" required>
                    <input type="number" id="nieuwe-prijs-incl" placeholder="Prijs incl. BTW" step="0.01" min="0" required>
                    <input type="number" id="nieuwe-btw-pct" placeholder="BTW%" step="0.01" value="9" min="0" max="100" required>
                    <input type="number" id="nieuwe-prijs-excl" placeholder="Prijs excl. BTW" step="0.01" readonly style="background:#f5f5f5;">
                    <button type="submit" class="btn">Toevoegen</button>
                </form>
            </div>
            
            <script>
                const token = '{SESSION_SECRET}';
                const messageDiv = document.getElementById('message');
                
                function showMessage(text, type) {{
                    messageDiv.textContent = text;
                    messageDiv.className = `message ${{type}}`;
                    messageDiv.style.display = 'block';
                    setTimeout(() => {{
                        messageDiv.style.display = 'none';
                    }}, 3000);
                }}
                
                // Auto-bereken prijs_excl en btw_bedrag bij wijziging prijs_incl
                document.querySelectorAll('.artikel-prijs-incl').forEach(function(input) {{
                    input.addEventListener('input', function() {{
                        const row = input.closest('tr');
                        const prijsIncl = parseFloat(input.value) || 0;
                        const btwPct = parseFloat(row.querySelector('.artikel-btw-pct').value) || 9;
                        
                        const prijsExcl = prijsIncl / (1 + btwPct / 100);
                        const btwBedrag = prijsIncl - prijsExcl;
                        
                        row.querySelector('.artikel-prijs-excl').value = prijsExcl.toFixed(2);
                        row.querySelector('.artikel-btw-bedrag').value = btwBedrag.toFixed(2);
                    }});
                }});
                
                // Auto-bereken bij wijziging BTW%
                document.querySelectorAll('.artikel-btw-pct').forEach(function(input) {{
                    input.addEventListener('input', function() {{
                        const row = input.closest('tr');
                        const prijsIncl = parseFloat(row.querySelector('.artikel-prijs-incl').value) || 0;
                        const btwPct = parseFloat(input.value) || 9;
                        
                        const prijsExcl = prijsIncl / (1 + btwPct / 100);
                        const btwBedrag = prijsIncl - prijsExcl;
                        
                        row.querySelector('.artikel-prijs-excl').value = prijsExcl.toFixed(2);
                        row.querySelector('.artikel-btw-bedrag').value = btwBedrag.toFixed(2);
                    }});
                }});
                
                // Auto-bereken voor nieuw artikel formulier
                document.getElementById('nieuwe-prijs-incl').addEventListener('input', function() {{
                    const prijsIncl = parseFloat(this.value) || 0;
                    const btwPct = parseFloat(document.getElementById('nieuwe-btw-pct').value) || 9;
                    const prijsExcl = prijsIncl / (1 + btwPct / 100);
                    document.getElementById('nieuwe-prijs-excl').value = prijsExcl.toFixed(2);
                }});
                
                document.getElementById('nieuwe-btw-pct').addEventListener('input', function() {{
                    const prijsIncl = parseFloat(document.getElementById('nieuwe-prijs-incl').value) || 0;
                    const btwPct = parseFloat(this.value) || 9;
                    const prijsExcl = prijsIncl / (1 + btwPct / 100);
                    document.getElementById('nieuwe-prijs-excl').value = prijsExcl.toFixed(2);
                }});
                
                // Opslaan artikel
                document.querySelectorAll('.btn-save-artikel').forEach(function(btn) {{
                    btn.addEventListener('click', function() {{
                        const artikelId = this.getAttribute('data-artikel-id');
                        const row = this.closest('tr');
                        
                        const data = {{
                            naam: row.querySelector('.artikel-naam').value,
                            prijs_excl: parseFloat(row.querySelector('.artikel-prijs-excl').value),
                            btw_pct: parseFloat(row.querySelector('.artikel-btw-pct').value),
                            btw_bedrag: parseFloat(row.querySelector('.artikel-btw-bedrag').value),
                            prijs_incl: parseFloat(row.querySelector('.artikel-prijs-incl').value),
                            actief: row.querySelector('.artikel-actief').checked
                        }};
                        
                        fetch(`/admin/artikelen/${{artikelId}}/update?token=${{token}}`, {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify(data)
                        }})
                        .then(r => r.json())
                        .then(result => {{
                            if (result.success) {{
                                showMessage('Artikel opgeslagen!', 'success');
                            }} else {{
                                showMessage('Fout bij opslaan: ' + (result.detail || 'Onbekende fout'), 'error');
                            }}
                        }})
                        .catch(error => {{
                            showMessage('Fout bij opslaan: ' + error.message, 'error');
                        }});
                    }});
                }});
                
                // Nieuw artikel toevoegen
                document.getElementById('add-artikel-form').addEventListener('submit', function(e) {{
                    e.preventDefault();
                    
                    const prijsIncl = parseFloat(document.getElementById('nieuwe-prijs-incl').value);
                    const btwPct = parseFloat(document.getElementById('nieuwe-btw-pct').value);
                    const prijsExcl = prijsIncl / (1 + btwPct / 100);
                    const btwBedrag = prijsIncl - prijsExcl;
                    
                    const data = {{
                        naam: document.getElementById('nieuwe-naam').value,
                        prijs_excl: prijsExcl,
                        btw_pct: btwPct,
                        btw_bedrag: btwBedrag,
                        prijs_incl: prijsIncl,
                        actief: true
                    }};
                    
                    fetch(`/admin/artikelen/toevoegen?token=${{token}}`, {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(data)
                    }})
                    .then(r => r.json())
                    .then(result => {{
                        if (result.success) {{
                            showMessage('Artikel toegevoegd!', 'success');
                            setTimeout(() => {{
                                window.location.reload();
                            }}, 1000);
                        }} else {{
                            showMessage('Fout bij toevoegen: ' + (result.detail || 'Onbekende fout'), 'error');
                        }}
                    }})
                    .catch(error => {{
                        showMessage('Fout bij toevoegen: ' + error.message, 'error');
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        _LOG.error(f"Fout bij ophalen artikelen: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen artikelen: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/{artikel_id}/update")
async def update_artikel(
    request: Request,
    artikel_id: str,
    verified: bool = Depends(verify_admin_session)
):
    """Update een artikel"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        body = await request.json()
        
        naam = body.get("naam", "").strip()
        prijs_excl = float(body.get("prijs_excl", 0))
        btw_pct = float(body.get("btw_pct", 9))
        btw_bedrag = float(body.get("btw_bedrag", 0))
        prijs_incl = float(body.get("prijs_incl", 0))
        actief = body.get("actief", True)
        
        if not naam:
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "Naam is verplicht"}
            )
        
        cur.execute("""
            UPDATE artikelen
            SET naam = %s,
                prijs_excl = %s,
                btw_pct = %s,
                btw_bedrag = %s,
                prijs_incl = %s,
                actief = %s
            WHERE id = %s
        """, (naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl, actief, artikel_id))
        
        conn.commit()
        
        return JSONResponse(content={"success": True})
        
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij updaten artikel: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Fout bij updaten artikel: {str(e)}"}
        )
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/toevoegen")
async def toevoegen_artikel(
    request: Request,
    verified: bool = Depends(verify_admin_session)
):
    """Voeg een nieuw artikel toe"""
    conn = None
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        body = await request.json()
        
        naam = body.get("naam", "").strip()
        prijs_excl = float(body.get("prijs_excl", 0))
        btw_pct = float(body.get("btw_pct", 9))
        btw_bedrag = float(body.get("btw_bedrag", 0))
        prijs_incl = float(body.get("prijs_incl", 0))
        actief = body.get("actief", True)
        
        if not naam:
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "Naam is verplicht"}
            )
        
        # Check of artikel met deze naam al bestaat
        cur.execute("SELECT id FROM artikelen WHERE naam = %s", (naam,))
        if cur.fetchone():
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "Artikel met deze naam bestaat al"}
            )
        
        cur.execute("""
            INSERT INTO artikelen (naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl, actief, odoo_id)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
        """, (naam, prijs_excl, btw_pct, btw_bedrag, prijs_incl, actief))
        
        conn.commit()
        
        return JSONResponse(content={"success": True})
        
    except Exception as e:
        if conn:
            conn.rollback()
        _LOG.error(f"Fout bij toevoegen artikel: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Fout bij toevoegen artikel: {str(e)}"}
        )
    finally:
        if conn:
            cur.close()
            conn.close()
