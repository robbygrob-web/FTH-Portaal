import os
from dotenv import load_dotenv

load_dotenv()

from app.llm import call_llm_json

messages = [
    {"role": "system", "content": "Je geeft altijd JSON terug."},
    {"role": "user", "content": "Geef een JSON object met velden: naam en status"}
]

try:
    result = call_llm_json(
        messages=messages,
        agent_type="default",
        required_fields=["naam", "status"]
    )

    print("✓ LLM call succesvol")
    print("Model:", result["model_used"])
    print("Tokens:", result["usage"].get("total_tokens"))
    print("Output:", result["content"])

except Exception as e:
    print("✗ Fout tijdens LLM test:")
    print(e)
