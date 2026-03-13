import os
from dotenv import load_dotenv

load_dotenv()

from app.router import route_message

# Test verschillende berichten
test_messages = [
    "Ik wil een nieuwe feature toevoegen voor order tracking",
    "Review de code in app/routes.py",
    "Kun je uitleggen hoe de mail functie werkt?",
    "Stop de huidige workflow"
]

for i, message in enumerate(test_messages, 1):
    print(f"\n{'='*60}")
    print(f"Test {i}: {message}")
    print('='*60)

    try:
        result = route_message(message)

        print("✓ Router call succesvol")
        print(f"Model: {result['model_used']}")
        print(f"Tokens: {result['usage'].get('total_tokens', 'N/A')}")

        content = result["content"]

        print("\nOutput:")
        print(f"  Intent: {content.get('intent')}")
        print(f"  Scope: {content.get('scope')}")
        print(f"  Input summary: {content.get('input_summary')}")
        print(f"  Next step: {content.get('next_step')}")

    except Exception as e:
        print(f"✗ Fout: {e}")
