"""Service for automatic ticket routing based on rules."""
from typing import Optional, Dict, Any, List
from app.logger import setup_logger
from app.supabase_config import supabase
from datetime import datetime, timezone

logger = setup_logger(__name__)


class RoutingService:
    """Service for automatic ticket routing."""
    
    def __init__(self):
        self.supabase = supabase
    
    def apply_routing_rules(self, ticket_id: str, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Apply routing rules to a ticket.
        Returns dict with actions taken.
        """
        try:
            if not self.supabase:
                return {"success": False, "error": "Database not configured"}
            
            # Get ticket details
            ticket_res = (
                self.supabase.table("tickets")
                .select("*")
                .eq("id", ticket_id)
                .limit(1)
                .execute()
            )
            
            if not ticket_res.data:
                return {"success": False, "error": "Ticket not found"}
            
            ticket = ticket_res.data[0]
            
            # Get all active routing rules for the organization (or global if no org)
            query = (
                self.supabase.table("routing_rules")
                .select("*")
                .eq("is_active", True)
            )
            
            if organization_id:
                query = query.eq("organization_id", organization_id)
            else:
                # Get organization from ticket if available
                if ticket.get("organization_id"):
                    query = query.eq("organization_id", ticket["organization_id"])
            
            rules_res = query.order("priority", desc=True).execute()
            rules = rules_res.data if rules_res.data else []
            
            if not rules:
                return {"success": True, "actions": [], "message": "No routing rules found"}
            
            # Get ticket messages for keyword matching
            messages_res = (
                self.supabase.table("messages")
                .select("message")
                .eq("ticket_id", ticket_id)
                .execute()
            )
            ticket_text = " ".join([msg.get("message", "") for msg in (messages_res.data or [])])
            ticket_text_lower = ticket_text.lower()
            subject_lower = ticket.get("subject", "").lower()
            context_lower = ticket.get("context", "").lower()
            
            # Get ticket tags
            tags_res = (
                self.supabase.table("ticket_tags")
                .select("tag_id")
                .eq("ticket_id", ticket_id)
                .execute()
            )
            ticket_tag_ids = {tag["tag_id"] for tag in (tags_res.data or [])}
            
            actions_taken = []
            
            # Evaluate each rule
            for rule in rules:
                if not self._rule_matches(rule, ticket, ticket_text_lower, subject_lower, context_lower, ticket_tag_ids):
                    continue
                
                # Rule matches - apply action
                action_result = self._apply_rule_action(rule, ticket_id, ticket)
                if action_result.get("success"):
                    actions_taken.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "action_type": rule["action_type"],
                        "action_value": rule["action_value"],
                        "result": action_result
                    })
                    
                    # Log the routing action
                    try:
                        self.supabase.table("routing_logs").insert({
                            "ticket_id": ticket_id,
                            "routing_rule_id": rule["id"],
                            "rule_name": rule["name"],
                            "action_taken": f"{rule['action_type']}: {rule['action_value']}",
                            "matched_conditions": rule.get("conditions", {}),
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }).execute()
                    except Exception as e:
                        logger.warning(f"Failed to log routing action: {e}")
            
            return {
                "success": True,
                "actions": actions_taken,
                "rules_evaluated": len(rules),
                "rules_matched": len(actions_taken)
            }
            
        except Exception as e:
            logger.error(f"Error in apply_routing_rules: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _rule_matches(
        self,
        rule: Dict[str, Any],
        ticket: Dict[str, Any],
        ticket_text_lower: str,
        subject_lower: str,
        context_lower: str,
        ticket_tag_ids: set
    ) -> bool:
        """Check if a routing rule matches the ticket."""
        conditions = rule.get("conditions", {})
        
        # Check keywords
        keywords = conditions.get("keywords", [])
        if keywords:
            keyword_match = False
            search_text = f"{subject_lower} {ticket_text_lower} {context_lower}"
            for keyword in keywords:
                if keyword.lower() in search_text:
                    keyword_match = True
                    break
            if not keyword_match:
                return False
        
        # Check issue types (can match against context or category)
        issue_types = conditions.get("issue_types", [])
        if issue_types:
            ticket_category = ticket.get("category", "").lower()
            ticket_context = context_lower
            issue_match = False
            for issue_type in issue_types:
                if issue_type.lower() in ticket_category or issue_type.lower() in ticket_context:
                    issue_match = True
                    break
            if not issue_match:
                return False
        
        # Check tags
        tag_names = conditions.get("tags", [])
        if tag_names:
            # Get tag IDs for the tag names
            tags_res = (
                self.supabase.table("tags")
                .select("id, name")
                .in_("name", tag_names)
                .execute()
            )
            rule_tag_ids = {tag["id"] for tag in (tags_res.data or [])}
            if not rule_tag_ids.intersection(ticket_tag_ids):
                return False
        
        # Check context
        contexts = conditions.get("context", [])
        if contexts:
            if context_lower not in [c.lower() for c in contexts]:
                return False
        
        # Check priority
        priorities = conditions.get("priority", [])
        if priorities:
            if ticket.get("priority", "").lower() not in [p.lower() for p in priorities]:
                return False
        
        return True
    
    def _apply_rule_action(self, rule: Dict[str, Any], ticket_id: str, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a routing rule action to a ticket."""
        try:
            action_type = rule["action_type"]
            action_value = rule["action_value"]
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
            
            if action_type == "assign_to_agent":
                # Verify agent exists and is admin
                agent_res = (
                    self.supabase.table("users")
                    .select("id, email, role")
                    .eq("email", action_value.lower())
                    .in_("role", ["admin", "super_admin"])
                    .limit(1)
                    .execute()
                )
                if agent_res.data:
                    update_data["assigned_to"] = action_value.lower()
                    update_data["status"] = "human_assigned"
                else:
                    return {"success": False, "error": f"Agent not found: {action_value}"}
            
            elif action_type == "set_priority":
                if action_value.lower() in ["low", "medium", "high", "urgent"]:
                    update_data["priority"] = action_value.lower()
                else:
                    return {"success": False, "error": f"Invalid priority: {action_value}"}
            
            elif action_type == "add_tag":
                # Find or create tag
                tag_res = (
                    self.supabase.table("tags")
                    .select("id")
                    .eq("name", action_value)
                    .limit(1)
                    .execute()
                )
                if tag_res.data:
                    tag_id = tag_res.data[0]["id"]
                    # Add tag to ticket if not already present
                    existing_tag_res = (
                        self.supabase.table("ticket_tags")
                        .select("id")
                        .eq("ticket_id", ticket_id)
                        .eq("tag_id", tag_id)
                        .limit(1)
                        .execute()
                    )
                    if not existing_tag_res.data:
                        self.supabase.table("ticket_tags").insert({
                            "ticket_id": ticket_id,
                            "tag_id": tag_id,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }).execute()
                else:
                    return {"success": False, "error": f"Tag not found: {action_value}"}
            
            elif action_type == "set_category":
                update_data["category"] = action_value
            
            # Apply updates to ticket
            if update_data:
                self.supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
            
            return {"success": True, "action": action_type, "value": action_value}
            
        except Exception as e:
            logger.error(f"Error applying rule action: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


# Global instance
routing_service = RoutingService()

