from typing import Dict, Any, Protocol
from .models import ActionProposal, PolicyDecision, DecisionStatus, ActionType

class PolicyRule(Protocol):
    async def evaluate(self, proposal: ActionProposal, context: Dict[str, Any]) -> PolicyDecision:
        """
        Evaluate the proposal given contextual data.
        Returns a PolicyDecision (allow/deny, reason, adjustment).
        """
        ...

class RestrictedUserExternalEmailRule:
    """Blocks sending external emails if the user role is restricted."""
    async def evaluate(self, proposal: ActionProposal, context: Dict[str, Any]) -> PolicyDecision:
        if proposal.action_type == ActionType.SEND_EMAIL:
            user_role = context.get("user_role")
            if user_role == "restricted":
                return PolicyDecision(
                    status=DecisionStatus.DENY,
                    reason="Cannot send external email for restricted user role",
                    confidence_adjustment=0.0
                )
        return PolicyDecision(status=DecisionStatus.ALLOW, reason="")

class LegalSensitiveEscalationRule:
    """Blocks automatic escalation of legally sensitive tickets."""
    async def evaluate(self, proposal: ActionProposal, context: Dict[str, Any]) -> PolicyDecision:
        if proposal.action_type == ActionType.ESCALATE:
            if context.get("is_legal_sensitive", False):
                return PolicyDecision(
                    status=DecisionStatus.DENY,
                    reason="Cannot automatically escalate legally sensitive tickets",
                    confidence_adjustment=0.0
                )
        return PolicyDecision(status=DecisionStatus.ALLOW, reason="")

class RiskyAccountAdjustmentRule:
    """Lowers confidence if context flags the account as new or risky."""
    async def evaluate(self, proposal: ActionProposal, context: Dict[str, Any]) -> PolicyDecision:
        if context.get("is_new_account", False):
            return PolicyDecision(
                status=DecisionStatus.ALLOW, 
                reason="Context flagged as new account. Lowering confidence parameter.",
                confidence_adjustment=-0.2 # Applies a penalty to the AI's confidence
            )
        return PolicyDecision(status=DecisionStatus.ALLOW, reason="")
