# Planning Email Systeem - Bevestigingssamenvatting

**Datum:** 2026-03-10  
**Status:** Wachtend op goedkeuring

---

## 1. DATABASE MIGRATIES

### Nieuwe velden op `orders` tabel:

| Veldnaam | Type | Default | Constraints | Beschrijving |
|----------|------|---------|-------------|--------------|
| `planning_afgemeld` | BOOLEAN | FALSE | - | Of klant heeft afgemeld voor planning |
| `planning_afmeld_token` | UUID | NULL | NULLABLE | Unieke token voor afmeldlink (alleen bij betaalde orders) |

**Migratie SQL:**
```sql
ALTER TABLE orders 
ADD COLUMN planning_afgemeld BOOLEAN DEFAULT FALSE,
ADD COLUMN planning_afmeld_token UUID;
```

**Opmerking:** 
- `contacten.voornaam` bestaat al in de database, geen migratie nodig.
- `orders.betaal_status` bestaat al in de live database (toegevoegd via `admin_routes.py` endpoint), geen migratie nodig.

**Verificatie schema.sql:**
- ✅ `orders.betaal_status` bestaat **AL** in live database (toegevoegd via admin endpoint) — geen migratie nodig
- ✅ `orders.klant_id` (niet `contact_id`) — correct veldnaam
- ✅ `facturen.factuurnummer` bestaat **WEL** — kan worden opgehaald als factuur record bestaat

---

## 2. BESTANDEN DIE WORDEN AANGEMAAKT

| Bestand | Beschrijving |
|---------|--------------|
| `app/email_templates/planning_9dagen.html` | HTML email template voor 9 dagen vooraf (geen afmeldknop, geen token) |
| `app/email_templates/planning_7dagen.html` | HTML email template voor 7 dagen vooraf (geen afmeldknop, geen token) |
| `app/email_templates/planning_5dagen_betaald.html` | HTML email template voor 5 dagen vooraf - betaald (met afmeldknop, token wordt gegenereerd) |
| `app/email_templates/planning_5dagen_onbetaald.html` | HTML email template voor 5 dagen vooraf - onbetaald (geen afmeldknop) |
| `app/email_templates/planning_3dagen_betaald.html` | HTML email template voor 3 dagen vooraf - betaald (met afmeldknop, gebruikt bestaande token) |
| `app/email_templates/planning_3dagen_onbetaald.html` | HTML email template voor 3 dagen vooraf - onbetaald (geen afmeldknop) |
| `app/email_templates/planning_1dag_betaald.html` | HTML email template voor 1 dag vooraf - betaald (met afmeldknop, gebruikt bestaande token) |
| `app/email_templates/planning_1dag_onbetaald.html` | HTML email template voor 1 dag vooraf - onbetaald (geen afmeldknop) |
| `app/factuur.py` | Module voor on-the-fly PDF generatie van facturen via reportlab (geen opslag) |
| `app/planning_scheduler.py` | Scheduler module die dagelijks controleert welke planning emails verstuurd moeten worden |

---

## 3. BESTANDEN DIE WORDEN GEWIJZIGD

| Bestand | Wijzigingen |
|---------|-------------|
| `app/mail.py` | Uitbreiden `stuur_mail()` functie met bijlagen support (attachments parameter) |
| `app/templates.py` | Toevoegen 8 nieuwe render functies voor planning templates: `render_planning_9dagen()`, `render_planning_7dagen()`, `render_planning_5dagen_betaald()`, `render_planning_5dagen_onbetaald()`, `render_planning_3dagen_betaald()`, `render_planning_3dagen_onbetaald()`, `render_planning_1dag_betaald()`, `render_planning_1dag_onbetaald()` |
| `app/routes.py` | Toevoegen 2 nieuwe endpoints: `GET /planning/afmelden/{token}` (toon bevestigingspagina) en `POST /planning/afmelden/{token}` (verwerk afmelding, zet `planning_afgemeld = TRUE`) |
| `app/main.py` | Mounten van planning scheduler als background task (APScheduler of FastAPI BackgroundTasks) |
| `database/schema.sql` | Toevoegen migratie SQL voor nieuwe velden (zie sectie 1) |

---

## 4. TEMPLATE OVERZICHT

