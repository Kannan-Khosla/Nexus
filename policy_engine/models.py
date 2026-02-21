from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    AUTO_RESOLVE = "auto_resolve"
    AUTO_REPLY = "auto_reply"
    SEND_EMAIL = "send_email"
    ESCALATE = "escalate"

class DecisionStatus(str, Enum):
    ALLOW = "allow"
    DENY = "deny"

class ActionProposal(BaseModel):
    action_type: ActionType
    target_id: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    payload: Dict[str, Any] = Field(default_factory=dict)

class PolicyDecision(BaseModel):
    status: DecisionStatus
    reason: str
    confidence_adjustment: float = 0.0 # e.g. -0.2 if context suggests higher risk
