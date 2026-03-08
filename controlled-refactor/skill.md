# Controlled Refactor Skill

## Doel
Deze Skill is bedoeld voor gecontroleerde code-refactors waarbij eerst een analyse wordt gedaan en nooit direct wijzigingen worden uitgevoerd zonder expliciete toestemming. Gebruik deze Skill wanneer je een project professioneel wilt herstructureren, opschonen of modulair opdelen zonder de kernlogica te veranderen.

## Toepassingsgebied
- Python/FastAPI-projecten
- Odoo/XML-RPC-achtige projecten
- Vergelijkbare backend-refactors

## Werkwijze: Twee Fasen

### FASE 1: ANALYSE (Verplicht - Wacht altijd op toestemming)
Voer eerst een grondige analyse uit van:
- Welke bestanden aangepast moeten worden
- Welke bestanden verplaatst moeten worden
- Welke bestanden verwijderd kunnen worden
- Welke imports moeten wijzigen
- Welke risico's op brekende wijzigingen er zijn
- Impact op bestaande endpoints en flows

**STOP na FASE 1** - Wacht op expliciete toestemming van de gebruiker (bijv. "Go") voordat je doorgaat.

### FASE 2: UITVOERING (Alleen na expliciete toestemming)
Voer de refactor uit en rapporteer:
- Welke bestanden zijn aangepast
- Welke bestanden zijn verwijderd
- Welke imports zijn gewijzigd
- Welke handmatige vervolgstappen nog nodig zijn
- Korte check tegen acceptatiecriteria

## Strikte Restricties

⚠️ **NOOIT doen zonder expliciete vraag:**
- Geen nieuwe frameworks toevoegen
- Geen XML-RPC herschrijven naar JSON-RPC
- Geen async refactor uitvoeren
- Geen businesslogica aanpassen buiten de gevraagde scope
- Geen Docker, CI, pytest-setup of uitgebreide loggingstructuren toevoegen

✅ **ALTIJD doen:**
- Bestaande endpointnamen en flow behouden
- Imports bijwerken en circulaire imports voorkomen
- Alleen expliciet genoemde overbodige bestanden verwijderen
- Wijzigingen klein, gecontroleerd en uitlegbaar houden

## Acceptatiecriteria
- De applicatie start zonder importfouten
- Configuratie wordt op één centrale plek geladen
- Bestaande endpointnamen blijven behouden
- Bestaande flow blijft intact
- Imports zijn bijgewerkt
- Circulaire imports zijn voorkomen

## Gebruik
Wanneer je deze Skill activeert, werk je altijd volgens het twee-fasen model. Zie ook `references/refactor-prompt.md` voor een herbruikbare prompt template.