| Template | Trigger Conditie | Variant | Bijlagen | Afmeldknop | Token Actie |
|----------|------------------|---------|----------|------------|-------------|
| `planning_9dagen.html` | 9 dagen voor leverdatum | Altijd | Geen | ❌ Nee | Geen |
| `planning_7dagen.html` | 7 dagen voor leverdatum | Altijd | Factuur PDF | ❌ Nee | Geen |
| `planning_5dagen_betaald.html` | 5 dagen voor leverdatum | `betaal_status = 'betaald'` | Factuur PDF | ✅ Ja | **Genereer** UUID token → opslaan in `orders.planning_afmeld_token` |
| `planning_5dagen_onbetaald.html` | 5 dagen voor leverdatum | `betaal_status != 'betaald'` | Factuur PDF | ❌ Nee | Geen |
| `planning_3dagen_betaald.html` | 3 dagen voor leverdatum | `betaal_status = 'betaald'` | Factuur PDF | ✅ Ja | **Gebruik** bestaande `orders.planning_afmeld_token` |
| `planning_3dagen_onbetaald.html` | 3 dagen voor leverdatum | `betaal_status != 'betaald'` | Factuur PDF | ❌ Nee | Geen |
| `planning_1dag_betaald.html` | 1 dag voor leverdatum | `betaal_status = 'betaald'` | Factuur PDF | ✅ Ja | **Gebruik** bestaande `orders.planning_afmeld_token` |
| `planning_1dag_onbetaald.html` | 1 dag voor leverdatum | `betaal_status != 'betaald'` | Factuur PDF | ❌ Nee | Geen |

**Bijlagen:** Alle templates behalve dag 9 krijgen factuur PDF als bijlage (on-the-fly gegenereerd via reportlab). Dag 9 is alleen aankondiging, factuur volgt op dag 7.

---

## 5. SCHEDULER LOGICA

### Dag 9 (9 dagen voor leverdatum):
- **Query conditie:** `(leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date + INTERVAL '9 days' AND status = 'sale' AND planning_afgemeld = FALSE`
- **Mail variant:** Altijd `planning_9dagen.html` (betaal_status is altijd 'onbetaald' want factuur nog niet verstuurd)
- **Bijlagen:** Geen (dag 9 is alleen aankondiging, factuur volgt op dag 7)
- **Token actie:** Geen
- **Dubbele verzending check:** Check `mail_logs` op `template_naam` + `order_id` + datum vandaag

### Dag 7 (7 dagen voor leverdatum):
- **Query conditie:** `(leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date + INTERVAL '7 days' AND status = 'sale' AND planning_afgemeld = FALSE`
- **Mail variant:** Altijd `planning_7dagen.html`
- **Bijlagen:** Factuur PDF (on-the-fly)
- **Token actie:** Geen
- **Dubbele verzending check:** Check `mail_logs` op `template_naam` + `order_id` + datum vandaag

### Dag 5 (5 dagen voor leverdatum):
- **Query conditie:** `(leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date + INTERVAL '5 days' AND status = 'sale' AND planning_afgemeld = FALSE`
- **Mail variant:** 
  - `planning_5dagen_betaald.html` als `betaal_status = 'betaald'`
  - `planning_5dagen_onbetaald.html` als `betaal_status != 'betaald'`
- **Bijlagen:** Factuur PDF (on-the-fly)
- **Token actie:** 
  - **Betaald:** Genereer UUID → opslaan in `orders.planning_afmeld_token` (alleen als nog niet bestaat). Token wordt altijd aangemaakt op dag 5 als eerste betaalde mail, geen fallback nodig voor dag 3 en 1.
  - **Onbetaald:** Geen
- **Dubbele verzending check:** Check `mail_logs` op `template_naam` + `order_id` + datum vandaag

### Dag 3 (3 dagen voor leverdatum):
- **Query conditie:** `(leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date + INTERVAL '3 days' AND status = 'sale' AND planning_afgemeld = FALSE`
- **Mail variant:**
  - `planning_3dagen_betaald.html` als `betaal_status = 'betaald'`
  - `planning_3dagen_onbetaald.html` als `betaal_status != 'betaald'`
- **Bijlagen:** Factuur PDF (on-the-fly)
- **Token actie:**
  - **Betaald:** Gebruik bestaande `orders.planning_afmeld_token` (altijd aanwezig, gegenereerd op dag 5)
  - **Onbetaald:** Geen
- **Dubbele verzending check:** Check `mail_logs` op `template_naam` + `order_id` + datum vandaag

### Dag 1 (1 dag voor leverdatum):
- **Query conditie:** `(leverdatum AT TIME ZONE 'Europe/Amsterdam')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date + INTERVAL '1 day' AND status = 'sale' AND planning_afgemeld = FALSE`
- **Mail variant:**
  - `planning_1dag_betaald.html` als `betaal_status = 'betaald'`
  - `planning_1dag_onbetaald.html` als `betaal_status != 'betaald'`
- **Bijlagen:** Factuur PDF (on-the-fly)
- **Token actie:**
  - **Betaald:** Gebruik bestaande `orders.planning_afmeld_token` (altijd aanwezig, gegenereerd op dag 5)
  - **Onbetaald:** Geen
- **Dubbele verzending check:** Check `mail_logs` op `template_naam` + `order_id` + datum vandaag

**Scheduler frequentie:** Dagelijks om 09:00 Europe/Amsterdam (of configuratie via environment variabele).

