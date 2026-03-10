# Railway PostgreSQL Setup

## Stap 1: Railway PostgreSQL Database Aanmaken

1. **Ga naar Railway Dashboard**
   - Log in op [railway.app](https://railway.app)
   - Selecteer je project (of maak een nieuw project aan)

2. **Voeg PostgreSQL Service Toe**
   - Klik op **"+ New"** of **"Add Service"**
   - Selecteer **"Database"** → **"Add PostgreSQL"**
   - Railway maakt automatisch een PostgreSQL database aan

3. **Haal DATABASE_URL Op**
   - Klik op de PostgreSQL service die je net hebt aangemaakt
   - Ga naar het tabblad **"Variables"** of **"Connect"**
   - Zoek naar **`DATABASE_URL`** of **`POSTGRES_URL`**
   - Kopieer de volledige connection string
   - Format: `postgresql://user:password@host:port/database`

## Stap 2: DATABASE_URL Toevoegen aan .env

Voeg de DATABASE_URL toe aan je `.env` bestand:

```env
DATABASE_URL=postgresql://user:password@host:port/database
```

**Let op:** Vervang de waarden met je echte Railway credentials.

## Stap 3: psycopg2 Installeren

Installeer de PostgreSQL adapter:

```bash
pip install psycopg2-binary
```

Of voeg toe aan `requirements.txt`:
```
psycopg2-binary>=2.9.0
```

## Stap 4: Schema Uitvoeren

Voer het setup script uit:

```bash
python scripts/setup_database.py
```

Het script zal:
- Verbinden met de Railway PostgreSQL database
- Het schema uitvoeren (`database/schema.sql`)
- Alle tabellen aanmaken
- Indexen en triggers instellen
- Verifiëren dat alles correct is aangemaakt

## Verificatie

Na het uitvoeren zou je moeten zien:
- ✅ Schema succesvol uitgevoerd!
- Lijst van aangemaakte tabellen:
  - contacten
  - orders
  - facturen
  - mail_logs
  - agents

## Troubleshooting

### DATABASE_URL niet gevonden
- Controleer of `.env` bestand bestaat
- Controleer of `DATABASE_URL` correct is gespeld
- Zorg dat `load_dotenv()` wordt aangeroepen

### Connection refused
- Controleer of Railway PostgreSQL service actief is
- Controleer of DATABASE_URL correct is (geen typos)
- Controleer firewall/netwerk instellingen

### Permission denied
- Controleer of de database user de juiste rechten heeft
- Railway geeft standaard alle rechten aan de database user

### Extension uuid-ossp niet gevonden
- Railway PostgreSQL heeft deze extensie standaard beschikbaar
- Als dit faalt, controleer Railway PostgreSQL versie

## Railway Environment Variables

Als je Railway gebruikt voor deployment, voeg ook DATABASE_URL toe als Railway environment variable:
- Ga naar je Railway project
- Klik op je service (FastAPI app)
- Ga naar **"Variables"**
- Voeg `DATABASE_URL` toe met de waarde van je PostgreSQL service
