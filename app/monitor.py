"""
Passieve Monitor / Trace logger voor FTH governance systeem.
Logt en vat samen, maar beslist niet.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

_LOG = logging.getLogger(__name__)

# Step constants (geen Enum)
STEP_ROUTER = "router"
STEP_BUILDER = "builder"
STEP_REVIEWER = "reviewer"
STEP_USER_ACTION = "user_action"
STEP_COMPLETE = "complete"

def log_step(
    session_id: str,
    step: str,
    agent_status: Optional[str],
    user_action: Optional[str],
    input_summary: str,
    output_summary: str,
    scope: str,
    next_step: Optional[str] = None,
    awaiting_user_verification: bool = False,
    agent_output: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Log een stap in de governance flow met agent status en user action.
    
    Passieve functie: logt alleen, beslist niet.
    
    Args:
        session_id: Unieke sessie ID
        step: Type stap (router, builder, reviewer, user_action, complete)
        agent_status: Agent status (READY_FOR_VERIFICATION, PROPOSAL_READY, GOED, etc.) of None
        user_action: User action (CONFIRM, ADJUST, STOP) of None
        input_summary: Korte samenvatting van input
        output_summary: Korte samenvatting van output
        scope: Scope van deze stap
        next_step: Volgende verwachte stap
        awaiting_user_verification: Of user verificatie nodig is
        agent_output: Optionele volledige agent output voor context
    
    Returns:
        Dict met log entry details
    """
    log_entry = {
        "session_id": session_id,
        "step": step,
        "agent_status": agent_status,
        "user_action": user_action,
        "timestamp": datetime.now().isoformat(),
        "input_summary": input_summary,
        "output_summary": output_summary,
        "scope": scope,
        "next_step": next_step,
        "awaiting_user_verification": awaiting_user_verification
    }
    
    # Log naar Python logger (passief, geen beslissingen)
    status_str = f"Agent: {agent_status}" if agent_status else ""
    action_str = f"User: {user_action}" if user_action else ""
    _LOG.info(f"[MONITOR] Session {session_id} - Step {step} - {status_str} {action_str}")
    _LOG.debug(f"[MONITOR] Input: {input_summary[:100]}...")
    _LOG.debug(f"[MONITOR] Output: {output_summary[:100]}...")
    
    return log_entry

def summarize_session(session_id: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Vat een sessie samen (passief, geen beslissingen).
    
    Args:
        session_id: Unieke sessie ID
        steps: Lijst van log entries (zoals geretourneerd door log_step)
    
    Returns:
        Dict met samenvatting inclusief agent status en user actions
    """
    if not steps:
        return {
            "session_id": session_id,
            "summary": "Geen stappen gelogd",
            "total_steps": 0
        }
    
    completed_steps = [s for s in steps if s.get("awaiting_user_verification") == False]
    awaiting_verification = [s for s in steps if s.get("awaiting_user_verification")]
    user_actions = [s for s in steps if s.get("user_action")]
    
    summary = {
        "session_id": session_id,
        "total_steps": len(steps),
        "completed_steps": len(completed_steps),
        "awaiting_verification": len(awaiting_verification),
        "user_actions_count": len(user_actions),
        "current_step": steps[-1].get("step") if steps else None,
        "current_agent_status": steps[-1].get("agent_status") if steps else None,
        "last_user_action": steps[-1].get("user_action") if steps else None,
        "scope": steps[-1].get("scope") if steps else None
    }
    
    _LOG.info(f"[MONITOR] Session {session_id} samenvatting: {summary}")
    
    return summary
