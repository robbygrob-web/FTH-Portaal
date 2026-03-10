# Gravity Forms Webhook Setup

Dit document beschrijft hoe je de Gravity Forms webhook instelt om nieuwe aanvragen automatisch naar onze FastAPI backend te sturen.

## Endpoint Informatie

**URL:** `https://fth-portaal-production.up.railway.app/webhooks/gravity/aanvraag?token=<WEBHOOK_SECRET>`

**Method:** POST

**Content-Type:** application/json

**Authenticatie:** Via query parameter `token`

**Note:** De WEBHOOK_SECRET staat in `.env` (niet in GitHub). Voeg deze toe aan de URL als query parameter.

## Request Body Format

Gravity Forms kan verschillende veldnamen gebruiken. Het endpoint ondersteunt meerdere varianten:

### Verplichte Velden

- **email** (of `Email` of `email_address`) - Verplicht voor contact identificatie

### Optionele Velden

**Contact gegevens:**
- `name` / `Name` / `bedrijfsnaam` - Naam van contact
- `phone` / `Phone` / `telefoon` - Telefoonnummer
- `street` / `Street` / `straat` / `address` - Straatnaam
- `zip` / `Zip` / `postcode` / `postal_code` - Postcode
- `city` / `City` / `stad` - Stad

**Order gegevens:**
- `event_date` / `Event Date` / `datum` / `Datum` - Datum/tijd evenement
- `location` / `Location` / `locatie` / `Locatie` - Locatie van evenement
- `aantal_personen` / `Aantal personen` / `personen` / `Personen` - Aantal personen
- `aantal_kinderen` / `Aantal kinderen` / `kinderen` - Aantal kinderen
- `opmerkingen` / `Opmerkingen` / `notes` / `Notes` / `message` - Opmerkingen

### Voorbeeld Request

```json
{
  "email": "contact@example.com",
  "name": "Bedrijfsnaam BV",
  "phone": "+31612345678",
  "street": "Hoofdstraat 123",
  "zip": "1234 AB",
  "city": "Amsterdam",
  "event_date": "2025-04-15 14:00:00",
  "location": "Amsterdam Centrum",
  "aantal_personen": 150,
  "aantal_kinderen": 20,
  "opmerkingen": "Graag vegetarische opties"
}
```

## Response Format

**Succes (200):**
```json
{
  "status": "success",
  "message": "Aanvraag verwerkt",
  "contact_id": "uuid-van-contact",
  "order_id": "uuid-van-order",
  "ordernummer": "GF-20250415-140000-ABC12345"
}
```

**Fout (400/401/500):**
```json
{
  "detail": "Foutmelding"
}
```

## Gravity Forms Configuratie

### Stap 1: Webhook Toevoegen

1. **Ga naar Gravity Forms:**
   - WordPress Admin → **Forms** → Selecteer je formulier
   - Klik op **Settings** → **Webhooks**

2. **Voeg nieuwe webhook toe:**
   - Klik op **Add New**
   - **Name:** `FTH Portaal Aanvraag`
   - **URL:** `https://fth-portaal-production.up.railway.app/webhooks/gravity/aanvraag?token=<WEBHOOK_SECRET>`
     - Vervang `<WEBHOOK_SECRET>` met de waarde uit `.env`
   - **Method:** `POST`
   - **Request Format:** `JSON`

3. **Configureer Field Mapping:**
   Map Gravity Forms velden naar de verwachte veldnamen:
   
   | Gravity Forms Veld | Map naar |
   |-------------------|----------|
   | Email | `email` |
   | Name | `name` |
   | Phone | `phone` |
   | Address | `street` |
   | City | `city` |
   | Zip | `zip` |
   | Date/Time | `event_date` |
   | Location | `location` |
   | Number (personen) | `aantal_personen` |
   | Number (kinderen) | `aantal_kinderen` |
   | Paragraph Text | `opmerkingen` |

5. **Activeer webhook:**
   - Zet **Active** aan
   - Sla op

### Stap 2: Testen

1. **Test met Gravity Forms:**
   - Vul het formulier in en verstuur
   - Controleer of de aanvraag in de database staat

2. **Test met script:**
   ```bash
   python scripts/test_gravity_webhook.py
   ```

## Wat gebeurt er bij een webhook call?

1. **Token verificatie:** Controleert `X-Gravity-Webhook-Token` header
2. **Contact lookup:** Zoekt contact op basis van email
3. **Contact aanmaken:** Als niet gevonden, maakt nieuw contact aan
4. **Order aanmaken:** Maakt nieuwe order aan met:
   - Status: `draft`
   - Portaal status: `nieuw`
   - Uniek ordernummer: `GF-YYYYMMDD-HHMMSS-UUID`
   - Order datum: huidige datum/tijd
   - Leverdatum: uit formulier of default (+7 dagen)

## Ordernummer Format

Ordernummers worden automatisch gegenereerd:
```
GF-YYYYMMDD-HHMMSS-UUID(8)
```

Voorbeeld: `GF-20250415-140000-ABC12345`

## Troubleshooting

### Webhook wordt niet aangeroepen

1. Controleer of webhook actief is in Gravity Forms
2. Controleer Gravity Forms logs
3. Test endpoint met curl:
   ```bash
   curl -X POST "https://fth-portaal-production.up.railway.app/webhooks/gravity/aanvraag?token=<WEBHOOK_SECRET>" \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "name": "Test"}'
   ```

### 401 Unauthorized

1. Controleer of `token` query parameter aanwezig is in URL
2. Controleer WEBHOOK_SECRET in `.env`
3. Controleer of token exact overeenkomt

### 400 Bad Request

1. Controleer of `email` veld aanwezig is
2. Controleer JSON format
3. Controleer logs voor specifieke foutmelding

### 500 Internal Server Error

1. Controleer DATABASE_URL in `.env`
2. Controleer database connectie
3. Controleer of `contacten` en `orders` tabellen bestaan
4. Controleer logs voor details

## Test Script

Gebruik `scripts/test_gravity_webhook.py` om het endpoint te testen:

```bash
# Lokaal (zorg dat FastAPI draait)
python scripts/test_gravity_webhook.py

# Of met production URL
BASE_URL=https://fth-portaal-production.up.railway.app python scripts/test_gravity_webhook.py
```

## Belangrijke Opmerkingen

1. **Email is verplicht:** Zonder email kan geen contact worden aangemaakt
2. **Geen duplicaten:** Als contact al bestaat (op basis van email), wordt bestaand contact gebruikt
3. **Order status:** Nieuwe orders krijgen altijd status `nieuw` (portaal_status)
4. **Ordernummer:** Wordt automatisch gegenereerd, moet uniek zijn
5. **Datum parsing:** Ondersteunt meerdere datum formaten, default is +7 dagen als niet opgegeven
