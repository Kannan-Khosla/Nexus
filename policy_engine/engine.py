from typing import List, Dict, Any
from .models import ActionProposal, PolicyDecision, DecisionStatus, ActionType
from .rules import PolicyRule

class PolicyEngine:
    def __init__(self, rules: List[PolicyRule] = None, auto_resolve_threshold: float = 0.85):
        """
        Initialize the policy engine with a set of modular rules and an 
        auto-resolve base threshold.
        """
        self.rules = rules or []
        self.auto_resolve_threshold = auto_resolve_threshold

    def add_rule(self, rule: PolicyRule):
        self.rules.append(rule)

    async def evaluate(self, proposal: ActionProposal, context: Dict[str, Any]) -> PolicyDecision:
        """
        Evaluate an ActionProposal against all registered rules, incorporating contextual data.
        Returns ALLOW or DENY, along with reasoning and cumulative confidence adjustment.
        """
        total_adjustment = 0.0
        reasons = []

        for rule in self.rules:
            decision = await rule.evaluate(proposal, context)
            
            if decision.status == DecisionStatus.DENY:
                # Immediate short-circuit on hard deny
                return PolicyDecision(
                    status=DecisionStatus.DENY,
                    reason=f"Denied by rule: {decision.reason}",
                    confidence_adjustment=total_adjustment + decision.confidence_adjustment
                )
            
            # Accumulate soft adjustments
            total_adjustment += decision.confidence_adjustment
            if decision.reason:
                reasons.append(decision.reason)

        # Calculate final adjusted confidence bounds bounded between 0.0 and 1.0
        final_confidence = max(0.0, min(1.0, proposal.confidence_score + total_adjustment))

        # Built-in core threshold check for auto-resolves
        if proposal.action_type == ActionType.AUTO_RESOLVE and final_confidence < self.auto_resolve_threshold:
            return PolicyDecision(
                status=DecisionStatus.DENY,
                reason=f"Final confidence {final_confidence:.2f} is below auto-resolve threshold {self.auto_resolve_threshold}.",
                confidence_adjustment=total_adjustment
            )

        # Approved
        reason_str = "All policies passed."
        if reasons:
            reason_str += " Notes: " + "; ".join(reasons)

        return PolicyDecision(
            status=DecisionStatus.ALLOW,
            reason=reason_str.strip(),
            confidence_adjustment=total_adjustment
        )
