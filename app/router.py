"""
Router agent: classificeert berichten en bepaalt volgende stap in workflow.
"""
from typing import Dict, Any
from app.llm import call_llm_json

# Toegestane next_step waarden
NEXT_STEP_BUILDER = "builder"
NEXT_STEP_REVIEWER = "reviewer"
NEXT_STEP_USER_ACTION = "user_action"
NEXT_STEP_COMPLETE = "complete"

# Required fields voor router output
ROUTER_REQUIRED_FIELDS = [
    "intent",
    "scope",
    "input_summary",
    "next_step"
]

ROUTER_SYSTEM_PROMPT = """Je bent een router agent.
Analyseer het bericht en bepaal intent, scope, korte samenvatting en de volgende stap in de workflow.
Antwoord uitsluitend in JSON met exact deze velden:
- intent: de intentie van het bericht
- scope: de scope van de taak
- input_summary: een korte samenvatting van de input
- next_step: één van deze waarden: "builder", "reviewer", "user_action", "complete"
"""

def route_message(message: str) -> Dict[str, Any]:
    """
    Route een bericht door het classificeren van intent en bepalen van volgende stap.
    
    Args:
        message: Het bericht om te routeren
    
    Returns:
        Dict met parsed JSON content + usage info van LLM call
        Content bevat: intent, scope, input_summary, next_step
    
    Raises:
        ValueError: Als LLM response geen geldig JSON is of verplichte velden ontbreken
        Exception: Bij LLM call fouten
    """
    messages = [
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
        {"role": "user", "content": message}
    ]
    
    result = call_llm_json(
        messages=messages,
        agent_type="router",
        required_fields=ROUTER_REQUIRED_FIELDS,
        max_tokens=500
    )
    
    content = result["content"]
    
    # Normalisatie: map summary -> input_summary als input_summary ontbreekt
    if "summary" in content and "input_summary" not in content:
        content["input_summary"] = content["summary"]
    
    # Valideer en normaliseer next_step
    next_step = content.get("next_step")
    allowed_steps = [
        NEXT_STEP_BUILDER,
        NEXT_STEP_REVIEWER,
        NEXT_STEP_USER_ACTION,
        NEXT_STEP_COMPLETE
    ]
    
    if next_step not in allowed_steps:
        # Veilige fallback: default naar user_action
        content["next_step"] = NEXT_STEP_USER_ACTION
    
    return result
