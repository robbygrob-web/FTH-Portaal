"""
Chat API routes voor Rob's chatbot interface.
Minimale implementatie: router → agent → reply.
"""
import os
import logging
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.router import route_message, NEXT_STEP_BUILDER, NEXT_STEP_REVIEWER
from app.llm import call_llm_json

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Hardcoded fallback agent configs (als DB record ontbreekt)
FALLBACK_AGENTS = {
    "Communicatie": {
        "naam": "Communicatie",
        "model": "gpt-4o-mini",
        "prompt": "Je bent de Communicatie agent binnen het FTH portaal. Je helpt Rob met communicatie-gerelateerde taken. Antwoord altijd in JSON met een 'reply' veld.",
        "temperatuur": 0.7
    },
    "Controleur": {
        "naam": "Controleur",
        "model": "gpt-4o-mini",
        "prompt": "Je bent de Controleur agent binnen het FTH portaal. Je helpt Rob met controle- en review-taken. Antwoord altijd in JSON met een 'reply' veld.",
        "temperatuur": 0.7
    },
    "Bouwbot": {
        "naam": "Bouwbot",
        "model": "gpt-4o-mini",
        "prompt": """Je bent Bouwbot, een interne build-assistant voor het FTH portaal.
Je helpt Rob met het bouwen van het platform, niet met klantoperaties.

Context: FastAPI + PostgreSQL + Railway + Gmail API. Focus op stap-voor-stap vervangen van Odoo functionaliteit.

Antwoord altijd in JSON met een 'reply' veld. De reply moet deze structuur volgen:

Modus:
[build_plan / cursor_prompt / patch_review / bug_fix_plan / flow_design]

Doel:
[kort]

Voorstel:
[1 kleine stap]

Waarom deze stap eerst:
[kort]

Risico / aandachtspunt:
[kort]

Bevestigingsvraag:
[wat wil je dat ik nu doe?]

Regels:
- Houd scope klein
- Vraag altijd om bevestiging voordat je naar de volgende build-stap gaat
- Vermijd scope creep
- Geef voorkeur aan minimale veilige wijzigingen
- Ga er niet vanuit dat code-wijzigingen direct moeten gebeuren
- Denk praktisch en beheerst""",
        "temperatuur": 0.7
    }
}

def get_database_url():
    """Haal DATABASE_URL op uit environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL niet gevonden in environment variabelen")
    return database_url

def get_agent_config(agent_name: str) -> Optional[Dict[str, Any]]:
    """
    Haal agent configuratie op uit agents table.
    
    Args:
        agent_name: Naam van de agent (exact match, case-sensitive)
    
    Returns:
        Dict met naam, model, prompt, temperatuur of None als niet gevonden
    """
    try:
        database_url = get_database_url()
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            "SELECT naam, model, prompt, temperatuur FROM agents WHERE actief = TRUE AND naam = %s LIMIT 1",
            (agent_name,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            return dict(result)
        return None
        
    except Exception as e:
        _LOG.warning(f"Fout bij ophalen agent config uit DB voor {agent_name}: {e}")
        return None

def run_agent(agent_config: Dict[str, Any], message: str) -> Dict[str, Any]:
    """
    Voer een agent uit met gegeven configuratie en bericht.
    
    Args:
        agent_config: Dict met naam, model, prompt, temperatuur
        message: Het bericht voor de agent
    
    Returns:
        Dict met parsed JSON content + usage info van LLM call
        Content bevat: reply
    """
    messages = [
        {"role": "system", "content": agent_config["prompt"]},
        {"role": "user", "content": message}
    ]
    
    result = call_llm_json(
        messages=messages,
        agent_type="default",
        required_fields=["reply"],
        model=agent_config["model"],
        temperature=float(agent_config["temperatuur"]),
        max_tokens=1000
    )
    
    return result

class ChatRequest(BaseModel):
    message: str
    agent_name: Optional[str] = None  # Optioneel: forceer specifieke agent (voor testing)

class ChatResponse(BaseModel):
    session_id: str
    router: Dict[str, Any]
    agent_name: Optional[str] = None
    agent_reply: Optional[str] = None
    agent_meta: Optional[Dict[str, Any]] = None

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint: router bepaalt richting, agent genereert antwoord.
    
    Flow:
    1. Router classificeert bericht
    2. Map router next_step naar agent naam
    3. Laad agent config (DB → fallback)
    4. Voer agent uit
    5. Return router + agent resultaat
    """
    session_id = str(uuid.uuid4())
    
    try:
        # Test mode: als agent_name expliciet is opgegeven, gebruik die direct
        if request.agent_name:
            agent_name = request.agent_name
            router_content = {
                "intent": "test_mode",
                "scope": "direct_agent_selection",
                "input_summary": request.message[:100],
                "next_step": "builder"
            }
        else:
            # Stap 1: Router classificeert bericht
            router_result = route_message(request.message)
            router_content = router_result["content"]
            next_step = router_content.get("next_step")
            
            # Stap 2: Map next_step naar agent naam
            agent_name = None
            if next_step == NEXT_STEP_BUILDER:
                agent_name = "Communicatie"
            elif next_step == NEXT_STEP_REVIEWER:
                agent_name = "Controleur"
            # else: user_action of complete → geen agent call
        
        agent_reply = None
        agent_meta = None
        
        # Stap 3 & 4: Laad agent config en voer uit (alleen als agent nodig)
        if agent_name:
            # Laad config (DB → fallback)
            agent_config = get_agent_config(agent_name)
            if not agent_config:
                _LOG.info(f"Agent {agent_name} niet gevonden in DB, gebruik fallback")
                agent_config = FALLBACK_AGENTS.get(agent_name)
            
            if agent_config:
                # Voer agent uit
                agent_result = run_agent(agent_config, request.message)
                agent_reply = agent_result["content"].get("reply", "")
                agent_meta = {
                    "model_used": agent_result["model_used"],
                    "tokens": agent_result["usage"].get("total_tokens", 0)
                }
            else:
                agent_reply = f"Agent '{agent_name}' niet beschikbaar (geen config gevonden)."
        else:
            # Geen agent nodig (user_action of complete)
            if next_step == "user_action":
                agent_reply = "Ik heb je bericht ontvangen. Kun je dit verduidelijken?"
            elif next_step == "complete":
                agent_reply = "Taak voltooid. Is er nog iets anders?"
            else:
                agent_reply = "Geen actie nodig."
        
        return ChatResponse(
            session_id=session_id,
            router={
                "intent": router_content.get("intent"),
                "scope": router_content.get("scope"),
                "input_summary": router_content.get("input_summary"),
                "next_step": router_content.get("next_step")
            },
            agent_name=agent_name,
            agent_reply=agent_reply,
            agent_meta=agent_meta
        )
        
    except Exception as e:
        _LOG.error(f"Chat endpoint fout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fout bij verwerken van chat bericht: {str(e)}")