**Dubbele verzending preventie:**
Voor elke mail: check eerst of `template_naam` + `order_id` + datum vandaag al bestaat in `mail_logs`. Als ja: overslaan.

Query:
```sql
SELECT COUNT(*) FROM mail_logs 
WHERE order_id = '{order_id}' 
AND template_naam = '{template_naam}' 
AND DATE(verzonden_op AT TIME ZONE 'Europe/Amsterdam') = 
    (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Amsterdam')::date
```

Als count > 0: skip deze mail (al verzonden vandaag).

---

## 6. AFMELD FLOW

### Stap 1: Token Generatie (Dag 5 - Betaald)
- Scheduler detecteert order met `betaal_status = 'betaald'` en `planning_afmeld_token IS NULL`
- Genereer UUID v4 token
- Opslaan in `orders.planning_afmeld_token`
- Token wordt gebruikt in afmeldlink: `/planning/afmelden/{token}`

### Stap 2: Email Verzending (Dag 5, 3, 1 - Betaald)
- Template bevat afmeldknop met link: `https://{domain}/planning/afmelden/{planning_afmeld_token}`
- Link wordt alleen getoond als `betaal_status = 'betaald'` EN `planning_afmeld_token IS NOT NULL`
- **Opmerking:** Op dag 9 is `betaal_status` altijd 'onbetaald' (factuur nog niet verstuurd), dus geen token nodig. Token wordt altijd aangemaakt op dag 5 als eerste betaalde mail. Geen fallback nodig voor dag 3 en 1 — token is altijd aanwezig als `betaal_status = 'betaald'`.

### Stap 3: Afmeld Pagina (GET /planning/afmelden/{token})
- Valideer token: `SELECT * FROM orders WHERE planning_afmeld_token = '{token}' AND planning_afgemeld = FALSE`
- Toon bevestigingspagina met:
  - Order details (ordernummer, leverdatum, plaats)
  - Bevestigingsknop: "Ja, ik wil afmelden"
  - Annuleerknop: "Nee, ik wil niet afmelden"

### Stap 4: Afmelding Verwerken (POST /planning/afmelden/{token})
- Valideer token opnieuw
- Update order: `UPDATE orders SET planning_afgemeld = TRUE WHERE planning_afmeld_token = '{token}'`
- Toon bevestigingspagina: "U heeft zich succesvol afgemeld"
- Log actie in `mail_logs` (optioneel)

**Beveiliging:**
- Token is UUID v4 (onvoorspelbaar)
- Token wordt alleen gebruikt voor afmelding (niet voor andere acties)
- Na afmelding kan token niet opnieuw gebruikt worden (`planning_afgemeld = TRUE`)

---

## 7. PAKKET BEPALING

### Uitsluitingslijst (artikelen die NIET als pakket tellen):
- `reiskosten`
- `toeslag`
- `broodjes`
- `drankjes`
- `kids pakket`

### Query Logica:
```sql
SELECT DISTINCT oa.naam
FROM order_artikelen oa
WHERE oa.order_id = '{order_id}'
  AND LOWER(oa.naam) NOT IN ('reiskosten', 'toeslag', 'broodjes', 'drankjes', 'kids pakket')
  AND oa.naam IS NOT NULL
  AND oa.naam != ''
LIMIT 1;
```

**Resultaat:** Eerste artikelnaam die niet in uitsluitingslijst staat wordt gebruikt als `pakket_naam` in template.

**Als geen pakket gevonden:** Gebruik fallback `pakket_naam = "Standaard pakket"` of leeg laten.

---

## 8. VOORNAAM VELD

### Gebruikt veld: `contacten.voornaam`

**Bevestiging:** 
- Veld `voornaam` bestaat al in `contacten` tabel (geen migratie nodig)
- **NIET** gebruiken: `naam.split()[0]` of andere string manipulatie
- **WEL** gebruiken: Direct `contact.voornaam` uit database

**Query voorbeeld:**
```sql
SELECT c.voornaam, c.naam, c.email
FROM contacten c
JOIN orders o ON o.klant_id = c.id
WHERE o.id = '{order_id}';
```

**Fallback:** Als `voornaam IS NULL`, gebruik `naam` als fallback (maar voorkeur voor expliciet `voornaam` veld).

---

## 9. BROODJES & DRANKJES LOGICA

### Dag 9:
- **Toon:** Ja/Nee blok voor broodjes en drankjes
- **Logica:** Check of artikel met naam `'broodjes'` of `'drankjes'` bestaat in `order_artikelen` voor deze order
- **Query:** `SELECT COUNT(*) FROM order_artikelen WHERE order_id = '{order_id}' AND LOWER(naam) IN ('broodjes', 'drankjes')`
- **Weergave:** 
  - Als count > 0: "Broodjes: Ja" / "Drankjes: Ja"
  - Als count = 0: "Broodjes: Nee" / "Drankjes: Nee"

