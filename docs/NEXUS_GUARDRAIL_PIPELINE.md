# Nexus Guardrail Pipeline (Agent Execution Controller)

## 1. Overview and New Features
This branch introduces a robust "Action Guardrail Pipeline" for the Nexus AI Agent. Prior to this, the agent evaluated context and immediately executed actions (like sending an email or resolving a ticket) directly within the main API flow.

**New Features Added:**
- **Action Proposal System:** Nexus no longer acts autonomously. It *proposes* an `ActionProposal` containing an intended action, payload, and a native confidence score (0.0 to 1.0).
- **Policy Engine (The Bouncer):** A modular rule-based engine that evaluates proposals against contextual database states. It can issue a Hard `DENY` or apply soft **Confidence Penalties** (e.g., deducting 20% confidence if the user has a risky account).
- **Data Minimization Audit Logging:** Every AI intent (approved or denied) is logged to a new `agent_audit_logs` table. Crucially, it implements a "Reference, Don't Copy" pattern—stripping raw PII (like draft email bodies) from the logs before saving, radically reducing security and compliance risks.
- **Fail-Closed Execution Orchestrator:** If the Policy Engine crashes due to an internal error or database timeout, the execution layer instantly defaults to a hard `DENY`, preventing unverified AI actions from executing blindly.

## 2. Architecture & Migrations

### Architecture Separation of Concerns
The pipeline is cleanly separated into modular Python files within `policy_engine/`:

*   **`models.py`**: Defines the strict Pydantic schemas (`ActionProposal`, `PolicyDecision`, `ActionType`, `DecisionStatus`).
*   **`rules.py`**: Contains the modular business logic protocols (e.g., `ConfidenceThresholdRule`, `RestrictedUserExternalEmailRule`).
*   **`engine.py`**: The `PolicyEngine` coordinator class. It aggregates rule outputs and computes final adjusted confidence bounds.
*   **`agent_executor.py` (Controller):** Wires the engine to the existing FastAPI endpoints in `main.py`, managing the async loops, audit logging, and the ultimate `is_allowed` boolean return.

### Database Migration
A new migration script was drafted: **`migrations/017_agent_audit_logs.sql`**
*(Note: As per guardrails, this has not been executed yet).*

**Schema details:**
*   `id` (UUID), `action_type`, `target_id`
*   `confidence_score` (Numeric), `status` (allow/deny), `reason` (Text)
*   `payload` and `context` (JSONB)
*   **Performance Indexes:** Indexes on `status`, `target_id`, and `created_at` for rapid frontend analytics.
*   **Security:** Enforced Row Level Security (RLS) restricts read access to authenticated admins only.

---

## 3. Deep Review: Scope of Improvement

While the current setup is a massive leap forward for enterprise-grade autonomous systems, here are key areas for future iteration:

### Architecture Improvements
1.  **Fully Async Handlers:** `agent_executor.py` currently builds a custom `asyncio` event loop to bridge the gap between your synchronous FastAPI endpoints (`def create_or_continue_ticket`) and the async Policy Engine. **Improvement:** Refactor `main.py` endpoints to be `async def` and use a true async Supabase client.
2.  **Event-Driven Task Queue:** Currently, the LLM prompt generation and policy evaluation happen *synchronously inside the HTTP request lifecycle*. **Improvement:** Move the `run_agent_action` into a background worker (like Celery or FastAPI BackgroundTasks). The API should instantly return a 202 Accepted, while the worker thinks, evaluates policy, and saves the result to the DB.
3.  **Logger Abstraction:** The audit logger currently hardcodes Supabase insertion. **Improvement:** Abstract this behind an `AuditLogger` interface so you can securely multiplex logs to Datadog/Sentry or standard output files later.

### Codebase & Feature Improvements
1.  **Dynamic Thresholds:** The auto-resolve threshold is currently hardcoded at `0.85`. **Improvement:** Move this configuration into the database (`system_settings` table) so non-technical admins can dial the agent's strictness up or down via the frontend without deploying code.
2.  **Granular PII Masking:** We currently drop `message` properties entirely from the audit logs. **Improvement:** Integrate a lightweight NLP tool (like Microsoft Presidio) to automatically redact phone numbers and SSNs, allowing you to safely log the *structure* of the AI's intended drift without violating GDPR.
3.  **Dry-Run Mode:** **Improvement:** Add a `boolean action_mode="shadow"` to the Policy Engine. This allows deploying brand-new AI capabilities that *pretend* to execute (running through the engine and writing dummy logs) without actually sending emails to customers, letting you validate the model's accuracy safely.

---

## 4. Hidden Edge-Case Manual Testing Guide

I know you want to manually test this branch before merging. Here are the "hidden" or complex failure states you should verify, and how to trigger them.

### Test Case 1: The "Soft Penalty" Margin Failure
**Goal:** Prove the engine correctly adds context penalties that drag a normally passing AI score *under* the execution threshold.
*   **Setup:** In `main.py`, modify an endpoint to pass `confidence_score=0.90` and `context={"is_new_account": True}` into `run_agent_action()`.
*   **Expected Result:** Since `is_new_account` triggers a `-0.20` penalty in `RiskyAccountAdjustmentRule` (bringing the score to `0.70`, below the `0.85` threshold), the action must be **DENIED**.
*   **Verification:** Check the terminal logs for `"Final confidence 0.70 is below auto-resolve threshold 0.85."`

### Test Case 2: PII Data Minimization Check
**Goal:** Prove that sensitive message bodies aren't accidentally saved forever in your audit tables.
*   **Setup:** Make a standard customer request that forces the AI to draft a reply.
*   **Expected Result:** The action is APPROVED, but when you look at the JSON logged to `agent_audit_logs.payload`.
*   **Verification:** The `payload` dict must **NOT** contain the key `message` (e.g., `{"message": "I am so sorry..."}`). It should only contain safe identifiers.

### Test Case 3: The "Fail Closed" Integrity Check
**Goal:** Prove that if the database crashes or a developer writes a broken rule, the agent instantly stops executing requests instead of running amok.
*   **Setup:** Open `policy_engine/rules.py`. Inside `RestrictedUserExternalEmailRule`, purposely write a broken line of code (e.g., `1 / 0`). Trigger an AI action via the UI.
*   **Expected Result:** The system catches the `ZeroDivisionError`, logs a `CRITICAL` traceback internally, but returns a clean, safe `DENY` to the execution layer.
*   **Verification:** The final API response should be `{ "policy_denied": True, "reason": "Policy engine error (Fail Closed): Evaluation failed due to an internal error."}`. The execution step MUST NOT run.

### Test Case 4: The Multiple Rule Conflict
**Goal:** Prove the engine aggressively halts on the *first* Hard Deny, rather than overriding it with a later rule's success.
*   **Setup:** In `main.py`, inject context: `{"user_role": "restricted", "is_legal_sensitive": True}`. Make the agent propose an `ESCALATE` action.
*   **Expected Result:** Both rules technically apply and both are `DENY` states. 
*   **Verification:** The policy engine should cleanly halt and return the reason for whichever rule fired *first* in the list, proving short-circuit behavior works.
