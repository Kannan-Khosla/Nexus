# Policy Engine Test Guide

This document explains the core `PolicyEngine` tests, what they check, and how to debug them if they fail.

## Test Cases in `test_policy_engine.py`

### 1. `test_confidence_below_threshold`
**What it does:** Tests the core engine logic to reject AI auto-resolves if the AI's native confidence score is intrinsically too low.
* **Input Proposal:** `action_type="auto_resolve"`, `confidence_score=0.80`, Context = `None`
* **Expected Result:** `DecisionStatus.DENY`
* **Why it fails if broken:** Meaning the `auto_resolve_threshold` (default `0.85`) is not being enforced by `engine.py` during `ActionType.AUTO_RESOLVE` intent checks.

### 2. `test_confidence_adjustment_drops_below_threshold`
**What it does:** Tests the "Soft Penalty" mechanic. The AI is highly confident (0.90), but the context flags the user as risky (`is_new_account=True`), which triggers a `-0.20` confidence penalty across the ruleset. Final confidence becomes `0.70`, which fails the baseline `0.85` check.
* **Input Proposal:** `action_type="auto_resolve"`, `confidence_score=0.90` 
* **Input Context:** `{"is_new_account": True}` 
* **Expected Result:** `DecisionStatus.DENY` with `confidence_adjustment = -0.2`
* **Why it fails if broken:** Meaning `RiskyAccountAdjustmentRule` is not passing back the modifier, or `engine.py` is failing to sum `total_adjustment` properly before doing the threshold check.

### 3. `test_restricted_user_email_deny`
**What it does:** Tests a "Hard Reject" scenario where external emails are blocked based on database context (RBAC/Roles).
* **Input Proposal:** `action_type="send_email"`, `confidence_score=0.99`
* **Input Context:** `{"user_role": "restricted"}`
* **Expected Result:** `DecisionStatus.DENY`
* **Why it fails if broken:** Meaning `RestrictedUserExternalEmailRule` isn't checking the `context.get("user_role")` correctly, or `engine.py` failed to short-circuit the loop on the first `DENY`.

### 4. `test_legal_sensitive_escalation_deny`
**What it does:** Tests a "Hard Reject" scenario involving sensitive ticket tags. Agents cannot unilaterally escalate things marked as legally sensitive.
* **Input Proposal:** `action_type="escalate"`, `confidence_score=0.95`
* **Input Context:** `{"is_legal_sensitive": True}`
* **Expected Result:** `DecisionStatus.DENY`
* **Why it fails if broken:** Meaning `LegalSensitiveEscalationRule` is bypassing the context flag, acting as a false negative.

### 5. `test_allow_when_all_pass`
**What it does:** The primary Happy Path. A normal user, a normal ticket, a high confidence score.
* **Input Proposal:** `action_type="send_email"`, `confidence_score=0.95`
* **Input Context:** `{"user_role": "regular", "is_legal_sensitive": False}`
* **Expected Result:** `DecisionStatus.ALLOW` with `confidence_adjustment = 0.0`
* **Why it fails if broken:** Meaning one of the rules (like the restricted user rule) has a logic bug and is firing a false positive `DENY`.

### 6. `test_allow_with_minor_penalty`
**What it does:** The Secondary Happy Path. Tests if the engine *allows* an action even when a penalty was applied, provided the final score still beats the threshold. (In this test, the baseline threshold is artificially lowered to `0.75` for testing purposes). The AI's 0.99 score drops to 0.79, so it survives.
* **Input Proposal:** `action_type="auto_resolve"`, `confidence_score=0.99`
* **Input Context:** `{"is_new_account": True}` 
* **Expected Result:** `DecisionStatus.ALLOW`
* **Why it fails if broken:** Meaning `engine.py` is miscalculating `max(0.0, min(1.0, proposal.confidence_score + total_adjustment))` or treating every penalty as a hard denial.
