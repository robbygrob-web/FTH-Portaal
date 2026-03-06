# FTH Portaal

Een portaal voor FTH waar leveranciers (partners) kunnen inloggen en inkooporders kunnen claimen.

## Functionaliteit

- **Partner Authenticatie**: Leveranciers loggen in met hun Odoo email en wachtwoord
- **Dashboard**: Overzicht van beschikbare inkooporders zonder partner
- **Claim Functionaliteit**: Partners kunnen een inkooporder claimen door op een knop te klikken
- **Automatische Update**: Het `partner_id` veld in Odoo wordt automatisch bijgewerkt naar de geclaimde partner

## Railway Omgevingsvariabelen

Zorg ervoor dat de volgende variabelen zijn ingesteld in Railway:

- `ODOO_BASE_URL` - De basis URL van je Odoo instance (bijv. `https://jouw-odoo.odoo.com`)
- `ODOO_DB` - De naam van je Odoo database
- `ODOO_LOGIN` - Admin gebruikersnaam voor Odoo API toegang
- `ODOO_API_KEY` - API key/wachtwoord voor Odoo API toegang
- `SESSION_SECRET` - Een geheim wachtwoord voor sessie encryptie (gebruik een lange, willekeurige string)

## Installatie en Deployment

1. **Lokale ontwikkeling**:
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

2. **Railway deployment**:
   - De `Procfile` is al geconfigureerd
   - Zorg dat alle omgevingsvariabelen zijn ingesteld
   - De app start automatisch op de poort die Railway toewijst

## Gebruik

1. **Inloggen**: Partners gaan naar `/login` en loggen in met hun Odoo credentials
2. **Dashboard**: Na inloggen zien ze een overzicht van beschikbare inkooporders
3. **Claimen**: Klik op "Claim Inkooporder" om een PO te claimen
4. **Uitloggen**: Klik op "Uitloggen" om de sessie te beëindigen

## API Endpoints

- `GET /` - Redirect naar login of dashboard
- `GET /login` - Login pagina
- `POST /login` - Verwerk login
- `GET /logout` - Uitloggen
- `GET /dashboard` - Dashboard met beschikbare inkooporders
- `POST /api/claim-po/{po_id}` - Claim een inkooporder
- `GET /health` - Health check endpoint
- `GET /test-connect` - Test Odoo verbinding

## Odoo Vereisten

- Partners moeten een geldig email adres hebben in Odoo
- Partners moeten kunnen inloggen met hun email en wachtwoord
- De admin gebruiker moet rechten hebben om purchase orders te lezen en te updaten
- Purchase orders zonder `partner_id` worden getoond als beschikbaar om te claimen

## Veiligheid

- Sessies worden beveiligd met `SESSION_SECRET`
- Partner authenticatie gebeurt direct via Odoo
- Alleen ingelogde partners kunnen inkooporders claimen
- Elke claim wordt gekoppeld aan de ingelogde partner
