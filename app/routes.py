from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.odoo_client import OdooClient
from app.auth import PartnerAuth
import logging

_LOG = logging.getLogger(__name__)

router = APIRouter()
partner_auth = PartnerAuth()

def get_partner_from_session(request: Request) -> dict:
    """Haal partner informatie uit de sessie"""
    partner = request.session.get("partner")
    if not partner:
        raise HTTPException(status_code=401, detail="Niet ingelogd")
    return partner

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Toon login pagina"""
    # Als al ingelogd, redirect naar dashboard
    if request.session.get("partner"):
        return RedirectResponse(url="/dashboard", status_code=303)
    
    html_content = """
    <!DOCTYPE html>
    <html lang="nl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FTH Portaal - Inloggen</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .login-container {
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                width: 100%;
                max-width: 400px;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 28px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 500;
                font-size: 14px;
            }
            input[type="email"],
            input[type="password"] {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input[type="email"]:focus,
            input[type="password"]:focus {
                outline: none;
                border-color: #667eea;
            }
            button {
                width: 100%;
                padding: 14px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
            }
            button:active {
                transform: translateY(0);
            }
            .error {
                background: #fee;
                color: #c33;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 20px;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>FTH Portaal</h1>
            <p class="subtitle">Inloggen voor leveranciers</p>
            <form method="post" action="/login">
                <div class="form-group">
                    <label for="email">E-mailadres</label>
                    <input type="email" id="email" name="email" required autofocus>
                </div>
                <div class="form-group">
                    <label for="password">Wachtwoord</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit">Inloggen</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Verwerk login"""
    partner = partner_auth.authenticate_partner(email, password)
    
    if not partner:
        html_content = """
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Portaal - Inloggen</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }
                .login-container {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    padding: 40px;
                    width: 100%;
                    max-width: 400px;
                }
                h1 {
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 28px;
                }
                .subtitle {
                    color: #666;
                    margin-bottom: 30px;
                    font-size: 14px;
                }
                .error {
                    background: #fee;
                    color: #c33;
                    padding: 12px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    font-size: 14px;
                }
                .form-group {
                    margin-bottom: 20px;
                }
                label {
                    display: block;
                    margin-bottom: 8px;
                    color: #333;
                    font-weight: 500;
                    font-size: 14px;
                }
                input[type="email"],
                input[type="password"] {
                    width: 100%;
                    padding: 12px 16px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 16px;
                    transition: border-color 0.3s;
                }
                input[type="email"]:focus,
                input[type="password"]:focus {
                    outline: none;
                    border-color: #667eea;
                }
                button {
                    width: 100%;
                    padding: 14px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
                }
            </style>
        </head>
        <body>
            <div class="login-container">
                <h1>FTH Portaal</h1>
                <p class="subtitle">Inloggen voor leveranciers</p>
                <div class="error">Ongeldige inloggegevens. Probeer het opnieuw.</div>
                <form method="post" action="/login">
                    <div class="form-group">
                        <label for="email">E-mailadres</label>
                        <input type="email" id="email" name="email" required autofocus>
                    </div>
                    <div class="form-group">
                        <label for="password">Wachtwoord</label>
                        <input type="password" id="password" name="password" required>
                    </div>
                    <button type="submit">Inloggen</button>
                </form>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=401)
    
    # Sla partner info op in sessie
    request.session["partner"] = partner
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/logout")
async def logout(request: Request):
    """Logout"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard met beschikbare inkooporders"""
    partner = get_partner_from_session(request)
    
    try:
        client = OdooClient()
        
        # Haal inkooporders op die nog geen partner hebben
        # In Odoo betekent partner_id = False dat het veld leeg is
        # We kunnen ook zoeken naar POs in draft of sent state zonder partner
        pos = client.execute_kw(
            "purchase.order",
            "search_read",
            [[["partner_id", "=", False]]],
            {
                "fields": ["id", "name", "date_order", "amount_total", "state"],
                "order": "date_order desc",
                "limit": 50
            }
        )
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Portaal - Dashboard</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: #f5f5f5;
                    min-height: 100vh;
                    padding: 20px;
                }}
                .header {{
                    background: white;
                    padding: 20px 30px;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .header h1 {{
                    color: #333;
                    font-size: 24px;
                }}
                .user-info {{
                    display: flex;
                    align-items: center;
                    gap: 20px;
                }}
                .user-name {{
                    color: #666;
                    font-size: 14px;
                }}
                .logout-btn {{
                    padding: 8px 16px;
                    background: #dc3545;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-size: 14px;
                    transition: background 0.3s;
                }}
                .logout-btn:hover {{
                    background: #c82333;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .po-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 20px;
                }}
                .po-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    transition: transform 0.2s, box-shadow 0.2s;
                }}
                .po-card:hover {{
                    transform: translateY(-4px);
                    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                }}
                .po-name {{
                    font-size: 18px;
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 8px;
                }}
                .po-detail {{
                    color: #666;
                    font-size: 14px;
                    margin-bottom: 4px;
                }}
                .po-amount {{
                    font-size: 20px;
                    font-weight: 700;
                    color: #667eea;
                    margin: 12px 0;
                }}
                .claim-btn {{
                    width: 100%;
                    padding: 12px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s, box-shadow 0.2s;
                    margin-top: 12px;
                }}
                .claim-btn:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 15px rgba(102, 126, 234, 0.4);
                }}
                .claim-btn:disabled {{
                    background: #ccc;
                    cursor: not-allowed;
                    transform: none;
                }}
                .success-message {{
                    background: #d4edda;
                    color: #155724;
                    padding: 12px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 60px 20px;
                    color: #666;
                }}
                .empty-state h2 {{
                    margin-bottom: 10px;
                    color: #333;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Beschikbare Inkooporders</h1>
                    <div class="user-info">
                        <span class="user-name">Ingelogd als: {partner['name']}</span>
                        <a href="/logout" class="logout-btn">Uitloggen</a>
                    </div>
                </div>
                
                <div id="message-container"></div>
                
                <div class="po-grid">
        """
        
        if not pos:
            html_content += """
                    <div class="empty-state" style="grid-column: 1 / -1;">
                        <h2>Geen beschikbare inkooporders</h2>
                        <p>Er zijn momenteel geen inkooporders beschikbaar om te claimen.</p>
                    </div>
            """
        else:
            for po in pos:
                po_id = po.get('id')
                po_name = po.get('name', 'N/A')
                po_date = po.get('date_order', '')[:10] if po.get('date_order') else 'N/A'
                po_amount = po.get('amount_total', 0)
                po_state = po.get('state', 'N/A')
                
                html_content += f"""
                    <div class="po-card">
                        <div class="po-name">{po_name}</div>
                        <div class="po-detail">Datum: {po_date}</div>
                        <div class="po-detail">Status: {po_state}</div>
                        <div class="po-amount">€ {po_amount:,.2f}</div>
                        <button class="claim-btn" onclick="claimPO({po_id}, '{po_name}')">
                            Claim Inkooporder
                        </button>
                    </div>
                """
        
        html_content += """
                </div>
            </div>
            
            <script>
                async function claimPO(poId, poName) {
                    const btn = event.target;
                    btn.disabled = true;
                    btn.textContent = 'Bezig met claimen...';
                    
                    try {
                        const response = await fetch(`/api/claim-po/${poId}`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            }
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok) {
                            showMessage(`Succesvol! Inkooporder ${poName} is geclaimd.`, 'success');
                            // Verwijder de kaart na 2 seconden
                            setTimeout(() => {
                                btn.closest('.po-card').remove();
                            }, 2000);
                        } else {
                            showMessage(result.detail || 'Fout bij claimen van inkooporder.', 'error');
                            btn.disabled = false;
                            btn.textContent = 'Claim Inkooporder';
                        }
                    } catch (error) {
                        showMessage('Er is een fout opgetreden. Probeer het opnieuw.', 'error');
                        btn.disabled = false;
                        btn.textContent = 'Claim Inkooporder';
                    }
                }
                
                function showMessage(message, type) {
                    const container = document.getElementById('message-container');
                    const div = document.createElement('div');
                    div.className = type === 'success' ? 'success-message' : 'error-message';
                    div.style.background = type === 'success' ? '#d4edda' : '#f8d7da';
                    div.style.color = type === 'success' ? '#155724' : '#721c24';
                    div.style.padding = '12px';
                    div.style.borderRadius = '8px';
                    div.style.marginBottom = '20px';
                    div.textContent = message;
                    container.innerHTML = '';
                    container.appendChild(div);
                    
                    setTimeout(() => {
                        div.remove();
                    }, 5000);
                }
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        _LOG.error(f"Dashboard fout: {e}")
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen van inkooporders: {str(e)}")

@router.post("/api/claim-po/{po_id}")
async def claim_po(request: Request, po_id: int):
    """Claim een inkooporder door partner_id te updaten"""
    partner = get_partner_from_session(request)
    
    try:
        client = OdooClient()
        
        # Update de purchase order met de partner_id
        client.execute_kw(
            "purchase.order",
            "write",
            [[po_id], {"partner_id": partner["id"]}]
        )
        
        return {
            "success": True,
            "message": f"Inkooporder is succesvol geclaimd door {partner['name']}",
            "po_id": po_id,
            "partner_id": partner["id"]
        }
    
    except Exception as e:
        _LOG.error(f"Claim PO fout: {e}")
        raise HTTPException(status_code=500, detail=f"Fout bij claimen van inkooporder: {str(e)}")
