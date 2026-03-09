from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.odoo_client import get_odoo_client
from app.auth import get_partner_auth
import logging
from datetime import datetime, date, date

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
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Montserrat', sans-serif;
                background: #fffdf2;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .logo {
                font-size: 24px;
                font-weight: 900;
                color: #333333;
                text-align: center;
                margin-bottom: 30px;
            }
            .login-container {
                background: white;
                border-radius: 12px;
                padding: 40px;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333333;
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
                color: #333333;
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
                border-color: #e2af13;
            }
            button {
                width: 100%;
                padding: 14px;
                background: #fec82a;
                color: #333333;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
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
            <div class="logo">FRIETTRUCKHUREN.NL</div>
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
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Montserrat', sans-serif;
                background: #fffdf2;
                min-height: 100vh;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: flex-start;
            }
            .logo {
                font-size: 24px;
                font-weight: 900;
                color: #333333;
                text-align: center;
                margin-bottom: 20px;
            }
            .form-container {
                background: white;
                max-width: 600px;
                width: 100%;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333333;
                margin-bottom: 20px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                color: #333333;
                font-weight: 500;
                font-size: 14px;
            }
            input[type="text"],
            input[type="email"] {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input[type="text"]:focus,
            input[type="email"]:focus {
                outline: none;
                border-color: #e2af13;
            }
            small {
                display: block;
                color: #999;
                font-size: 12px;
                margin-top: 4px;
            }
            button {
                width: 100%;
                padding: 14px;
                background: #fec82a;
                color: #333333;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="form-container">
            <div class="logo">FRIETTRUCKHUREN.NL</div>
            <h1>Onboarding</h1>
            <p>Vul uw gegevens in om verder te gaan.</p>
            <form method="post" action="/onboarding">
                <div class="form-group">
                    <label for="name">Bedrijfsnaam:</label>
                    <input type="text" id="name" name="name" autocomplete="organization" required>
                </div>
                <div class="form-group">
                    <label for="street">Straat:</label>
                    <input type="text" id="street" name="street" autocomplete="street-address">
                </div>
                <div class="form-group">
                    <label for="zip">Postcode:</label>
                    <input type="text" id="zip" name="zip" autocomplete="postal-code">
                </div>
                <div class="form-group">
                    <label for="city">Stad:</label>
                    <input type="text" id="city" name="city" autocomplete="address-level2">
                </div>
                <div class="form-group">
                    <label for="vat">BTW nummer:</label>
                    <input type="text" id="vat" name="vat" pattern="NL[0-9]{9}B[0-9]{2}" title="Voer een geldig BTW nummer in, bijv. NL123456782B90" autocomplete="off">
                    <small>Bijv. NL123456782B90</small>
                </div>
                <div class="form-group">
                    <label for="peppol_endpoint">KvK nummer:</label>
                    <input type="text" id="peppol_endpoint" name="peppol_endpoint" pattern="[0-9]{8}" title="Voer een geldig KvK nummer in" autocomplete="off">
                    <small>Bijv. 12345678</small>
                </div>
                <div class="form-group">
                    <label for="email">E-mail:</label>
                    <input type="email" id="email" name="email" autocomplete="email">
                </div>
                <div class="form-group">
                    <label for="phone">Telefoon:</label>
                    <input type="text" id="phone" name="phone" pattern="([+]31|0)[0-9]{9}" title="Voer een geldig telefoonnummer in, bijv. 0612345678 of +31612345678" autocomplete="tel">
                    <small>Bijv. 0612345678</small>
                </div>
                <div class="form-group">
                    <label for="iban">IBAN nummer:</label>
                    <input type="text" id="iban" name="iban" pattern="[A-Z]{2}[0-9]{2}[A-Z]{4}[0-9]{10}" title="Voer een geldig IBAN in, bijv. NL91ABNA0417164300" autocomplete="off">
                    <small>Bijv. NL91ABNA0417164300</small>
                </div>
                <div class="form-group">
                    <label for="bank_ten_naamstelling">Tenaamstelling:</label>
                    <input type="text" id="bank_ten_naamstelling" name="bank_ten_naamstelling" autocomplete="name">
                </div>
                <input type="hidden" name="step" value="1">
                <button type="submit">Verder →</button>
            </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.post("/onboarding")
async def onboarding_post(
    request: Request,
    step: str = Form(...),
    name: str = Form(None),
    street: str = Form(None),
    zip: str = Form(None),
    city: str = Form(None),
    vat: str = Form(None),
    peppol_endpoint: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    iban: str = Form(None),
    bank_ten_naamstelling: str = Form(None),
    contract_agreed: str = Form(None)
):
    """Verwerk onboarding formulier - 2-staps proces"""
    partner = get_partner_from_session(request)
    partner_id = partner["id"]
    
    if step == "1":
        # Step 1: Store form data in session and show contract
        request.session["onboarding_data"] = {
            "name": name,
            "street": street,
            "zip": zip,
            "city": city,
            "vat": vat,
            "peppol_endpoint": peppol_endpoint,
            "email": email,
            "phone": phone,
            "iban": iban,
            "bank_ten_naamstelling": bank_ten_naamstelling
        }
        
        # Show contract page
        onboarding_data = request.session["onboarding_data"]
        today = datetime.now().strftime("%d-%m-%Y")
        
        # Build partner address string
        partner_address_parts = []
        if onboarding_data.get("name"):
            partner_address_parts.append(onboarding_data["name"])
        if onboarding_data.get("street"):
            partner_address_parts.append(onboarding_data["street"])
        if onboarding_data.get("zip") and onboarding_data.get("city"):
            partner_address_parts.append(f"{onboarding_data['zip']} {onboarding_data['city']}")
        elif onboarding_data.get("zip"):
            partner_address_parts.append(onboarding_data["zip"])
        elif onboarding_data.get("city"):
            partner_address_parts.append(onboarding_data["city"])
        partner_address = "<br>".join(partner_address_parts) if partner_address_parts else "N/A"
        
        partner_kvk = onboarding_data.get("peppol_endpoint", "")
        partner_vat = onboarding_data.get("vat", "")
        
        partner_name = onboarding_data.get('name', 'N/A')
        partner_street = onboarding_data.get('street', '')
        partner_zip = onboarding_data.get('zip', '')
        partner_city = onboarding_data.get('city', '')
        partner_vat = onboarding_data.get('vat', '')
        partner_kvk = onboarding_data.get('peppol_endpoint', '')
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Portaal - Contract</title>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Montserrat', sans-serif;
                    background: #fffdf2;
                    padding: 20px;
                    max-width: 600px;
                    margin: 0 auto;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: 900;
                    color: #333333;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .contract-container {{
                    background: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{ 
                    color: #333333;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .checkbox-section {{ 
                    margin: 30px 0; 
                    padding: 20px; 
                    background: #f5f5f5; 
                    border-radius: 8px; 
                }}
                button {{ 
                    width: 100%;
                    padding: 14px; 
                    background: #fec82a; 
                    color: #333333; 
                    border: none; 
                    border-radius: 8px; 
                    font-size: 16px; 
                    font-weight: 700;
                    cursor: pointer; 
                }}
            </style>
        </head>
        <body>
            <div class="logo">FRIETTRUCKHUREN.NL</div>
            <div class="contract-container">
                <h1>Samenwerkingsovereenkomst Friettruckhuren.nl</h1>
            
            <div style="height:300px; overflow-y:scroll; border:1px solid #ccc; padding:15px; background:#f9f9f9; font-size:13px; line-height:1.6;">
                <p><strong>Datum:</strong> {today}</p>
                
                <p><strong>Partijen:</strong></p>
                <p>Friettruckhuren.nl, handelsnaam van Treatlab VOF, gevestigd te Thomas Edisonstraat 14, 3284WD Zuid-Beijerland, KvK 77075382, vertegenwoordigd door Robby Grob</p>
                
                <p><strong>en</strong></p>
                
                <p>{partner_name}, gevestigd te {partner_street}, {partner_zip} {partner_city}, KvK {partner_kvk}, BTW {partner_vat}, hierna te noemen: Partner.</p>
                
                <h3>Artikel 1 - Samenwerking</h3>
                <p>• Friettruckhuren.nl exploiteert een platform waarop opdrachten voor frietcatering worden aangeboden.<br>
                • Partner kan via het partnerportaal opdrachten claimen.<br>
                • Partner voert geclaimde opdrachten zelfstandig uit en blijft verantwoordelijk voor de uitvoering.<br>
                • Friettruckhuren.nl verzorgt verkoop, marketing, communicatie met klanten en administratieve afhandeling.</p>
                
                <h3>Artikel 2 - Vergoeding</h3>
                <p>• Partner ontvangt een vergoeding per uitgevoerde opdracht zoals vermeld in het partnerportaal.<br>
                • De vergoeding wordt bepaald op basis van de opdrachtgegevens en is exclusief BTW.<br>
                • Friettruckhuren.nl behoudt zich het recht voor om vergoedingen aan te passen met voorafgaande kennisgeving.</p>
                
                <h3>Artikel 3 - Betaling</h3>
                <p>• Betalingen vinden plaats volgens de betaalcondities zoals vermeld in het partnerportaal.<br>
                • Voor zakelijke opdrachten geldt de betaaltermijn zoals overeengekomen in de opdracht.<br>
                • Partner dient een geldig IBAN-rekeningnummer te verstrekken voor betalingen.</p>
                
                <h3>Artikel 4 - Self-billing</h3>
                <p>• Friettruckhuren.nl verzorgt self-billing voor alle opdrachten.<br>
                • Partner ontvangt automatisch gegenereerde facturen via het partnerportaal.<br>
                • Partner dient alle benodigde gegevens correct en volledig aan te leveren voor self-billing.</p>
                
                <h3>Artikel 5 - No-show</h3>
                <p>• Bij no-show of niet-naleving van de opdracht kan Friettruckhuren.nl een boete opleggen.<br>
                • De hoogte van de boete wordt bepaald op basis van de schade die is geleden.<br>
                • Partner is verantwoordelijk voor tijdige communicatie bij wijzigingen of annuleringen.</p>
                
                <h3>Artikel 6 - Algemene voorwaarden</h3>
                <p>• Op deze overeenkomst zijn de Algemene Partnervoorwaarden van Friettruckhuren.nl van toepassing.<br>
                • Deze voorwaarden zijn opgenomen in de bijlage en maken integraal deel uit van deze overeenkomst.</p>
                
                <h3>Algemene Partnervoorwaarden</h3>
                
                <h4>Artikel 1 - Definities</h4>
                <p>In deze voorwaarden wordt verstaan onder: Platform: het digitale platform van Friettruckhuren.nl; Partner: de partij die via het platform opdrachten uitvoert; Opdracht: een concrete frietcatering opdracht zoals aangeboden via het platform.</p>
                
                <h4>Artikel 2 - Toepasselijkheid</h4>
                <p>Deze voorwaarden zijn van toepassing op alle overeenkomsten tussen Friettruckhuren.nl en Partner, tenzij schriftelijk anders overeengekomen.</p>
                
                <h4>Artikel 3 - Aanmelding en account</h4>
                <p>Partner dient zich aan te melden via het partnerportaal en een account aan te maken. Partner is verantwoordelijk voor de juistheid van de verstrekte gegevens en de vertrouwelijkheid van inloggegevens.</p>
                
                <h4>Artikel 4 - Claimen van opdrachten</h4>
                <p>Partner kan opdrachten claimen via het partnerportaal. Een geclaimde opdracht is bindend en dient te worden uitgevoerd volgens de opdrachtspecificaties.</p>
                
                <h4>Artikel 5 - Uitvoering opdrachten</h4>
                <p>Partner voert opdrachten zelfstandig uit en is verantwoordelijk voor de kwaliteit, veiligheid en tijdige uitvoering. Partner dient te beschikken over de benodigde vergunningen en verzekeringen.</p>
                
                <h4>Artikel 6 - Kwaliteitseisen</h4>
                <p>Partner dient te voldoen aan alle geldende kwaliteitseisen en hygiënenormen. Friettruckhuren.nl behoudt zich het recht voor om kwaliteitscontroles uit te voeren.</p>
                
                <h4>Artikel 7 - Verzekeringen</h4>
                <p>Partner dient te beschikken over een geldige aansprakelijkheidsverzekering en andere benodigde verzekeringen voor de uitvoering van opdrachten.</p>
                
                <h4>Artikel 8 - Geheimhouding</h4>
                <p>Partner verplicht zich tot geheimhouding van alle vertrouwelijke informatie die hij in het kader van de samenwerking verwerft.</p>
                
                <h4>Artikel 9 - Intellectueel eigendom</h4>
                <p>Alle intellectuele eigendomsrechten op het platform en de daarbij behorende materialen blijven eigendom van Friettruckhuren.nl.</p>
                
                <h4>Artikel 10 - Aansprakelijkheid</h4>
                <p>Friettruckhuren.nl is niet aansprakelijk voor schade die Partner lijdt in verband met de uitvoering van opdrachten, tenzij sprake is van opzet of bewuste roekeloosheid.</p>
                
                <h4>Artikel 11 - Schadevergoeding</h4>
                <p>Partner is aansprakelijk voor alle schade die voortvloeit uit de uitvoering van opdrachten en dient deze te vergoeden aan Friettruckhuren.nl of derden.</p>
                
                <h4>Artikel 12 - Opzegging</h4>
                <p>Beide partijen kunnen deze overeenkomst opzeggen met een opzegtermijn van 30 dagen, tenzij anders overeengekomen.</p>
                
                <h4>Artikel 13 - Wijzigingen</h4>
                <p>Wijzigingen in deze voorwaarden worden schriftelijk medegedeeld en treden in werking 30 dagen na kennisgeving, tenzij Partner bezwaar maakt.</p>
                
                <h4>Artikel 14 - Geschillen</h4>
                <p>Geschillen worden in eerste instantie opgelost door middel van overleg. Indien dit niet tot een oplossing leidt, worden geschillen voorgelegd aan de bevoegde rechter.</p>
                
                <h4>Artikel 15 - Toepasselijk recht</h4>
                <p>Op deze overeenkomst is Nederlands recht van toepassing.</p>
                
                <h4>Artikel 16 - Overige bepalingen</h4>
                <p>Indien een bepaling van deze voorwaarden nietig of vernietigbaar blijkt, blijven de overige bepalingen van kracht.</p>
            </div>
            
                <p style="font-size:12px;color:#666;">Scroll omhoog om de volledige overeenkomst te lezen.</p>
                
                <form method="post" action="/onboarding">
                    <input type="hidden" name="step" value="2">
                    <div class="checkbox-section">
                        <label>
                            <input type="checkbox" name="contract_agreed" value="1" required>
                            Ik ga akkoord met de samenwerkingsovereenkomst en algemene voorwaarden
                        </label>
                    </div>
                    <button type="submit">Bevestigen</button>
                </form>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    
    elif step == "2":
        # Step 2: Save to Odoo and redirect
        if not contract_agreed:
            raise HTTPException(status_code=400, detail="U moet akkoord gaan met de voorwaarden")
        
        onboarding_data = request.session.get("onboarding_data")
        if not onboarding_data:
            raise HTTPException(status_code=400, detail="Geen onboarding data gevonden")
        
        try:
            client = get_odoo_client()
            
            # Prepare values dict
            values = {
                "name": onboarding_data.get("name"),
            }
            
            if onboarding_data.get("street"):
                values["street"] = onboarding_data["street"]
            if onboarding_data.get("zip"):
                values["zip"] = onboarding_data["zip"]
            if onboarding_data.get("city"):
                values["city"] = onboarding_data["city"]
            if onboarding_data.get("vat"):
                values["vat"] = onboarding_data["vat"]
            if onboarding_data.get("peppol_endpoint"):
                values["peppol_endpoint"] = onboarding_data["peppol_endpoint"]
            if onboarding_data.get("email"):
                values["email"] = onboarding_data["email"]
            if onboarding_data.get("phone"):
                values["phone"] = onboarding_data["phone"]
            
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
            if onboarding_data.get("iban"):
                existing_banks = client.execute_kw(
                    "res.partner.bank",
                    "search_read",
                    [["partner_id", "=", partner_id]],
                    {"fields": ["id"], "limit": 1}
                )
                
                bank_values = {
                    "partner_id": partner_id,
                    "acc_number": onboarding_data["iban"],
                }
                if onboarding_data.get("bank_ten_naamstelling"):
                    bank_values["acc_holder_name"] = onboarding_data["bank_ten_naamstelling"]
                
                if existing_banks and len(existing_banks) > 0:
                    client.execute_kw(
                        "res.partner.bank",
                        "write",
                        [existing_banks[0]["id"]],
                        bank_values
                    )
                else:
                    client.execute_kw(
                        "res.partner.bank",
                        "create",
                        [bank_values]
                    )
            
            # Clear onboarding data from session
            if "onboarding_data" in request.session:
                del request.session["onboarding_data"]
            
            # Update session
            partner["selfbilling_compleet"] = True
            request.session["partner"] = partner
            
            return RedirectResponse(url="/dashboard", status_code=303)
            
        except Exception as e:
            _LOG.error(f"Onboarding fout: {e}")
            raise HTTPException(status_code=500, detail=f"Fout bij opslaan van gegevens: {str(e)}")
    
    else:
        raise HTTPException(status_code=400, detail="Ongeldige stap")

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
                           "x_studio_aantal_kinderen", "tax_totals", "x_studio_ordertype", "payment_term_id", "order_line", "x_studio_selection_field_67u_1jj77rtf7"],
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
                           "x_studio_aantal_kinderen", "x_studio_selection_field_67u_1jj77rtf7", "x_studio_ordertype", "payment_term_id", "order_line"],
                "order": "id desc",
                "limit": 50
            }
        )
        
        # Collect all order_line IDs
        all_line_ids = []
        for po in pos + claimed:
            order_lines = po.get('order_line', [])
            if order_lines:
                all_line_ids.extend(order_lines)
        
        # Fetch order lines if IDs exist
        lines_by_order = {}
        if all_line_ids:
            lines = client.execute_kw(
                "sale.order.line",
                "read",
                all_line_ids,
                {"fields": ["order_id", "name"]}
            )
            
            # Build lookup dictionary
            for line in lines:
                order_id = line['order_id'][0] if isinstance(line['order_id'], (list, tuple)) else line['order_id']
                if order_id not in lines_by_order:
                    lines_by_order[order_id] = []
                lines_by_order[order_id].append(line['name'])
        
        # Filter orders: keep only those with commitment_date >= today or False/None
        today = date.today()
        pos_filtered = []
        for po in pos:
            commitment_date = po.get('commitment_date')
            if not commitment_date:
                pos_filtered.append(po)
            else:
                try:
                    # Parse date string (format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
                    po_date = datetime.strptime(commitment_date[:10], '%Y-%m-%d').date()
                    if po_date >= today:
                        pos_filtered.append(po)
                except:
                    # If parsing fails, keep the order
                    pos_filtered.append(po)
        
        claimed_filtered = []
        for po in claimed:
            commitment_date = po.get('commitment_date')
            if not commitment_date:
                claimed_filtered.append(po)
            else:
                try:
                    po_date = datetime.strptime(commitment_date[:10], '%Y-%m-%d').date()
                    if po_date >= today:
                        claimed_filtered.append(po)
                except:
                    claimed_filtered.append(po)
        
        # Update pos and claimed with filtered lists
        pos = pos_filtered
        claimed = claimed_filtered
        
        # Sort both lists by commitment_date ascending
        pos.sort(key=lambda x: x.get('commitment_date') or '9999')
        claimed.sort(key=lambda x: x.get('commitment_date') or '9999')
        
        # Helper function to format date as DD-MM
        def format_short_date(date_str):
            if not date_str or date_str == 'N/A':
                return 'N/A'
            try:
                date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
                return date_obj.strftime('%d-%m')
            except:
                return date_str[:10] if len(date_str) >= 10 else date_str
        
        # Bepaal button kleur op basis van selfbilling_compleet
        selfbilling = partner.get('selfbilling_compleet', False)
        button_color = '#27ae60' if selfbilling else '#e67e22'
        mijn_gegevens_button = f'<a href="/onboarding" style="background:{button_color};color:white;padding:10px 20px;border-radius:8px;text-decoration:none;margin-left:20px;">Mijn gegevens</a>'
        
        # Calculate stats (only claimed orders)
        count_offertes = sum(1 for po in claimed if po.get('state') == 'sent')
        count_orders = sum(1 for po in claimed if po.get('state') == 'sale')
        count_geclaimd = len(claimed)
        
        # Calculate amount totals
        total_offertes = sum(po.get('x_studio_inkoop_partner_incl_btw', 0) or 0 for po in claimed if po.get('state') == 'sent')
        total_orders = sum(po.get('x_studio_inkoop_partner_incl_btw', 0) or 0 for po in claimed if po.get('state') == 'sale')
        total_geclaimd = sum(po.get('x_studio_inkoop_partner_incl_btw', 0) or 0 for po in claimed)
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="nl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FTH Portaal - Dashboard</title>
            <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: 'Montserrat', sans-serif;
                    background: #fffdf2;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 16px;
                    padding-bottom: 70px;
                }}
                .stats-bar {{
                    display: flex;
                    gap: 12px;
                    margin-bottom: 16px;
                }}
                .stat {{
                    flex: 1;
                    background: white;
                    padding: 16px;
                    border-radius: 12px;
                    text-align: center;
                }}
                .stat-number {{
                    display: block;
                    font-size: 24px;
                    font-weight: 700;
                    color: #fec82a;
                    margin-bottom: 4px;
                }}
                .stat-label {{
                    display: block;
                    font-size: 12px;
                    color: #666;
                }}
                .stat-amount {{
                    display: block;
                    font-size: 12px;
                    color: #27ae60;
                    font-weight: 600;
                    margin-bottom: 4px;
                }}
                .legend {{
                    background: white;
                    padding: 8px 16px;
                    border-radius: 8px;
                    margin-bottom: 12px;
                    font-size: 13px;
                    color: #666;
                }}
                .po-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 12px 16px;
                    margin-bottom: 6px;
                    width: 100%;
                    box-sizing: border-box;
                    overflow: hidden;
                }}
                .po-card-row {{
                    display: flex;
                    align-items: center;
                    flex-wrap: wrap;
                    margin-bottom: 4px;
                    line-height: 1.4;
                }}
                .po-name {{
                    font-size: 14px;
                    font-weight: 600;
                    color: #333;
                    margin: 0;
                }}
                .po-detail {{
                    color: #666;
                    font-size: 13px;
                    margin: 0;
                    line-height: 1.4;
                }}
                @media (max-width: 380px) {{
                    .po-card {{
                        padding: 10px 12px;
                    }}
                    .po-detail {{
                        font-size: 12px;
                    }}
                    .claim-btn {{
                        padding: 6px 12px;
                        font-size: 11px;
                    }}
                }}
                .po-amount-row {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-top: 8px;
                }}
                .po-amount {{
                    font-size: 18px;
                    font-weight: 700;
                    color: #333333;
                    margin: 0;
                }}
                .claim-btn {{
                    width: auto;
                    padding: 8px 20px;
                    background: #fec82a;
                    color: #333333;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 700;
                    cursor: pointer;
                    margin: 0;
                }}
                .claim-btn:disabled {{
                    background: #ccc;
                    cursor: not-allowed;
                }}
                .success-message {{
                    background: #d4edda;
                    color: #155724;
                    padding: 12px;
                    border-radius: 8px;
                    margin-bottom: 16px;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 40px 20px;
                    color: #666;
                }}
                .section-header {{
                    font-size: 20px;
                    font-weight: 700;
                    color: #333;
                    margin: 24px 0 16px 0;
                }}
                .toggle-container {{
                    margin-bottom: 16px;
                }}
                .toggle-container label {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 14px;
                    color: #333;
                    cursor: pointer;
                }}
                .toggle-container input[type="checkbox"] {{
                    width: 18px;
                    height: 18px;
                    cursor: pointer;
                }}
            </style>
        </head>
        <body data-selfbilling-compleet="{partner.get('selfbilling_compleet', False)}">
            <div style="text-align:center; padding:8px 0 16px 0;">
                <span style="font-family:'Montserrat',sans-serif; font-weight:900; font-size:14px; color:#333333; letter-spacing:1px;">FRIETTRUCKHUREN.NL</span>
            </div>
            
            <div class="stats-bar">
                <div class="stat">
                    <span class="stat-number">{count_offertes}</span>
                    <span class="stat-amount">€ {total_offertes:,.0f}</span>
                    <span class="stat-label">Mijn offertes</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{count_orders}</span>
                    <span class="stat-amount">€ {total_orders:,.0f}</span>
                    <span class="stat-label">Mijn orders</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{count_geclaimd}</span>
                    <span class="stat-amount">€ {total_geclaimd:,.0f}</span>
                    <span class="stat-label">Mijn totaal</span>
                    </div>
                </div>
                
                <div id="message-container"></div>
                
            <div class="toggle-container">
                <label>
                    <input type="checkbox" id="splitToggle" checked onchange="toggleSplit()">
                    <strong>Beschikbaar/Geclaimd splitsen</strong>
                </label>
            </div>
            
            <div id="merged-section" style="display:none;">
                <div class="legend">
                    <span style="color:#e67e22;">●</span> Beschikbaar &nbsp;
                    <span style="color:#3498db;">●</span> Offerte &nbsp;
                    <span style="color:#27ae60;">●</span> Order
                </div>
                <div id="merged-cards">
        """
        
        # Render all cards in merged section (pos + claimed combined)
        all_orders_merged = pos + claimed
        if not all_orders_merged:
            html_content += """
                    <div class="empty-state">
                        <h2>Geen opdrachten</h2>
                        <p>Er zijn momenteel geen opdrachten beschikbaar.</p>
                    </div>
            """
        else:
            for po in all_orders_merged:
                po_id = po.get('id')
                po_name = po.get('name', 'N/A')
                po_date = po.get('date_order', '')[:10] if po.get('date_order') else 'N/A'
                po_amount = po.get('x_studio_inkoop_partner_incl_btw', 0)
                po_state = po.get('state', 'N/A')
                po_commitment_date = po.get('commitment_date', 'N/A') if po.get('commitment_date') else 'N/A'
                short_date = format_short_date(po_commitment_date)
                po_plaats = po.get('x_studio_plaats', 'N/A')
                po_personen = po.get('x_studio_aantal_personen', 'N/A')
                po_kinderen = po.get('x_studio_aantal_kinderen', 'N/A')
                po_ordertype = po.get('x_studio_ordertype', '')
                po_payment_term = po.get('payment_term_id', False)
                po_selection_status = po.get('x_studio_selection_field_67u_1jj77rtf7', 'N/A')
                
                # Status bullet
                if po_state == 'sent':
                    bullet_color = '#3498db'
                elif po_state == 'sale':
                    bullet_color = '#27ae60'
                else:
                    bullet_color = '#e67e22'
                
                # Ordertype badge
                ordertype_badge = ''
                if po_ordertype == 'b2b':
                    ordertype_badge = '<span style="background: #3498db; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">Zakelijk</span>'
                elif po_ordertype == 'b2c':
                    ordertype_badge = '<span style="background: #95a5a6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">Particulier</span>'
                
                # Status badge
                status_badge = ''
                if po_selection_status in ("beschikbaar", "nieuw"):
                    status_badge = '<span style="background:#e67e22;color:white;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;margin-left:6px;">Beschikbaar</span>'
                elif po_selection_status == "claimed":
                    status_badge = '<span style="background:#3498db;color:white;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;margin-left:6px;">Geclaimd</span>'
                elif po_selection_status == "transfer":
                    status_badge = '<span style="background:#e74c3c;color:white;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;margin-left:6px;">Transfer</span>'
                
                # Payment terms (only for b2b, exclude "Vooraf")
                payment_terms_html = ''
                if po_ordertype == 'b2b' and po_payment_term:
                    payment_term_name = po_payment_term[1] if isinstance(po_payment_term, (list, tuple)) else str(po_payment_term)
                    if 'Vooraf' not in payment_term_name:
                        payment_terms_html = f'<div class="po-card-row"><div class="po-detail">Betaalconditie: {payment_term_name}</div></div>'
                
                # Order line descriptions
                descriptions = lines_by_order.get(po.get('id'), [])
                desc_html = ''
                if descriptions:
                    desc_list = ' | '.join(descriptions)
                    desc_html = f'<div class="po-card-row"><div class="po-detail">📦 {desc_list}</div></div>'
                
                # Button logic - merged section: only show claim button, not release button
                is_claimed = any(c.get('id') == po_id for c in claimed)
                if is_claimed:
                    # In merged section, hide release buttons
                    button_html = ''
                else:
                    button_html = f'<button class="claim-btn" onclick="claimPO({po_id}, \'{po_name}\')" style="width:auto; padding:8px 20px; margin-left:auto;">Claim</button>'
                
                html_content += f"""
                    <div class="po-card">
                        <div class="po-card-row">
                            <span style="color:{bullet_color};font-size:16px;">●</span>
                            <span class="po-detail" style="margin-left:4px;">{short_date}</span>
                            <span title="{po_name}" style="cursor:help; border-bottom:1px dotted #999; color:#999;" onclick="alert('{po_name}')">#</span>
                            {ordertype_badge}
                            {status_badge}
                            <span style="font-size:14px; font-weight:600; color:#333333; margin-left:8px;">€ {po_amount:,.0f}</span>
                            {button_html}
                        </div>
                        {desc_html}
                        <div class="po-card-row">
                            <div class="po-detail">{po_plaats} | {po_personen} px {po_kinderen} kd</div>
                        </div>
                        {payment_terms_html}
                    </div>
                """
        
        html_content += """
                </div>
            </div>
            
            <div id="beschikbaar-section">
                <h2 class="section-header">Beschikbare orders</h2>
                <div class="legend">
                    <span style="color:#e67e22;">●</span> Beschikbaar &nbsp;
                    <span style="color:#3498db;">●</span> Offerte &nbsp;
                    <span style="color:#27ae60;">●</span> Order
                </div>
                <div id="beschikbaar-cards">
        """
        
        if not pos:
            html_content += """
                    <div class="empty-state">
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
                short_date = format_short_date(po_commitment_date)
                po_plaats = po.get('x_studio_plaats', 'N/A')
                po_personen = po.get('x_studio_aantal_personen', 'N/A')
                po_kinderen = po.get('x_studio_aantal_kinderen', 'N/A')
                po_ordertype = po.get('x_studio_ordertype', '')
                po_payment_term = po.get('payment_term_id', False)
                
                # Status bullet
                if po_state == 'sent':
                    bullet_color = '#3498db'
                elif po_state == 'sale':
                    bullet_color = '#27ae60'
                else:
                    bullet_color = '#e67e22'
                
                # Ordertype badge
                ordertype_badge = ''
                if po_ordertype == 'b2b':
                    ordertype_badge = '<span style="background: #3498db; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">Zakelijk</span>'
                elif po_ordertype == 'b2c':
                    ordertype_badge = '<span style="background: #95a5a6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">Particulier</span>'
                
                # Payment terms (only for b2b, exclude "Vooraf")
                payment_terms_html = ''
                if po_ordertype == 'b2b' and po_payment_term:
                    payment_term_name = po_payment_term[1] if isinstance(po_payment_term, (list, tuple)) else str(po_payment_term)
                    if 'Vooraf' not in payment_term_name:
                        payment_terms_html = f'<div class="po-card-row"><div class="po-detail">Betaalconditie: {payment_term_name}</div></div>'
                
                # Order line descriptions
                descriptions = lines_by_order.get(po.get('id'), [])
                desc_html = ''
                if descriptions:
                    desc_list = ' | '.join(descriptions)
                    desc_html = f'<div class="po-card-row"><div class="po-detail">📦 {desc_list}</div></div>'
                
                html_content += f"""
                    <div class="po-card" data-section="beschikbaar">
                        <div class="po-card-row">
                            <span style="color:{bullet_color};font-size:16px;">●</span>
                            <span class="po-detail" style="margin-left:4px;">{short_date}</span>
                            <span title="{po_name}" style="cursor:help; border-bottom:1px dotted #999; color:#999;" onclick="alert('{po_name}')">#</span>
                            {ordertype_badge}
                            <span style="font-size:14px; font-weight:600; color:#333333; margin-left:8px;">€ {po_amount:,.0f}</span>
                            <button class="claim-btn" onclick="claimPO({po_id}, '{po_name}')" style="width:auto; padding:8px 20px; margin-left:auto;">Claim</button>
                        </div>
                        {desc_html}
                        <div class="po-card-row">
                            <div class="po-detail">{po_plaats} | {po_personen} px {po_kinderen} kd</div>
                        </div>
                        {payment_terms_html}
                    </div>
                """
        
        html_content += """
                </div>
            </div>
            
            <div id="mijn-section">
                <h2 class="section-header">Mijn Opdrachten</h2>
                <div class="legend">
                    <span style="color:#e67e22;">●</span> Beschikbaar &nbsp;
                    <span style="color:#3498db;">●</span> Offerte &nbsp;
                    <span style="color:#27ae60;">●</span> Order
                </div>
                <div id="mijn-cards">
        """
        
        if not claimed:
            html_content += """
                        <div class="empty-state">
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
                short_date = format_short_date(po_commitment_date)
                po_plaats = po.get('x_studio_plaats', 'N/A')
                po_personen = po.get('x_studio_aantal_personen', 'N/A')
                po_kinderen = po.get('x_studio_aantal_kinderen', 'N/A')
                po_selection_status = po.get('x_studio_selection_field_67u_1jj77rtf7', 'N/A')
                po_ordertype = po.get('x_studio_ordertype', '')
                po_payment_term = po.get('payment_term_id', False)
                
                # Status bullet
                if po_state == 'sent':
                    bullet_color = '#3498db'
                elif po_state == 'sale':
                    bullet_color = '#27ae60'
                else:
                    bullet_color = '#e67e22'
                
                # Ordertype badge
                ordertype_badge = ''
                if po_ordertype == 'b2b':
                    ordertype_badge = '<span style="background: #3498db; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">Zakelijk</span>'
                elif po_ordertype == 'b2c':
                    ordertype_badge = '<span style="background: #95a5a6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 6px;">Particulier</span>'
                
                # Payment terms (only for b2b, exclude "Vooraf")
                payment_terms_html = ''
                if po_ordertype == 'b2b' and po_payment_term:
                    payment_term_name = po_payment_term[1] if isinstance(po_payment_term, (list, tuple)) else str(po_payment_term)
                    if 'Vooraf' not in payment_term_name:
                        payment_terms_html = f'<div class="po-card-row"><div class="po-detail">Betaalconditie: {payment_term_name}</div></div>'
                
                # Order line descriptions
                descriptions = lines_by_order.get(po.get('id'), [])
                desc_html = ''
                if descriptions:
                    desc_list = ' | '.join(descriptions)
                    desc_html = f'<div class="po-card-row"><div class="po-detail">📦 {desc_list}</div></div>'
                
                # Button based on status
                if po_selection_status == "claimed":
                    button_html = f'<button class="claim-btn" onclick="releaseOrder({po_id}, \'{po_name}\')" style="background:white; color:#e74c3c; border:1px solid #e74c3c; padding:6px 14px; width:auto; margin-left:auto;">Bied aan</button>'
                elif po_selection_status == "transfer":
                    button_html = '<button class="claim-btn" disabled style="background: #3498db; width:auto; padding:8px 20px; margin-left:auto;">Transfer</button>'
                else:
                    button_html = f'<button class="claim-btn" onclick="releaseOrder({po_id}, \'{po_name}\')" style="background:white; color:#e74c3c; border:1px solid #e74c3c; padding:6px 14px; width:auto; margin-left:auto;">Bied aan</button>'
                
                html_content += f"""
                        <div class="po-card" data-section="mijn">
                            <div class="po-card-row">
                                <span style="color:{bullet_color};font-size:16px;">●</span>
                                <span class="po-detail" style="margin-left:4px;">{short_date}</span>
                                <span title="{po_name}" style="cursor:help; border-bottom:1px dotted #999; color:#999;" onclick="alert('{po_name}')">#</span>
                                {ordertype_badge}
                                <span style="font-size:14px; font-weight:600; color:#333333; margin-left:8px;">€ {po_amount:,.0f}</span>
                                {button_html}
                            </div>
                            {desc_html}
                            <div class="po-card-row">
                                <div class="po-detail">{po_plaats} | {po_personen} px {po_kinderen} kd</div>
                            </div>
                            {payment_terms_html}
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
                            btn.textContent = 'Transfer';
                            btn.style.background = '#3498db';
                            btn.disabled = true;
                        } else {
                            showMessage(result.error || 'Fout bij vrijgeven van order.', 'error');
                            btn.disabled = false;
                            btn.textContent = 'Bied aan';
                        }
                    } catch (error) {
                        showMessage('Er is een fout opgetreden. Probeer het opnieuw.', 'error');
                        btn.disabled = false;
                        btn.textContent = 'Bied aan';
                    }
                }
                
                function toggleSplit() {
                    const toggle = document.getElementById('splitToggle');
                    const beschikbaarSection = document.getElementById('beschikbaar-section');
                    const mijnSection = document.getElementById('mijn-section');
                    const mergedSection = document.getElementById('merged-section');
                    
                    if (toggle.checked) {
                        beschikbaarSection.style.display = 'block';
                        mijnSection.style.display = 'block';
                        mergedSection.style.display = 'none';
                    } else {
                        beschikbaarSection.style.display = 'none';
                        mijnSection.style.display = 'none';
                        mergedSection.style.display = 'block';
                    }
                }
            </script>
            <div style="position:fixed; bottom:0; left:0; right:0; background:#333333; padding:10px 16px; display:flex; justify-content:space-between; align-items:center; z-index:100;">
                {mijn_gegevens_button}
                <span style="color:#999; font-size:13px;">{partner['name']}</span>
                <a href="/logout" style="background:#dc3545; color:white; padding:6px 14px; border-radius:6px; text-decoration:none; font-size:13px;">Uitloggen</a>
            </div>
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
