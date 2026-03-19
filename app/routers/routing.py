"""Routing rule endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from app.supabase_config import supabase
from app.logger import setup_logger
from app.dependencies import get_current_admin
from app.schemas import RoutingRuleRequest
import json

logger = setup_logger(__name__)
router = APIRouter()

@router.post("/admin/routing-rules")
def create_routing_rule(
    req: RoutingRuleRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new routing rule."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Validate action_type
        valid_actions = ["assign_to_agent", "assign_to_group", "set_priority", "add_tag", "set_category"]
        if req.action_type not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action type must be one of: {', '.join(valid_actions)}"
            )
        
        rule_data = {
            "name": req.name,
            "description": req.description,
            "priority": req.priority,
            "is_active": req.is_active,
            "conditions": json.dumps(req.conditions),
            "action_type": req.action_type,
            "action_value": req.action_value,
            "created_by": current_admin["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("routing_rules")
            .insert(rule_data)
            .execute()
        )
        
        logger.info(f"Created routing rule: {req.name} by {current_admin['email']}")
        return {"success": True, "rule": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_routing_rule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create routing rule",
        )


@router.get("/admin/routing-rules")
def list_routing_rules(
    current_admin: dict = Depends(get_current_admin)
):
    """List all routing rules."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        result = (
            supabase.table("routing_rules")
            .select("*")
            .order("priority", desc=True)
            .execute()
        )
        
        # Parse conditions JSON
        rules = result.data if result.data else []
        for rule in rules:
            if isinstance(rule.get("conditions"), str):
                try:
                    rule["conditions"] = json.loads(rule["conditions"])
                except:
                    rule["conditions"] = {}
        
        return {"rules": rules}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_routing_rules: {e}", exc_info=True)
        raise


@router.delete("/admin/routing-rules/{rule_id}")
def delete_routing_rule(
    rule_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete a routing rule."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify rule exists
        rule_res = (
            supabase.table("routing_rules")
            .select("*")
            .eq("id", rule_id)
            .limit(1)
            .execute()
        )
        if not rule_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routing rule not found"
            )
        
        supabase.table("routing_rules").delete().eq("id", rule_id).execute()
        
        logger.info(f"Deleted routing rule {rule_id} by {current_admin['email']}")
        return {"success": True, "message": "Routing rule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_routing_rule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete routing rule",
        )
