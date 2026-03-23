"""Pydantic request/response models for all API endpoints."""

from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class TicketRequest(BaseModel):
    context: str
    subject: str
    message: str
    priority: str = "medium"  # low, medium, high, urgent


class MessageRequest(BaseModel):
    message: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class RatingRequest(BaseModel):
    message_id: str
    rating: int  # 1-5


class EscalateRequest(BaseModel):
    reason: str | None = None


class AdminReplyRequest(BaseModel):
    message: str


class AssignAdminRequest(BaseModel):
    admin_email: str


class SLADefinitionRequest(BaseModel):
    name: str
    description: str | None = None
    priority: str  # low, medium, high, urgent
    response_time_minutes: int
    resolution_time_minutes: int
    business_hours_only: bool = False
    business_hours_start: str | None = None  # HH:MM format
    business_hours_end: str | None = None  # HH:MM format
    business_days: list[int] | None = None  # [1-7] where 1=Monday, 7=Sunday


class UpdatePriorityRequest(BaseModel):
    priority: str  # low, medium, high, urgent


class TimeEntryRequest(BaseModel):
    duration_minutes: int
    description: str | None = None
    entry_type: str = "work"  # work, waiting, research, communication, other
    billable: bool = True


class EmailAccountRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None
    provider: str  # smtp, sendgrid, ses, mailgun, other
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    api_key: str | None = None
    credentials: dict | None = None
    is_active: bool = True
    is_default: bool = False
    imap_host: str | None = None
    imap_port: int | None = None
    imap_enabled: bool = False


class SendEmailRequest(BaseModel):
    to_emails: list[EmailStr]
    subject: str
    body_text: str
    body_html: str | None = None
    cc_emails: list[EmailStr] | None = None
    bcc_emails: list[EmailStr] | None = None
    reply_to: EmailStr | None = None
    account_id: str | None = None


class EmailWebhookRequest(BaseModel):
    raw_email: str | None = None
    from_email: EmailStr | None = None
    to_email: EmailStr | None = None
    subject: str | None = None
    body: str | None = None
    message_id: str | None = None
    in_reply_to: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class EmailTemplateRequest(BaseModel):
    name: str
    subject: str
    body_text: str
    body_html: str | None = None
    template_type: str  # ticket_created, ticket_reply, ticket_closed, ticket_assigned, custom
    variables: dict | None = None
    is_active: bool = True


class DeleteTicketsRequest(BaseModel):
    ticket_ids: list[str]


class RestoreTicketsRequest(BaseModel):
    ticket_ids: list[str]


class RoutingRuleRequest(BaseModel):
    name: str
    description: str | None = None
    priority: int = 0
    is_active: bool = True
    conditions: dict  # {keywords: [], issue_types: [], tags: [], context: [], priority: []}
    action_type: str  # assign_to_agent, assign_to_group, set_priority, add_tag, set_category
    action_value: str  # Agent email, group name, priority value, tag name, category name


class TagRequest(BaseModel):
    name: str
    color: str | None = None
    description: str | None = None


class CategoryRequest(BaseModel):
    name: str
    color: str | None = None
    description: str | None = None


class TicketTagsRequest(BaseModel):
    tag_ids: list[str]


class TicketCategoryRequest(BaseModel):
    category: str | None = None


# ============================================================
# RAG / Knowledge Base
# ============================================================

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class ChatRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str | None = None
    content: str
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SearchResultItem]


# ============================================================
# Compliance / Document Evaluation
# ============================================================

class RequirementInput(BaseModel):
    id: str
    title: str
    description: str
    category: str | None = None


class ComplianceTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    requirements: list[RequirementInput]


class EvaluateRequest(BaseModel):
    document_id: str
    template_id: str


class RequirementResult(BaseModel):
    requirement_id: str
    status: Literal["pass", "fail", "partial", "not_applicable"]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""


class EvaluationResponse(BaseModel):
    id: str
    document_id: str
    template_id: str
    results: list[RequirementResult]
    overall_score: float
    summary: str


# ============================================================
# Multi-Agent Workflows
# ============================================================

class ClassifierOutput(BaseModel):
    category: str
    sentiment: Literal["positive", "neutral", "negative", "frustrated"]
    complexity: Literal["simple", "moderate", "complex"]
    tags: list[str] = []


class ResearcherOutput(BaseModel):
    relevant_docs: list[dict] = []
    suggested_resolution: str
    confidence: float = Field(ge=0.0, le=1.0)


class DrafterOutput(BaseModel):
    draft_response: str
    tone: str
    key_points: list[str] = []


class ReviewerOutput(BaseModel):
    approved: bool
    feedback: str
    revised_response: str
    quality_score: float = Field(ge=0.0, le=1.0)


class WorkflowStepResult(BaseModel):
    agent_name: str
    output: dict
    duration_ms: int


class WorkflowAnalysisResponse(BaseModel):
    id: str
    ticket_id: str
    pipeline_name: str
    status: str
    steps: list[WorkflowStepResult]
    final_output: Optional[dict] = None
