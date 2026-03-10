# Gravity Forms Polling Script

## Overzicht

Het script `scripts/poll_gravity_forms.py` haalt Gravity Forms inzendingen op via de REST API en verwerkt ze als orders in de eigen database. Dit vervangt de webhook functionaliteit met een betrouwbaardere polling aanpak.

## Vereisten

### Environment Variabelen

Voeg de volgende variabelen toe aan je `.env` bestand:

```bash
# Gravity Forms REST API Configuratie
WORDPRESS_URL=https://friettruck-huren.nl
GRAVITY_FORMS_API_USERNAME=your_wordpress_username
GRAVITY_FORMS_API_PASSWORD=your_application_password
GRAVITY_FORMS_FORM_ID=1
```

### WordPress Application Password

1. Log in op WordPress admin panel (`https://friettruck-huren.nl/wp-admin`)
2. Ga naar **Users** → **Profile**
3. Scroll naar beneden naar **Application Passwords**
4. Voer een naam in (bijv. "FTH Portaal API")
5. Klik op **Add New Application Password**
6. Kopieer het gegenereerde wachtwoord (dit zie je maar één keer!)
7. Gebruik dit wachtwoord als `GRAVITY_FORMS_API_PASSWORD`

**Let op:** Gebruik niet je normale WordPress wachtwoord, maar een Application Password.

### Form ID Bepalen

1. Ga naar **Forms** → **Forms** in WordPress admin
2. Open het formulier waarvan je entries wilt ophalen
3. Kijk in de URL: `.../wp-admin/admin.php?page=gf_edit_forms&id=1`
4. Het nummer na `id=` is je Form ID

## Gebruik

### Lokaal Testen

```bash
python scripts/poll_gravity_forms.py
```

### Automatisch Uitvoeren

Voor productie gebruik kun je het script periodiek uitvoeren via:

- **Cron job** (Linux/Mac):
  ```bash
  # Elke 5 minuten
  */5 * * * * cd /path/to/project && python scripts/poll_gravity_forms.py
  ```

- **Windows Task Scheduler**:
  - Maak een nieuwe taak
  - Trigger: Elke 5 minuten
  - Actie: `python.exe` met argumenten: `scripts/poll_gravity_forms.py`

- **Railway Cron Job**:
  - Voeg een cron service toe aan je Railway project
  - Command: `python scripts/poll_gravity_forms.py`
  - Schedule: `*/5 * * * *` (elke 5 minuten)

## Hoe Het Werkt

1. **Ophalen Entries**: Script haalt alle entries op van het opgegeven formulier via Gravity Forms REST API
2. **Duplicaat Detectie**: Script controleert of een entry al is verwerkt door te zoeken naar `GF_ENTRY_{entry_id}` in het opmerkingen veld van orders
3. **Contact Aanmaken**: Als contact nog niet bestaat, wordt deze aangemaakt op basis van email
4. **Order Aanmaken**: Elke nieuwe entry wordt verwerkt als order met:
   - Uniek ordernummer (format: `GF-YYYYMMDD-HHMMSS-UUID`)
   - Status: `nieuw`
   - Type: `Aanvraag`
   - Ordertype: `b2c`

## Veld Mapping

Het script probeert automatisch velden te herkennen op basis van:
- **Labels**: Als Gravity Forms labels beschikbaar zijn, worden deze gebruikt
- **Inhoud detectie**: Email adressen, telefoonnummers, etc. worden automatisch gedetecteerd

### Ondersteunde Velden

- **Email**: Automatisch gedetecteerd of via label "email"
- **Naam**: Via label "naam" of "name"
- **Telefoon**: Via label "telefoon" of "phone"
- **Adres**: Via labels "straat", "postcode", "stad"
- **Datum Evenement**: Via label "datum", "date", of "evenement"
- **Locatie**: Via label "locatie" of "location"
- **Aantal Personen**: Via label "personen" of "aantal"
- **Aantal Kinderen**: Via label "kinderen"
- **Opmerkingen**: Via label "opmerking", "notitie", of "message"

## Troubleshooting

### Authenticatie Fout

```
Authenticatie gefaald. Controleer GRAVITY_FORMS_API_USERNAME en GRAVITY_FORMS_API_PASSWORD
```

**Oplossing**: 
- Controleer of je een Application Password gebruikt (niet je normale wachtwoord)
- Controleer of de gebruikersnaam correct is

### Geen Entries Gevonden

**Mogelijke oorzaken**:
- Form ID is incorrect
- Formulier heeft nog geen entries
- API rechten zijn niet correct ingesteld

**Oplossing**:
- Controleer Form ID in WordPress admin
- Test de API handmatig: `curl -u username:password https://friettruck-huren.nl/wp-json/gf/v2/entries?form_ids=1`

### Entries Worden Dubbel Verwerkt

Het script gebruikt het `opmerkingen` veld om te tracken welke entries al zijn verwerkt. Als entries toch dubbel worden verwerkt:

1. Controleer of het `opmerkingen` veld niet wordt overschreven
2. Controleer of de entry ID correct wordt opgeslagen

## API Referentie

### Gravity Forms REST API Endpoints

- **Entries ophalen**: `GET /wp-json/gf/v2/entries?form_ids={form_id}`
- **Authenticatie**: Basic Auth met WordPress username en Application Password

### Response Format

```json
[
  {
    "id": 123,
    "date_created": "2025-03-14 10:30:00",
    "form_fields": {
      "1": "email@example.com",
      "2": "John Doe",
      ...
    },
    "labels": {
      "1": "Email",
      "2": "Naam",
      ...
    }
  }
]
```

## Veiligheid

- **Application Passwords**: Gebruik altijd Application Passwords, niet je normale WordPress wachtwoord
- **HTTPS**: Zorg dat WordPress site HTTPS gebruikt
- **API Rechten**: Beperk API toegang tot alleen wat nodig is
- **Rate Limiting**: Overweeg rate limiting toe te voegen als je veel requests doet
