# Railway DATABASE_URL Environment Variable Setup

## Overzicht

Voor de webhook functionaliteit en database connecties moet `DATABASE_URL` ingesteld zijn als Railway environment variable, niet alleen in je lokale `.env` bestand.

## Stap-voor-stap Instructies

### Stap 1: Haal DATABASE_URL op van Railway PostgreSQL Service

1. **Log in op Railway Dashboard**
   - Ga naar [railway.app](https://railway.app)
   - Selecteer je project

2. **Open PostgreSQL Service**
   - Klik op je PostgreSQL service (meestal genaamd "Postgres" of "Database")
   - Ga naar het tabblad **"Variables"** of **"Connect"**

3. **Kopieer DATABASE_URL**
   - Zoek naar **`DATABASE_URL`** of **`POSTGRES_URL`**
   - Klik op het oog-icoon om de waarde te tonen
   - Kopieer de volledige connection string
   - Format: `postgresql://user:password@host:port/database`

### Stap 2: Voeg DATABASE_URL toe aan FastAPI Service

1. **Open FastAPI Service**
   - Ga terug naar je project overzicht
   - Klik op je FastAPI service (de service die je applicatie draait)

2. **Ga naar Variables**
   - Klik op het tabblad **"Variables"**
   - Of klik op **"Settings"** → **"Variables"**

3. **Voeg DATABASE_URL toe**
   - Klik op **"+ New Variable"** of **"Add Variable"**
   - **Variable Name**: `DATABASE_URL`
   - **Value**: Plak de DATABASE_URL die je hebt gekopieerd van de PostgreSQL service
   - Klik op **"Add"** of **"Save"**

### Stap 3: Verifieer

1. **Check Variables Tab**
   - Je zou nu `DATABASE_URL` moeten zien in de lijst van environment variables
   - De waarde zou moeten beginnen met `postgresql://`

2. **Redeploy (optioneel)**
   - Railway zou automatisch moeten redeployen na het toevoegen van een variable
   - Als dat niet gebeurt, klik op **"Deploy"** → **"Redeploy"**

## Belangrijke Opmerkingen

### Interne vs. Publieke URL

Railway biedt twee soorten DATABASE_URL:

1. **Interne URL** (aanbevolen voor Railway services):
   - Format: `postgresql://postgres:***@postgres.railway.internal:5432/railway`
   - Alleen bereikbaar binnen Railway netwerk
   - Sneller en veiliger
   - **Gebruik deze voor Railway environment variable**

2. **Publieke URL** (alleen voor lokaal testen):
   - Format: `postgresql://postgres:password@metro.proxy.rlwy.net:18535/railway`
   - Bereikbaar van buiten Railway
   - Langzamer, alleen voor development
   - **Gebruik deze alleen in je lokale `.env` bestand**

### Environment Variable Prioriteit

Railway environment variables hebben **prioriteit** over `.env` bestanden:
- Als `DATABASE_URL` in Railway staat, wordt die gebruikt
- Lokale `.env` wordt alleen gebruikt voor lokale development

### Veiligheid

- **Nooit commit** je `.env` bestand naar Git
- Railway environment variables zijn automatisch veilig (niet zichtbaar in logs)
- De interne Railway URL bevat `***` als placeholder - Railway vult dit automatisch in

## Troubleshooting

### DATABASE_URL niet gevonden

**Symptoom**: `ValueError: DATABASE_URL niet gevonden in environment variabelen`

**Oplossing**:
1. Controleer of `DATABASE_URL` in Railway Variables staat
2. Controleer of de variable naam exact `DATABASE_URL` is (hoofdletters)
3. Redeploy de service na het toevoegen van de variable

### Connection Refused

**Symptoom**: `psycopg2.OperationalError: could not connect to server`

**Oplossing**:
1. Controleer of je de **interne URL** gebruikt (niet de publieke URL)
2. Controleer of PostgreSQL service actief is
3. Controleer of beide services in hetzelfde Railway project zitten

### Webhook Routes Verschijnen Niet

**Mogelijke oorzaken**:
1. `DATABASE_URL` ontbreekt → Import faalt stil
2. `psycopg2-binary` niet geïnstalleerd → Check Railway build logs
3. Import error wordt niet gelogd → Check Railway logs voor `[ERROR]` berichten

**Debug stappen**:
1. Check Railway logs voor `[DEBUG] Webhooks router geïmporteerd` bericht
2. Check Railway logs voor `[ERROR] Webhooks router import gefaald` bericht
3. Check Railway build logs voor `psycopg2` installatie

## Verificatie Commando's

Na het instellen kun je verifiëren:

```bash
# Lokaal testen (gebruik publieke URL in .env)
python -c "from app.webhooks import router; print(f'Routes: {len(router.routes)}')"

# Check Railway logs voor:
# [DEBUG] Webhooks router geïmporteerd: 3 routes
# [DEBUG] Webhooks router geregistreerd in app
```

## Snelle Checklist

- [ ] PostgreSQL service bestaat in Railway project
- [ ] DATABASE_URL gekopieerd van PostgreSQL service Variables
- [ ] DATABASE_URL toegevoegd aan FastAPI service Variables
- [ ] Variable naam is exact `DATABASE_URL` (hoofdletters)
- [ ] Service geredeployed na het toevoegen van variable
- [ ] Railway logs tonen geen `[ERROR]` berichten
- [ ] Railway logs tonen `[DEBUG] Webhooks router geïmporteerd` bericht
