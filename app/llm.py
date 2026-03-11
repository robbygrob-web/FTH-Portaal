"""
Centrale LiteLLM helper voor uniforme model calls met JSON veiligheidslaag.
"""
import json
import logging
from typing import Optional, Dict, Any, List
from litellm import completion
from app.config import get_llm_config

_LOG = logging.getLogger(__name__)

# String constants voor agent status (geen Enum)
ROUTER_STATUS_READY = "READY_FOR_VERIFICATION"
ROUTER_STATUS_CLARIFY = "NEEDS_CLARIFICATION"
BUILDER_STATUS_READY = "PROPOSAL_READY"
REVIEWER_STATUS_GOED = "GOED"
REVIEWER_STATUS_AANPASSEN = "AANPASSEN"
REVIEWER_STATUS_BLOKKEREN = "BLOKKEREN"

# String constants voor user actions (geen Enum)
USER_ACTION_CONFIRM = "CONFIRM"
USER_ACTION_ADJUST = "ADJUST"
USER_ACTION_STOP = "STOP"

def safe_parse_json(content: str, max_retries: int = 1) -> Dict[str, Any]:
    """
    Parse JSON veilig met max 1 retry bij invalid JSON.
    
    Args:
        content: JSON string om te parsen
        max_retries: Maximum aantal retries (default 1)
    
    Returns:
        Parsed JSON dict
    
    Raises:
        ValueError: Als JSON niet geparsed kan worden na retries
    """
    for attempt in range(max_retries + 1):
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                _LOG.warning(f"JSON parse error (poging {attempt + 1}/{max_retries + 1}): {e}")
                # Probeer eventuele markdown code blocks te verwijderen
                content = content.strip()
                if content.startswith("```"):
                    # Verwijder markdown code blocks
                    lines = content.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    content = "\n".join(lines)
                continue
            else:
                _LOG.error(f"JSON parse error na {max_retries + 1} pogingen: {e}, content: {content[:200]}")
                raise ValueError(f"LLM response is geen geldig JSON na {max_retries + 1} pogingen: {e}")

def validate_required_fields(parsed_json: Dict[str, Any], required_fields: List[str]) -> None:
    """
    Valideer dat alle required fields aanwezig zijn in parsed JSON.
    
    Args:
        parsed_json: Parsed JSON dict
        required_fields: Lijst van verplichte velden
    
    Raises:
        ValueError: Als verplichte velden ontbreken
    """
    if not required_fields:
        return
    
    missing = [field for field in required_fields if field not in parsed_json]
    if missing:
        raise ValueError(f"Ontbrekende verplichte velden: {missing}")

def call_llm_json(
    messages: List[Dict[str, str]],
    agent_type: str = "default",
    required_fields: List[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Centrale functie voor LLM calls via LiteLLM met JSON output validatie en veiligheidslaag.
    
    Args:
        messages: List van message dicts met 'role' en 'content'
        agent_type: "router", "builder", "reviewer" voor model selectie
        required_fields: Lijst van verplichte velden in JSON response
        model: Optioneel model override
        temperature: Optioneel temperature override
        max_tokens: Optioneel max_tokens override
        **kwargs: Extra parameters voor LiteLLM
    
    Returns:
        Dict met parsed JSON content, 'usage', 'model_used'
    
    Raises:
        ValueError: Als API key ontbreekt of JSON invalid is
        Exception: Bij LLM call fouten
    """
    config = get_llm_config(agent_type)
    
    if not config["api_key"]:
        raise ValueError("LITELLM_API_KEY of OPENAI_API_KEY vereist")
    
    # Merge config met overrides
    final_model = model or config["model"]
    final_temperature = temperature if temperature is not None else config["temperature"]
    final_max_tokens = max_tokens or config["max_tokens"]
    
    try:
        # Force JSON response via response_format
        response = completion(
            model=final_model,
            messages=messages,
            temperature=final_temperature,
            max_tokens=final_max_tokens,
            api_key=config["api_key"],
            response_format={"type": "json_object"},  # Force JSON
            **kwargs
        )
        
        content = response.choices[0].message.content
        usage = response.usage.dict() if hasattr(response.usage, 'dict') else {}
        
        # Parse JSON met veiligheidslaag (max 1 retry)
        parsed_json = safe_parse_json(content, max_retries=1)
        
        # Valideer required fields
        validate_required_fields(parsed_json, required_fields)
        
        _LOG.info(f"LLM call succesvol: agent={agent_type}, model={final_model}, tokens={usage.get('total_tokens', 'N/A')}")
        
        return {
            "content": parsed_json,  # Parsed JSON, niet raw string
            "usage": usage,
            "model_used": final_model
        }
        
    except Exception as e:
        _LOG.error(f"LLM call gefaald (agent={agent_type}): {e}")
        raise