### Dag 7, 5, 3, 1:
- **Toon:** ❌ NIET tonen (geen broodjes/drankjes blok in template)

---

## 10. FACTUUR PDF GENERATIE

### On-the-fly generatie (geen opslag):
- **Library:** reportlab (al gebruikt in `app/contract.py`)
- **Functie:** `app/factuur.py` → `generate_factuur_pdf(order_data: dict) -> bytes`
- **Input:** Order data (geen afhankelijkheid van `facturen` tabel)
- **Output:** PDF bytes (direct als bijlage toevoegen aan email)
- **Opslag:** ❌ NOOIT opslaan op schijf of in database

### Factuur Data (uit database):
- **orders:** leverdatum, plaats, aantal_personen, aantal_kinderen, ordertype, ordernummer
- **order_artikelen:** naam, aantal, prijs_incl (per artikel)
- **contacten:** voornaam, naam (achternaam), email, straat, postcode, stad, btw_nummer
- **factuurnummer:** 
  - Ophalen uit `facturen.factuurnummer` ALS record bestaat voor deze order (`facturen.order_id = orders.id`)
  - Als geen factuur record: genereer tijdelijk nummer op basis van order id (bijv. `TEMP-{order_id[:8]}`)
  - **Geen crash, geen lege PDF** — altijd een geldige PDF als bijlage genereren

**Verificatie:**
- ✅ `orders.ordernummer` bestaat **WEL** in schema.sql (VARCHAR(50) NOT NULL UNIQUE) — kan gebruikt worden
- ✅ `contacten.btw_nummer` is **optioneel** — alleen tonen op PDF als veld bestaat EN niet leeg is (`btw_nummer IS NOT NULL AND btw_nummer != ''`)

### Bedragen Berekening:
**NIET gebruiken:** `orders.totaal_bedrag`, `orders.bedrag_excl_btw`, `orders.bedrag_btw`

**WEL berekenen via order_artikelen:**
```sql
-- Totaal bedrag (inclusief BTW)
SELECT SUM(prijs_incl * aantal) as totaal
FROM order_artikelen
WHERE order_id = '{order_id}';
```

**BTW berekening (9%):**
- **Totaal (incl BTW):** `SUM(prijs_incl * aantal)`
- **Bedrag excl BTW:** `totaal / 1.09`
- **BTW bedrag:** `totaal - (totaal / 1.09)`

**Voorbeeld:**
- Totaal = €109.00
- Excl BTW = €109.00 / 1.09 = €100.00
- BTW = €109.00 - €100.00 = €9.00

---

## 11. OPEN PUNTEN BEANTWOORD

### Betaalstatus "betaald":
- **Hoe wordt dit gezet?** Via Mollie webhook (al werkend)
- **Waar:** `app/webhooks.py` → Mollie webhook handler zet `betaal_status = 'betaald'` bij succesvolle betaling
- **Status:** ✅ Al geïmplementeerd, geen wijzigingen nodig

### Afmeld token aanmaken:
- **Wanneer:** Bij dag 5 betaald mail (als token nog niet bestaat)
- **Waar:** In `app/planning_scheduler.py` → functie `send_planning_5dagen_betaald()`
- **Actie:** `UPDATE orders SET planning_afmeld_token = '{uuid}' WHERE id = '{order_id}' AND planning_afmeld_token IS NULL`

---

## 12. IMPLEMENTATIE VOLGORDE (na goedkeuring)

1. **Database migraties** → `database/schema.sql` bijwerken + migratie script
2. **app/mail.py** → Bijlagen support toevoegen
3. **app/factuur.py** → PDF generatie module (nieuw bestand)
4. **HTML email templates** → Alle 8 templates aanmaken
5. **app/templates.py** → Render functies toevoegen
6. **app/planning_scheduler.py** → Scheduler logica (nieuw bestand)
7. **app/routes.py** → Afmeld endpoints (GET + POST)
8. **app/main.py** → Scheduler mounten

---

## BEVESTIGING

**Alle bovenstaande punten zijn correct en compleet?**

- [ ] Database migraties correct
- [ ] Template namen exact zoals gespecificeerd
- [ ] Voornaam veld: `contacten.voornaam` (niet naam.split())
- [ ] Pakket uitsluitingen: reiskosten, toeslag, broodjes, drankjes, kids pakket
- [ ] Broodjes/drankjes: alleen dag 9, niet dag 7/5/3/1
- [ ] Afmeldknop: alleen bij betaald, token logica correct
- [ ] Factuur PDF: on-the-fly, geen opslag
- [ ] Scheduler logica: per dag correct gespecificeerd

**Wacht op "goedgekeurd" voordat implementatie start.**
