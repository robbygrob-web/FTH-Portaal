from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.odoo_client import get_odoo_client
from app.auth import get_partner_auth
import logging

_LOG = logging.getLogger(__name__)

router = APIRouter()

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
    partner_auth = get_partner_auth()
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
    
    # Redirect naar dashboard
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_get(request: Request):
    """Onboarding form voor partner gegevens"""
    partner = get_partner_from_session(request)
    
    html_content = """
    <!DOCTYPE html>
    <html lang="nl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FTH Portaal - Onboarding</title>
    </head>
    <body>
        <h1>Onboarding</h1>
        <p>Vul uw gegevens in om verder te gaan.</p>
        <form method="post" action="/onboarding">
            <div>
                <label for="name">Bedrijfsnaam:</label>
                <input type="text" id="name" name="name" autocomplete="organization" required>
            </div>
            <div>
                <label for="street">Straat:</label>
                <input type="text" id="street" name="street" autocomplete="street-address">
            </div>
            <div>
                <label for="zip">Postcode:</label>
                <input type="text" id="zip" name="zip" autocomplete="postal-code">
            </div>
            <div>
                <label for="city">Stad:</label>
                <input type="text" id="city" name="city" autocomplete="address-level2">
            </div>
            <div>
                <label for="vat">BTW nummer:</label>
                <input type="text" id="vat" name="vat" pattern="NL[0-9]{9}B[0-9]{2}" title="Voer een geldig BTW nummer in, bijv. NL123456782B90" autocomplete="off">
                <small style="color:#999;">Bijv. NL123456782B90</small>
            </div>
            <div>
                <label for="peppol_endpoint">KvK nummer:</label>
                <input type="text" id="peppol_endpoint" name="peppol_endpoint" pattern="[0-9]{8}" title="Voer een geldig KvK nummer in" autocomplete="off">
                <small style="color:#999;">Bijv. 12345678</small>
            </div>
            <div>
                <label for="email">E-mail:</label>
                <input type="email" id="email" name="email" autocomplete="email">
            </div>
            <div>
                <label for="phone">Telefoon:</label>
                <input type="text" id="phone" name="phone" pattern="([+]31|0)[0-9]{9}" title="Voer een geldig telefoonnummer in, bijv. 0612345678 of +31612345678" autocomplete="tel">
                <small style="color:#999;">Bijv. 0612345678</small>
            </div>
            <div>
                <label for="iban">IBAN nummer:</label>
                <input type="text" id="iban" name="iban" pattern="[A-Z]{2}[0-9]{2}[A-Z]{4}[0-9]{10}" title="Voer een geldig IBAN in, bijv. NL91ABNA0417164300" autocomplete="off">
                <small style="color:#999;">Bijv. NL91ABNA0417164300</small>
            </div>
            <div>
                <label for="bank_ten_naamstelling">Tenaamstelling:</label>
                <input type="text" id="bank_ten_naamstelling" name="bank_ten_naamstelling" autocomplete="name">
            </div>
            <div>
                <label>
                    <input type="checkbox" name="x_studio_selfbilling_akkoord_1" value="1">
                    Ik ga akkoord met de voorwaarden
                </label>
            </div>
            <button type="submit">Verzenden</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.post("/onboarding")
async def onboarding_post(
    request: Request,
    name: str = Form(...),
    street: str = Form(None),
    zip: str = Form(None),
    city: str = Form(None),
    vat: str = Form(None),
    peppol_endpoint: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    iban: str = Form(None),
    bank_ten_naamstelling: str = Form(None)
):
    """Verwerk onboarding formulier"""
    partner = get_partner_from_session(request)
    partner_id = partner["id"]
    
    try:
        client = get_odoo_client()
        
        # Prepare values dict - only include fields that are not None
        values = {
            "name": name,
        }
        
        if street:
            values["street"] = street
        if zip:
            values["zip"] = zip
        if city:
            values["city"] = city
        if vat:
            values["vat"] = vat
        if peppol_endpoint:
            values["peppol_endpoint"] = peppol_endpoint
        if email:
            values["email"] = email
        if phone:
            values["phone"] = phone
        
        # Write to res.partner
        client.execute_kw(
            "res.partner",
            "write",
            [partner_id],
            values
        )
        
        # Force recompute by writing name again
        client.execute_kw(
            "res.partner",
            "write", 
            [partner_id],
            {"name": values.get("name") or partner["name"]}
        )
        
        # Create or update res.partner.bank record if IBAN is provided
        if iban:
            # Check if bank account already exists
            existing_banks = client.execute_kw(
                "res.partner.bank",
                "search_read",
                [["partner_id", "=", partner_id]],
                {"fields": ["id"], "limit": 1}
            )
            
            bank_values = {
                "partner_id": partner_id,
                "acc_number": iban,
            }
            if bank_ten_naamstelling:
                bank_values["acc_holder_name"] = bank_ten_naamstelling
            
            if existing_banks and len(existing_banks) > 0:
                # Update existing bank account
                client.execute_kw(
                    "res.partner.bank",
                    "write",
                    [existing_banks[0]["id"]],
                    bank_values
                )
            else:
                # Create new bank account
                client.execute_kw(
                    "res.partner.bank",
                    "create",
                    [bank_values]
                )
        
        # Update session
        partner["selfbilling_compleet"] = True
        request.session["partner"] = partner
        
        return RedirectResponse(url="/dashboard", status_code=303)
        
    except Exception as e:
        _LOG.error(f"Onboarding fout: {e}")
        raise HTTPException(status_code=500, detail=f"Fout bij opslaan van gegevens: {str(e)}")

@router.get("/logout")
async def logout(request: Request):
    """Logout"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root route - redirect naar login of dashboard"""
    if request.session.get("partner"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard met beschikbare inkooporders"""
    partner = get_partner_from_session(request)
    
    try:
        client = get_odoo_client()
        
        # Haal sale orders op
        pos = client.execute_kw(
            "sale.order",
            "search_read",
            ["|",
             ["x_studio_selection_field_67u_1jj77rtf7", "=", "beschikbaar"],
             "&",
             ["x_studio_selection_field_67u_1jj77rtf7", "=", "transfer"],
             ["x_studio_contractor", "!=", partner["id"]]
            ],
            {
                "fields": ["id", "name", "date_order", "x_studio_inkoop_partner_incl_btw", "state", 
                           "commitment_date", "x_studio_plaats", "x_studio_aantal_personen", 
                           "x_studio_aantal_kinderen", "tax_totals"],
                "order": "id desc",
                "limit": 50
            }
        )
        
        # Haal geclaimte orders op voor deze partner
        claimed = client.execute_kw(
            "sale.order",
            "search_read",
            ["&",
             ["x_studio_contractor", "=", partner["id"]],
             "|",
             ["x_studio_selection_field_67u_1jj77rtf7", "=", "claimed"],
             ["x_studio_selection_field_67u_1jj77rtf7", "=", "transfer"]
            ],
            {
                "fields": ["id", "name", "date_order", "x_studio_inkoop_partner_incl_btw", "state",
                           "commitment_date", "x_studio_plaats", "x_studio_aantal_personen",
                           "x_studio_aantal_kinderen", "x_studio_selection_field_67u_1jj77rtf7"],
                "order": "id desc",
                "limit": 50
            }
        )
        
        # Bepaal button kleur op basis van selfbilling_compleet
        selfbilling = partner.get('selfbilling_compleet', False)
        button_color = '#27ae60' if selfbilling else '#e67e22'
        mijn_gegevens_button = f'<a href="/onboarding" style="background:{button_color};color:white;padding:10px 20px;border-radius:8px;text-decoration:none;margin-left:20px;">Mijn gegevens</a>'
        
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
        <body data-selfbilling-compleet="{partner.get('selfbilling_compleet', False)}">
            <div class="container">
                <div class="header">
                    <h1>Beschikbare Inkooporders</h1>
                    {mijn_gegevens_button}
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
                po_amount = po.get('x_studio_inkoop_partner_incl_btw', 0)
                po_state = po.get('state', 'N/A')
                po_commitment_date = po.get('commitment_date', 'N/A') if po.get('commitment_date') else 'N/A'
                po_plaats = po.get('x_studio_plaats', 'N/A')
                po_personen = po.get('x_studio_aantal_personen', 'N/A')
                po_kinderen = po.get('x_studio_aantal_kinderen', 'N/A')
                
                html_content += f"""
                    <div class="po-card">
                        <div class="po-name">{po_name}</div>
                        <div class="po-detail">Datum: {po_date}</div>
                        <div class="po-detail">Status: {po_state}</div>
                        <div class="po-detail">Leverdatum: {po_commitment_date}</div>
                        <div class="po-detail">Locatie: {po_plaats}</div>
                        <div class="po-detail">Aantal personen: {po_personen}</div>
                        <div class="po-detail">Aantal kinderen: {po_kinderen}</div>
                        <div class="po-amount">€ {po_amount:,.2f}</div>
                        <button class="claim-btn" onclick="claimPO({po_id}, '{po_name}')">
                            Claim Inkooporder
                        </button>
                    </div>
                """
        
        html_content += """
                </div>
                
                <div style="margin-top: 40px;">
                    <h2 style="color: #333; font-size: 20px; margin-bottom: 20px;">Mijn Opdrachten</h2>
                    <div class="po-grid">
        """
        
        if not claimed:
            html_content += """
                        <div class="empty-state" style="grid-column: 1 / -1;">
                            <h2>Geen opdrachten</h2>
                            <p>U heeft momenteel geen geclaimde opdrachten.</p>
                        </div>
            """
        else:
            for po in claimed:
                po_id = po.get('id')
                po_name = po.get('name', 'N/A')
                po_date = po.get('date_order', '')[:10] if po.get('date_order') else 'N/A'
                po_amount = po.get('x_studio_inkoop_partner_incl_btw', 0)
                po_state = po.get('state', 'N/A')
                po_commitment_date = po.get('commitment_date', 'N/A') if po.get('commitment_date') else 'N/A'
                po_plaats = po.get('x_studio_plaats', 'N/A')
                po_personen = po.get('x_studio_aantal_personen', 'N/A')
                po_kinderen = po.get('x_studio_aantal_kinderen', 'N/A')
                po_selection_status = po.get('x_studio_selection_field_67u_1jj77rtf7', 'N/A')
                
                # Button based on status
                if po_selection_status == "claimed":
                    button_html = f'<button class="claim-btn" onclick="releaseOrder({po_id}, \'{po_name}\')" style="background: #e74c3c;">Zoek Vervanger</button>'
                elif po_selection_status == "transfer":
                    button_html = '<button class="claim-btn" disabled style="background: #3498db;">Beschikbaar voor transfer</button>'
                else:
                    button_html = f'<button class="claim-btn" onclick="releaseOrder({po_id}, \'{po_name}\')" style="background: #e74c3c;">Zoek Vervanger</button>'
                
                html_content += f"""
                        <div class="po-card">
                            <div class="po-name">{po_name}</div>
                            <div class="po-detail">Datum: {po_date}</div>
                            <div class="po-detail">Status: {po_state}</div>
                            <div class="po-detail">Leverdatum: {po_commitment_date}</div>
                            <div class="po-detail">Locatie: {po_plaats}</div>
                            <div class="po-detail">Aantal personen: {po_personen}</div>
                            <div class="po-detail">Aantal kinderen: {po_kinderen}</div>
                            <div class="po-amount">€ {po_amount:,.2f}</div>
                            {button_html}
                        </div>
                """
        
        html_content += """
                    </div>
                </div>
            </div>
            
            <script>
                async function claimPO(poId, poName) {
                    // Check selfbilling_compleet status
                    const selfbillingCompleet = document.body.getAttribute('data-selfbilling-compleet') === 'True';
                    if (!selfbillingCompleet) {
                        const message = 'Vul eerst je gegevens in om orders te kunnen claimen.';
                        const confirmed = confirm(message + '\\n\\nWil je naar de onboarding pagina gaan?');
                        if (confirmed) {
                            window.location.href = '/onboarding';
                        }
                        return;
                    }
                    
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
                
                async function releaseOrder(poId, poName) {
                    const btn = event.target;
                    btn.disabled = true;
                    btn.textContent = 'Bezig met vrijgeven...';
                    
                    try {
                        const response = await fetch(`/api/release-po/${poId}`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            }
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok && result.success) {
                            showMessage(`Succesvol! Order ${poName} is vrijgegeven voor vervanger.`, 'success');
                            btn.textContent = 'Beschikbaar voor transfer';
                            btn.style.background = '#3498db';
                        } else {
                            showMessage(result.error || 'Fout bij vrijgeven van order.', 'error');
                            btn.disabled = false;
                            btn.textContent = 'Zoek Vervanger';
                        }
                    } catch (error) {
                        showMessage('Er is een fout opgetreden. Probeer het opnieuw.', 'error');
                        btn.disabled = false;
                        btn.textContent = 'Zoek Vervanger';
                    }
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
    """Claim een sale order: zet x_studio_contractor naar partner_id en status naar 'claimed'"""
    partner = get_partner_from_session(request)
    partner_id = partner["id"]
    
    # Debug logging
    _LOG.info(f"[DEBUG claim_po] partner_id value: {partner_id}, type: {type(partner_id)}")
    
    try:
        client = get_odoo_client()
        
        # Read current partner_invoice_id before write
        current = client.execute_kw(
            "sale.order", "read", [po_id],
            {"fields": ["partner_invoice_id"]}
        )
        original_invoice_id = current[0]["partner_invoice_id"][0] if current and current[0].get("partner_invoice_id") else None
        
        # Update de sale order
        result = client.execute_kw(
            "sale.order",
            "write",
            [po_id],
            {
                "x_studio_contractor": partner_id,
                "x_studio_selection_field_67u_1jj77rtf7": "claimed"
            }
        )
        
        # Restore partner_invoice_id if it was set
        if original_invoice_id:
            client.execute_kw(
                "sale.order", "write", [po_id],
                {"partner_invoice_id": original_invoice_id}
            )
        
        # Debug logging
        _LOG.info(f"[DEBUG claim_po] write result: {result}, type: {type(result)}")
        
        if not result:
            return {"success": False, "error": "Update mislukt"}
        
        return {"success": True}
    
    except Exception as e:
        _LOG.error(f"Claim PO fout: {e}")
        return {"success": False, "error": f"Fout bij claimen van order: {str(e)}"}

@router.post("/api/release-po/{po_id}")
async def release_po(request: Request, po_id: int):
    partner = get_partner_from_session(request)
    try:
        client = get_odoo_client()
        _LOG.info(f"[DEBUG release] po_id: {po_id}, writing transfer status")
        result = client.execute_kw(
            "sale.order",
            "write",
            [po_id],
            {"x_studio_selection_field_67u_1jj77rtf7": "transfer"}
        )
        _LOG.info(f"[DEBUG release] result: {result}")
        if not result:
            return {"success": False, "error": "Update mislukt"}
        return {"success": True}
    except Exception as e:
        _LOG.error(f"Release PO fout: {e}")
        return {"success": False, "error": str(e)}

@router.get("/partner-orders", response_class=HTMLResponse)
async def partner_orders(request: Request):
    """Partner view: toon relevante sale.order records"""
    partner = get_partner_from_session(request)
    
    try:
        client = get_odoo_client()
        
        # Domain filter: (x_studio_selection_field_67u_1jj77rtf7 = "beschikbaar" AND x_studio_contractor = 1361) 
        # OR (x_studio_selection_field_67u_1jj77rtf7 = "transfer")
        domain = [
            '|',
            '&',
            ('x_studio_selection_field_67u_1jj77rtf7', '=', 'beschikbaar'),
            ('x_studio_contractor', '=', 1361),
            ('x_studio_selection_field_67u_1jj77rtf7', '=', 'transfer')
        ]
        
        # Debug: print domain en modelnaam
        print(f"[DEBUG partner-orders] Model: sale.order")
        print(f"[DEBUG partner-orders] Domain: {domain}")
        
        # Haal sale.order records op
        orders = client.execute_kw(
            "sale.order",
            "search_read",
            [domain],
            {
                "fields": [
                    "id",
                    "name",
                    "state",
                    "type_name",
                    "partner_id",
                    "commitment_date",
                    "x_studio_contractor",
                    "x_studio_plaats",
                    "x_studio_aantal_personen",
                    "x_studio_selection_field_67u_1jj77rtf7"
                ],
                "order": "id desc",
                "limit": 100
            }
        )
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Portaal - Partner Orders</title>
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
                    max-width: 1400px;
                    margin: 0 auto;
                }}
                table {{
                    width: 100%;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    border-collapse: collapse;
                    overflow: hidden;
                }}
                thead {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                th {{
                    padding: 16px;
                    text-align: left;
                    font-weight: 600;
                    font-size: 14px;
                }}
                td {{
                    padding: 14px 16px;
                    border-bottom: 1px solid #e0e0e0;
                    font-size: 14px;
                    color: #333;
                }}
                tbody tr:hover {{
                    background: #f8f9fa;
                }}
                tbody tr:last-child td {{
                    border-bottom: none;
                }}
                .type-badge {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                .type-offerte {{
                    background: #fff3cd;
                    color: #856404;
                }}
                .type-verkooporder {{
                    background: #d4edda;
                    color: #155724;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 60px 20px;
                    color: #666;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
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
                    <h1>Partner Orders</h1>
                    <div class="user-info">
                        <span class="user-name">Ingelogd als: {partner['name']}</span>
                        <a href="/logout" class="logout-btn">Uitloggen</a>
                    </div>
                </div>
        """
        
        if not orders:
            html_content += """
                <div class="empty-state">
                    <h2>Geen orders gevonden</h2>
                    <p>Er zijn momenteel geen relevante sale orders beschikbaar.</p>
                </div>
            """
        else:
            html_content += """
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Ordernummer</th>
                            <th>Type</th>
                            <th>Status</th>
                            <th>Klant</th>
                            <th>Leverdatum</th>
                            <th>Contractor</th>
                            <th>Plaats</th>
                            <th>Aantal personen</th>
                            <th>Selection Status</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for order in orders:
                order_id = order.get('id', 'N/A')
                order_name = order.get('name', 'N/A')
                order_state = order.get('state', 'N/A')
                type_name = order.get('type_name', 'N/A')
                partner_id = order.get('partner_id')
                partner_name = partner_id[1] if partner_id and isinstance(partner_id, (list, tuple)) and len(partner_id) > 1 else (partner_id if partner_id else 'N/A')
                commitment_date = order.get('commitment_date', '')[:10] if order.get('commitment_date') else 'N/A'
                contractor = order.get('x_studio_contractor')
                contractor_name = contractor[1] if contractor and isinstance(contractor, (list, tuple)) and len(contractor) > 1 else (contractor if contractor else 'N/A')
                plaats = order.get('x_studio_plaats', 'N/A')
                aantal_personen = order.get('x_studio_aantal_personen', 'N/A')
                selection_status = order.get('x_studio_selection_field_67u_1jj77rtf7', 'N/A')
                
                # Determine type badge class
                type_class = 'type-offerte' if order_state == 'sent' else 'type-verkooporder'
                
                html_content += f"""
                        <tr>
                            <td>{order_id}</td>
                            <td>{order_name}</td>
                            <td><span class="type-badge {type_class}">{type_name}</span></td>
                            <td>{order_state}</td>
                            <td>{partner_name}</td>
                            <td>{commitment_date}</td>
                            <td>{contractor_name}</td>
                            <td>{plaats}</td>
                            <td>{aantal_personen}</td>
                            <td>{selection_status}</td>
                        </tr>
                """
            
            html_content += """
                    </tbody>
                </table>
            """
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        _LOG.error(f"Partner orders fout: {e}")
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen van partner orders: {str(e)}")

@router.get("/test-odoo-verbinding")
async def test_odoo_verbinding_endpoint():
    """Test Odoo verbinding endpoint"""
    try:
        from app.config import get_odoo_base_url, get_odoo_db, get_odoo_login, get_odoo_api_key, validate_odoo_config
        from app.odoo_client import get_odoo_client
        
        # DEBUG: Toon configuratie in endpoint
        odoo_base_url = get_odoo_base_url()
        odoo_db = get_odoo_db()
        odoo_login = get_odoo_login()
        odoo_api_key = get_odoo_api_key()
        print(f"[DEBUG test-odoo-verbinding] ===== START DEBUG OUTPUT =====")
        print(f"[DEBUG test-odoo-verbinding] Ruwe ODOO_BASE_URL uit config: {odoo_base_url}")
        print(f"[DEBUG test-odoo-verbinding] ODOO_DB: {odoo_db}")
        print(f"[DEBUG test-odoo-verbinding] ODOO_LOGIN: {odoo_login}")
        print(f"[DEBUG test-odoo-verbinding] ODOO_API_KEY aanwezig: {bool(odoo_api_key)}")
        
        # Valideer configuratie
        is_valid, missing = validate_odoo_config()
        if not is_valid:
            print(f"[DEBUG test-odoo-verbinding] Validatie FAILED - ontbrekend: {missing}")
            return {
                "status": "FAIL",
                "error": "Ontbrekende omgevingsvariabelen",
                "missing": missing
            }
        
        print(f"[DEBUG test-odoo-verbinding] Validatie PASSED - initialiseren OdooClient...")
        
        # Test verbinding
        client = get_odoo_client()
        
        print(f"[DEBUG test-odoo-verbinding] OdooClient geïnitialiseerd")
        print(f"[DEBUG test-odoo-verbinding] Client URL: {client.url}")
        print(f"[DEBUG test-odoo-verbinding] Client DB: {client.db}")
        
        # Test query
        user_info = client.execute_kw(
            'res.users',
            'read',
            [client.uid],
            {'fields': ['name', 'login']}
        )
        
        print(f"[DEBUG test-odoo-verbinding] ===== SUCCESS =====")
        return {
            "status": "SUCCESS",
            "message": "Odoo verbinding werkt correct",
            "config": {
                "base_url": odoo_base_url,
                "database": odoo_db,
                "login": odoo_login,
                "api_key_set": bool(odoo_api_key)
            },
            "user": {
                "id": client.uid,
                "name": user_info[0].get('name') if user_info else None,
                "login": user_info[0].get('login') if user_info else None
            }
        }
    except Exception as e:
        print(f"[DEBUG test-odoo-verbinding] ===== ERROR =====")
        print(f"[DEBUG test-odoo-verbinding] Error type: {type(e).__name__}")
        print(f"[DEBUG test-odoo-verbinding] Error message: {str(e)}")
        _LOG.error(f"Test Odoo verbinding fout: {e}")
        return {
            "status": "FAIL",
            "error": str(e),
            "type": type(e).__name__
        }
