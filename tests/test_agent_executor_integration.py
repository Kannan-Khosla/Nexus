import unittest
from unittest.mock import patch, MagicMock
from policy_engine.models import ActionType
import agent_executor

class TestAgentExecutorIntegration(unittest.TestCase):

    @patch("agent_executor.supabase")
    def test_run_agent_action_denied(self, mock_supabase):
        """
        Integration test simulating an agent proposing an action that violates policy.
        Verifies:
        1. Policy blocks the action.
        2. Audit log creation is attempted.
        3. Execution flag (is_allowed) is False, preventing downstream execution.
        """
        # Set up a mock for the supabase table insertion
        mock_audit_table = MagicMock()
        mock_supabase.table.return_value = mock_audit_table
        
        # Scenario: Agent wants to send an email, but context says the user is "restricted"
        action_type = ActionType.SEND_EMAIL
        target_id = "test_ticket_123"
        confidence_score = 0.95
        payload = {"message": "Here is your refund data.", "secret_key": "hidden"}
        context = {"user_role": "restricted"} # This should trigger the RestrictedUserExternalEmailRule

        # Simulate the orchestrator running the pipeline
        is_allowed, reason, modified_payload = agent_executor.run_agent_action(
            action_type=action_type,
            target_id=target_id,
            confidence_score=confidence_score,
            payload=payload,
            context=context
        )

        # 1. Verify policy blocks correctly
        self.assertFalse(is_allowed, "Policy engine should have denied the action for a restricted user.")
        self.assertIn("restricted user role", reason)

        # 2. Verify audit log creation was attempted exactly once
        mock_supabase.table.assert_called_with("agent_audit_logs")
        mock_audit_table.insert.assert_called_once()
        
        # Verify the audit log payload specifically stripped out the sensitive "message" string
        # as part of our Data Minimization design
        inserted_data = mock_audit_table.insert.call_args[0][0]
        self.assertEqual(inserted_data["action_type"], "send_email")
        self.assertEqual(inserted_data["target_id"], "test_ticket_123")
        self.assertEqual(inserted_data["status"], "deny")
        self.assertNotIn("message", inserted_data["payload"], "Sensitive message payload should not be logged.")
        self.assertIn("secret_key", inserted_data["payload"], "Other safe payload parts should be logged.")

        # 3. Execution NOT called - Prove that orchestrator correctly returns False
        # In main.py, execution only happens if `is_allowed` is True.
        self.assertFalse(is_allowed)

    @patch("agent_executor.supabase")
    def test_run_agent_action_approved(self, mock_supabase):
        """
        Integration test simulating an agent proposing a valid action.
        Verifies:
        1. Policy approves the action.
        2. Audit log creation is attempted (status=allow).
        3. Execution flag (is_allowed) is True.
        """
        mock_audit_table = MagicMock()
        mock_supabase.table.return_value = mock_audit_table
        
        # Scenario: Valid user, valid action
        action_type = ActionType.AUTO_REPLY
        target_id = "test_ticket_456"
        confidence_score = 0.99
        payload = {"message": "Hello, how can I help?"}
        context = {"user_role": "regular"}

        is_allowed, reason, modified_payload = agent_executor.run_agent_action(
            action_type=action_type,
            target_id=target_id,
            confidence_score=confidence_score,
            payload=payload,
            context=context
        )

        # 1. Verify policy allows correctly
        self.assertTrue(is_allowed)
        
        # 2. Verify audit log creation
        mock_audit_table.insert.assert_called_once()
        inserted_data = mock_audit_table.insert.call_args[0][0]
        self.assertEqual(inserted_data["status"], "allow")
        
        # 3. Execution flag is True
        self.assertTrue(is_allowed)

    @patch("agent_executor.supabase")
    @patch("agent_executor.engine.evaluate")
    def test_run_agent_action_fails_closed_on_crash(self, mock_evaluate, mock_supabase):
        """
        Integration test verifying 'Fail Closed' behavior.
        If the policy engine crashes or throws an exception, the system must 
        default to DENY to prevent unapproved AI actions.
        """
        mock_audit_table = MagicMock()
        mock_supabase.table.return_value = mock_audit_table
        
        # Simulate a crash in the policy engine (e.g. database disconnect during context fetch)
        mock_evaluate.side_effect = Exception("Simulated Database Timeout")

        is_allowed, reason, modified_payload = agent_executor.run_agent_action(
            action_type=ActionType.AUTO_REPLY,
            target_id="test_ticket_789",
            confidence_score=0.99,
            payload={"message": "I will refund you now."},
            context={}
        )

        # 1. Verify we FAILED CLOSED
        self.assertFalse(is_allowed, "System failed to FAIL CLOSED on engine crash.")
        self.assertIn("Policy engine error (Fail Closed)", reason)
        self.assertNotIn("Simulated Database Timeout", reason, "Raw stack trace strings should not be exposed externally.")
        
        # 2. Verify audit log creation attempts to log the crash
        mock_audit_table.insert.assert_called_once()
        inserted_data = mock_audit_table.insert.call_args[0][0]
        self.assertEqual(inserted_data["status"], "deny")

if __name__ == '__main__':
    unittest.main()
