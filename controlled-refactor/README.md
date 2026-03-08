# Controlled Refactor Skill

Een Cursor Skill voor gecontroleerde code-refactors met een twee-fasen aanpak: eerst analyse, dan pas uitvoering na expliciete toestemming.

## Structuur

```
controlled-refactor/
├── skill.md                    # Hoofd skill definitie
├── .cursorrules               # Cursor rules voor refactor gedrag
├── references/
│   └── refactor-prompt.md     # Herbruikbare refactor prompt template
└── README.md                  # Deze documentatie
```

## Gebruik

1. Activeer deze Skill wanneer je een refactor wilt uitvoeren
2. De Skill werkt automatisch in twee fasen:
   - **FASE 1**: Analyse (wacht op toestemming)
   - **FASE 2**: Uitvoering (na "Go")

## Bestanden

- **`skill.md`**: Hoofddefinitie van de Skill met werkwijze en restricties
- **`.cursorrules`**: Regels die automatisch worden toegepast tijdens refactors
- **`references/refactor-prompt.md`**: Template prompt die je kunt gebruiken voor refactor requests

## Doelgroep

- Python/FastAPI-projecten
- Odoo/XML-RPC-achtige projecten
- Backend-refactors waarbij structuur belangrijk is

## Installatie

Pak de `skill.zip` uit in je Cursor Skills directory of importeer via Cursor's Skill management interface.
