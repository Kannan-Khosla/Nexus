"""Ticket endpoints: create, reply, rate, escalate, thread, stats, customer tickets."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timezone
from app.supabase_config import supabase
from app.config import settings
from app.logger import setup_logger
from app.dependencies import get_current_user, get_current_admin
from app.helpers import is_rate_limited, sanitize_output, generate_ai_reply
from app.routing_service import routing_service
from app.schemas import (
    TicketRequest, MessageRequest, RatingRequest, EscalateRequest,
)

logger = setup_logger(__name__)
router = APIRouter()

@router.post("/ticket")
def create_or_continue_ticket(
    req: TicketRequest, current_user: dict = Depends(get_current_user)
):
    """Create or continue a ticket and optionally generate an AI reply.

    Parameters
    ----------
    req : TicketRequest
        `{ context, subject, message }`
    current_user : dict
        Current authenticated customer

    Returns
    -------
    dict
        `{ ticket_id, reply? }` or `{ ticket_id, rate_limited, wait_seconds }`
    """
    try:
        if supabase is None:
            return {"error": "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env file"}
        
        user_id = current_user["id"]
        
        # 1️⃣ Find open ticket with same context & subject for this user
        existing = (
            supabase.table("tickets")
            .select("*")
            .eq("context", req.context)
            .eq("subject", req.subject)
            .eq("status", "open")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            ticket = existing.data[0]
            ticket_id = ticket["id"]
            logger.info(f"Continuing existing ticket: {ticket_id}")
        else:
            # Create new ticket
            priority = req.priority if hasattr(req, 'priority') and req.priority in ['low', 'medium', 'high', 'urgent'] else 'medium'
            
            # Auto-assign SLA based on priority
            sla_id = None
            try:
                sla_res = (
                    supabase.table("sla_definitions")
                    .select("id")
                    .eq("priority", priority)
                    .eq("is_active", True)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if sla_res.data:
                    sla_id = sla_res.data[0]["id"]
            except Exception as e:
                logger.warning(f"Could not auto-assign SLA for priority {priority}: {e}")
            
            new_ticket = (
                supabase.table("tickets")
                .insert(
                    {
                        "context": req.context,
                        "subject": req.subject,
                        "status": "open",
                        "priority": priority,
                        "sla_id": sla_id,
                        "user_id": user_id,
                        "source": "web",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .execute()
            )
            ticket = new_ticket.data[0]
            ticket_id = ticket["id"]
            logger.info(f"Created new ticket: {ticket_id}")
            
            # Apply routing rules to new tickets
            try:
                routing_result = routing_service.apply_routing_rules(ticket_id)
                if routing_result.get("success") and routing_result.get("rules_matched", 0) > 0:
                    logger.info(f"Applied {routing_result['rules_matched']} routing rule(s) to ticket {ticket_id}")
                    # Reload ticket to get updated assignment/priority
                    ticket_res = (
                        supabase.table("tickets")
                        .select("*")
                        .eq("id", ticket_id)
                        .limit(1)
                        .execute()
                    )
                    if ticket_res.data:
                        ticket = ticket_res.data[0]
            except Exception as e:
                logger.warning(f"Failed to apply routing rules to ticket {ticket_id}: {e}")

        # 2️⃣ Add customer message
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "customer",
                "message": req.message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        # 3️⃣ Check if human is assigned — skip AI if true
        if ticket.get("assigned_to"):
            logger.info(
                f"Human agent assigned ({ticket['assigned_to']}), skipping AI reply for ticket {ticket_id}"
            )
            return {
                "ticket_id": ticket_id,
                "reply": f"Human agent {ticket['assigned_to']} will handle this ticket.",
            }

        # 4️⃣ Fetch full message history for context
        history = (
            supabase.table("messages")
            .select("sender, message")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .execute()
        )
        conversation_history = "\n".join(
            [f"{m['sender'].capitalize()}: {m['message']}" for m in history.data]
        )

        # 5️⃣ Generate AI reply
        prompt = f"""
        You are an AI support assistant for {req.context}.
        Continue the following ticket conversation helpfully and politely.
        ----
        {conversation_history}
        ----
        Reply as the assistant:
        """

        # 5.1️⃣ Rate limit check
        limited, _meta = is_rate_limited(ticket_id)
        if limited:
            return {
                "ticket_id": ticket_id,
                "rate_limited": True,
                "wait_seconds": settings.ai_reply_window_seconds,
            }

        # 5.2️⃣ Generate AI reply with retry/backoff
        logger.info(f"Generating AI reply for ticket {ticket_id}")
        raw_answer = generate_ai_reply(prompt)

        # 5.3️⃣ Sanitize output for profanity/PII
        answer, flags = sanitize_output(raw_answer)

        # 6️⃣ Store AI reply
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "ai",
                "message": answer,
                "confidence": 0.95,
                "success": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        return {"ticket_id": ticket_id, "reply": answer}

    except Exception as e:
        logger.error(f"Error in create_or_continue_ticket: {e}", exc_info=True)
        raise


# ---------------------------------------------------
# POST /ticket/{ticket_id}/reply → Continue thread
# ---------------------------------------------------
@router.post("/ticket/{ticket_id}/reply")
def reply_to_existing_ticket(
    ticket_id: str, req: MessageRequest, current_user: dict = Depends(get_current_user)
):
    """Append a customer message and optionally generate an AI reply.

    If a human is assigned, AI reply is skipped.
    Rate limiting and output sanitization apply if AI is used.
    """
    try:
        if supabase is None:
            return {"error": "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env file"}
        
        user_id = current_user["id"]
        
        # 1️⃣ Verify ticket exists and belongs to user
        ticket_res = (
            supabase.table("tickets").select("*").eq("id", ticket_id).limit(1).execute()
        )
        if not ticket_res.data:
            return {"error": f"Ticket {ticket_id} not found."}

        ticket = ticket_res.data[0]
        
        # Verify ticket belongs to current user
        if ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )

        # 2️⃣ Store new customer message
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "customer",
                "message": req.message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        # 3️⃣ If human assigned, skip AI
        if ticket.get("assigned_to"):
            logger.info(
                f"Human assigned ({ticket['assigned_to']}), skipping AI for ticket {ticket_id}"
            )
            return {
                "ticket_id": ticket_id,
                "reply": f"Human agent {ticket['assigned_to']} will handle this.",
            }

        # 4️⃣ Fetch all messages
        history = (
            supabase.table("messages")
            .select("sender, message")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .execute()
        )
        conversation_history = "\n".join(
            [f"{m['sender'].capitalize()}: {m['message']}" for m in history.data]
        )

        # 5️⃣ Generate AI reply
        prompt = f"""
        You are an AI assistant continuing this customer support thread.
        ----
        {conversation_history}
        ----
        Respond concisely and politely as the assistant.
        """

        # 5.1️⃣ Rate limit check
        limited, _meta = is_rate_limited(ticket_id)
        if limited:
            return {
                "ticket_id": ticket_id,
                "rate_limited": True,
                "wait_seconds": settings.ai_reply_window_seconds,
            }

        # 5.2️⃣ Generate AI reply with retry/backoff
        raw_answer = generate_ai_reply(prompt)

        # 5.3️⃣ Sanitize output for profanity/PII
        answer, flags = sanitize_output(raw_answer)

        # 6️⃣ Store AI reply
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "ai",
                "message": answer,
                "confidence": 0.95,
                "success": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        return {"ticket_id": ticket_id, "reply": answer}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reply_to_existing_ticket: {e}", exc_info=True)
        raise


# ---------------------------------------------------
# POST /ticket/{ticket_id}/rate → Rate an AI response
# ---------------------------------------------------
@router.post("/ticket/{ticket_id}/rate")
def rate_ai_response(
    ticket_id: str,
    req: RatingRequest,
    current_user: dict = Depends(get_current_user),
):
    """Rate an AI response message."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        user_id = current_user["id"]
        
        # Validate rating
        if req.rating < 1 or req.rating > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be between 1 and 5",
            )
        
        # Verify ticket exists and belongs to user
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        ticket = ticket_res.data[0]
        if ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Verify message exists and is an AI response
        message_res = (
            supabase.table("messages")
            .select("*")
            .eq("id", req.message_id)
            .eq("ticket_id", ticket_id)
            .limit(1)
            .execute()
        )
        if not message_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        message = message_res.data[0]
        if message.get("sender") != "ai":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only AI messages can be rated",
            )
        
        # Check if user already rated this message
        existing_rating = (
            supabase.table("ratings")
            .select("*")
            .eq("ticket_id", ticket_id)
            .eq("message_id", req.message_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if existing_rating.data:
            # Update existing rating
            supabase.table("ratings").update({"rating": req.rating}).eq(
                "id", existing_rating.data[0]["id"]
            ).execute()
            logger.info(f"Updated rating for message {req.message_id} by user {user_id}")
        else:
            # Create new rating
            supabase.table("ratings").insert(
                {
                    "ticket_id": ticket_id,
                    "message_id": req.message_id,
                    "user_id": user_id,
                    "rating": req.rating,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
            logger.info(f"Created rating for message {req.message_id} by user {user_id}")
        
        return {"success": True, "message": "Rating saved"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in rate_ai_response: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save rating",
        )


# ---------------------------------------------------
# POST /ticket/{ticket_id}/escalate → Request human support
# ---------------------------------------------------
@router.post("/ticket/{ticket_id}/escalate")
def escalate_to_human(
    ticket_id: str,
    req: EscalateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Request human support for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        user_id = current_user["id"]
        
        # Verify ticket exists and belongs to user
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        ticket = ticket_res.data[0]
        if ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Check if escalation already exists
        existing_escalation = (
            supabase.table("human_escalations")
            .select("*")
            .eq("ticket_id", ticket_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if existing_escalation.data:
            escalation = existing_escalation.data[0]
            if escalation["status"] != "resolved":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Human support already requested for this ticket",
                )
        
        # Create escalation
        supabase.table("human_escalations").insert(
            {
                "ticket_id": ticket_id,
                "user_id": user_id,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        
        # Update ticket status
        supabase.table("tickets").update(
            {"status": "human_assigned", "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", ticket_id).execute()
        
        # Add system message
        escalation_message = "Customer requested to connect with a human agent."
        if req.reason:
            escalation_message += f" Reason: {req.reason}"
        
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "system",
                "message": escalation_message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        
        logger.info(f"Ticket {ticket_id} escalated to human by user {user_id}")
        
        return {
            "success": True,
            "message": "Human support requested. An agent will assist you shortly.",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in escalate_to_human: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to escalate ticket",
        )


# ---------------------------------------------------
# GET /ticket/{ticket_id} → Fetch full thread
# ---------------------------------------------------
@router.get("/ticket/{ticket_id}")
def get_ticket_thread(
    ticket_id: str, current_user: dict = Depends(get_current_user)
):
    """Fetch a ticket and its full message thread ordered by time."""
    try:
        if supabase is None:
            return {"error": "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env file"}
        
        ticket = (
            supabase.table("tickets").select("*").eq("id", ticket_id).limit(1).execute()
        )
        if not ticket.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket_data = ticket.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access: customers can only see their tickets, admins can see all
        if user_role == "customer" and ticket_data.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        messages = (
            supabase.table("messages")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .execute()
        )
        
        # Get ratings for AI messages
        ratings = (
            supabase.table("ratings")
            .select("*")
            .eq("ticket_id", ticket_id)
            .eq("user_id", user_id)
            .execute()
        )
        ratings_map = {r["message_id"]: r["rating"] for r in ratings.data}
        
        # Attach ratings to messages
        messages_with_ratings = messages.data.copy()
        for msg in messages_with_ratings:
            msg["user_rating"] = ratings_map.get(msg["id"])
        
        return {
            "ticket": ticket_data,
            "messages": messages_with_ratings,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_ticket_thread: {e}", exc_info=True)
        raise


# ---------------------------------------------------
# GET /stats → Ticket summary
# ---------------------------------------------------
@router.get("/stats")
def get_stats():
    """Fetch ticket metrics and a sample from the `ticket_summary` view."""
    try:
        total = supabase.table("tickets").select("id", count="exact").execute().count
        open_t = (
            supabase.table("tickets")
            .select("id", count="exact")
            .eq("status", "open")
            .execute()
            .count
        )
        closed_t = total - open_t

        summary = (
            supabase.table("ticket_summary")
            .select(
                "ticket_id, context, subject, status, total_messages, avg_confidence"
            )
            .limit(5)
            .execute()
        )

        return {
            "total_tickets": total,
            "open_tickets": open_t,
            "closed_tickets": closed_t,
            "sample_summary": summary.data,
        }

    except Exception as e:
        logger.error(f"Error in get_stats: {e}", exc_info=True)
        raise


@router.get("/customer/tickets")
def get_customer_tickets(
    search: str = Query(default=None, description="Search in subject and message content"),
    filter_status: str = Query(default=None, description="Filter by status (open, human_assigned, closed)"),
    context: str = Query(default=None, description="Filter by context/brand"),
    date_from: str = Query(default=None, description="Filter from date (ISO format: YYYY-MM-DD)"),
    date_to: str = Query(default=None, description="Filter to date (ISO format: YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Number of items per page"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all tickets for the current customer with search, filter, and pagination options.
    
    Supports:
    - Full-text search in subject and message content
    - Filter by status, context, date range
    - Pagination with page and page_size parameters
    """
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        user_id = current_user["id"]
        query = supabase.table("tickets").select("*", count="exact").eq("user_id", user_id)
        
        # Exclude deleted tickets by default
        query = query.eq("is_deleted", False)
        
        # Apply filters
        if filter_status:
            query = query.eq("status", filter_status)
        if context:
            query = query.eq("context", context)
        if date_from:
            query = query.gte("created_at", f"{date_from}T00:00:00Z")
        if date_to:
            query = query.lte("created_at", f"{date_to}T23:59:59Z")
        
        res = query.order("updated_at", desc=True).execute()
        all_tickets = res.data
        
        # If search is provided, filter by subject and message content
        if search:
            filtered_tickets = []
            search_lower = search.lower()
            for ticket in all_tickets:
                # Check if search matches subject
                if search_lower in ticket.get("subject", "").lower():
                    filtered_tickets.append(ticket)
                    continue
                
                # Check if search matches any message in the ticket
                messages_res = (
                    supabase.table("messages")
                    .select("message")
                    .eq("ticket_id", ticket["id"])
                    .execute()
                )
                for msg in messages_res.data:
                    if search_lower in msg.get("message", "").lower():
                        filtered_tickets.append(ticket)
                        break
            
            all_tickets = filtered_tickets
        
        # Calculate pagination
        total_count = len(all_tickets)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        skip = (page - 1) * page_size
        tickets = all_tickets[skip:skip + page_size]
        
        return {
            "tickets": tickets,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_customer_tickets: {e}", exc_info=True)
        raise
