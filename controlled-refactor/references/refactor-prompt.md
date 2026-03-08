# Standaard Refactor Prompt Template

Gebruik deze prompt wanneer je een gecontroleerde refactor wilt uitvoeren.

---

Ik wil de architectuur van dit project opschonen zonder de kernlogica te veranderen. Werk in twee fasen:

## FASE 1: ANALYSE
Analyseer eerst kort welke bestanden aangepast, verplaatst of verwijderd moeten worden op basis van de onderstaande criteria. Wacht na FASE 1 altijd op mijn 'Go' voordat je wijzigingen uitvoert.

### Analyse Checklist:
- [ ] Welke bestanden moeten aangepast worden?
- [ ] Welke bestanden moeten verplaatst worden?
- [ ] Welke bestanden kunnen verwijderd worden?
- [ ] Welke imports moeten wijzigen?
- [ ] Welke risico's op brekende wijzigingen zijn er?
- [ ] Wat is de impact op bestaande endpoints en flows?

## FASE 2: REFACTOR
Voer de refactor uit waarbij je de code modulair opdeelt in de juiste projectstructuur.

### ✅ ACCEPTATIECRITERIA
- de applicatie start zonder importfouten
- configuratie wordt op één centrale plek geladen
- bestaande endpointnamen blijven behouden
- bestaande flow blijft intact
- imports zijn bijgewerkt
- circulaire imports zijn voorkomen

### ⚠️ STRIKTE RESTRICTIES
- geen nieuwe frameworks tenzij expliciet gevraagd
- geen async refactor tenzij expliciet gevraagd
- geen infra zoals Docker, CI of uitgebreide logging
- geen aanpassing van businesslogica buiten de gevraagde scope

---

**Wacht op mijn "Go" voordat je FASE 2 start.**
