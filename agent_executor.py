import asyncio
from datetime import datetime, timezone
import logging
from policy_engine.models import ActionProposal, ActionType, DecisionStatus
from policy_engine.engine import PolicyEngine
from policy_engine.rules import (
    RestrictedUserExternalEmailRule,
    LegalSensitiveEscalationRule,
    RiskyAccountAdjustmentRule
)
try:
    from supabase_config import supabase
except ImportError:
    supabase = None

logger = logging.getLogger(__name__)

# Initialize the global policy engine
engine = PolicyEngine(auto_resolve_threshold=0.85)
engine.add_rule(RestrictedUserExternalEmailRule())
engine.add_rule(LegalSensitiveEscalationRule())
engine.add_rule(RiskyAccountAdjustmentRule())

def run_agent_action(
    action_type: ActionType,
    target_id: str,
    confidence_score: float,
    payload: dict,
    context: dict
) -> tuple[bool, str, dict]:
    """
    Executes the Guardrail Pipeline: Proposal -> Policy Check -> Audit Log -> Return Decision.
    Since FastAPI endpoints in this codebase are generally synchronous, 
    we run the async evaluate via asyncio safely.
    
    Returns:
        (is_allowed, reason, modified_payload)
    """
    proposal = ActionProposal(
        action_type=action_type,
        target_id=target_id,
        confidence_score=confidence_score,
        payload=payload
    )
    
    # 1. Evaluate via Policy Engine
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        decision = loop.run_until_complete(engine.evaluate(proposal, context))
    except Exception as e:
        logger.error(f"CRITICAL: Policy Engine crashed while evaluating {action_type}. Failing CLOSED. Error: {e}", exc_info=True)
        from policy_engine.models import PolicyDecision
        # Fail Closed if the engine throws an unhandled exception
        # Do not expose `str(e)` in the reason, as it might leak internal trace details externally.
        decision = PolicyDecision(
            status=DecisionStatus.DENY,
            reason="Policy engine error (Fail Closed): Evaluation failed due to an internal error.",
            confidence_adjustment=-1.0
        )
    
    # 2. Record Audit Log
    try:
        if supabase:
            # We strip out PII from payload (Reference, Don't Copy pattern)
            safe_payload = {k: v for k, v in payload.items() if k not in ("reply_text", "email_body", "message")}
            
            supabase.table("agent_audit_logs").insert({
                "action_type": action_type.value,
                "target_id": target_id,
                "confidence_score": confidence_score,
                "payload": safe_payload, 
                "context": context,
                "status": decision.status.value,
                "reason": decision.reason,
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
    except Exception as e:
        logger.warning(f"Failed to record audit log (table might not exist yet): {e}")

    # 3. Return the decision Result
    if decision.status == DecisionStatus.ALLOW:
        return True, decision.reason, payload
    else:
        return False, decision.reason, payload
