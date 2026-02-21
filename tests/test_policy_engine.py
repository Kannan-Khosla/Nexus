import unittest
from policy_engine.models import ActionProposal, ActionType, DecisionStatus
from policy_engine.engine import PolicyEngine
from policy_engine.rules import (
    RestrictedUserExternalEmailRule,
    LegalSensitiveEscalationRule,
    RiskyAccountAdjustmentRule
)

class TestPolicyEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = PolicyEngine(auto_resolve_threshold=0.85)
        self.engine.add_rule(RestrictedUserExternalEmailRule())
        self.engine.add_rule(LegalSensitiveEscalationRule())
        self.engine.add_rule(RiskyAccountAdjustmentRule())

    # 1. Test Confidence Below Threshold (Hard Deny)
    async def test_confidence_below_threshold(self):
        proposal = ActionProposal(
            action_type=ActionType.AUTO_RESOLVE,
            target_id="ticket_1",
            confidence_score=0.80 # Below 0.85 threshold
        )
        decision = await self.engine.evaluate(proposal, context={})
        
        self.assertEqual(decision.status, DecisionStatus.DENY)
        self.assertIn("below auto-resolve threshold", decision.reason)

    # 2. Test Confidence Adjustment Drops Below Threshold (Soft Deny)
    async def test_confidence_adjustment_drops_below_threshold(self):
        proposal = ActionProposal(
            action_type=ActionType.AUTO_RESOLVE,
            target_id="ticket_2",
            confidence_score=0.90 # Initially above threshold
        )
        context = {"is_new_account": True} # Triggers -0.2 penalty -> 0.70 final
        
        decision = await self.engine.evaluate(proposal, context)
        
        self.assertEqual(decision.status, DecisionStatus.DENY)
        self.assertEqual(decision.confidence_adjustment, -0.2)
        self.assertIn("below auto-resolve threshold", decision.reason)

    # 3. Test Restricted Role (Hard Deny)
    async def test_restricted_user_email_deny(self):
        proposal = ActionProposal(
            action_type=ActionType.SEND_EMAIL,
            target_id="ticket_3",
            confidence_score=0.99
        )
        context = {"user_role": "restricted"}
        
        decision = await self.engine.evaluate(proposal, context)
        
        self.assertEqual(decision.status, DecisionStatus.DENY)
        self.assertIn("restricted user role", decision.reason)

    # 4. Test Legal Sensitive Escalation (Hard Deny)
    async def test_legal_sensitive_escalation_deny(self):
        proposal = ActionProposal(
            action_type=ActionType.ESCALATE,
            target_id="ticket_4",
            confidence_score=0.95
        )
        context = {"is_legal_sensitive": True}
        
        decision = await self.engine.evaluate(proposal, context)
        
        self.assertEqual(decision.status, DecisionStatus.DENY)
        self.assertIn("legally sensitive", decision.reason)

    # 5. Test Valid Action Passes (Happy Path)
    async def test_allow_when_all_pass(self):
        proposal = ActionProposal(
            action_type=ActionType.SEND_EMAIL,
            target_id="ticket_5",
            confidence_score=0.95
        )
        context = {"user_role": "regular", "is_legal_sensitive": False}
        
        decision = await self.engine.evaluate(proposal, context)
        
        self.assertEqual(decision.status, DecisionStatus.ALLOW)
        self.assertEqual(decision.confidence_adjustment, 0.0)
        self.assertIn("All policies passed", decision.reason)

    # 6. Test Valid Action Passes with Minor Penalty (Happy Path + Soft Penalty)
    async def test_allow_with_minor_penalty(self):
        proposal = ActionProposal(
            action_type=ActionType.AUTO_RESOLVE,
            target_id="ticket_6",
            confidence_score=0.99
        )
        context = {"is_new_account": True} # Triggers -0.2 penalty -> 0.79 final
        
        # We need a custom engine here to test a lower threshold, so it passes
        custom_engine = PolicyEngine(auto_resolve_threshold=0.75)
        custom_engine.add_rule(RiskyAccountAdjustmentRule())
        
        decision = await custom_engine.evaluate(proposal, context)
        
        self.assertEqual(decision.status, DecisionStatus.ALLOW)
        self.assertEqual(decision.confidence_adjustment, -0.2)
        self.assertIn("All policies passed", decision.reason)

if __name__ == '__main__':
    unittest.main()
