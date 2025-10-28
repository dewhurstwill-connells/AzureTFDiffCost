"""
Terraform Plan Parser
Extracts resource changes from Terraform plan JSON files.
"""

import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TerraformPlanParser:
    """Parses Terraform plan JSON files and extracts resource changes."""
    
    def parse_plan(self, plan_file: str) -> List[Dict[str, Any]]:
        """
        Parse a Terraform plan JSON file and extract resource changes.
        
        Args:
            plan_file: Path to the Terraform plan JSON file
            
        Returns:
            List of resource changes with action, type, and configuration details
        """
        logger.info(f"Parsing Terraform plan from {plan_file}")
        
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)
        
        resource_changes = plan_data.get("resource_changes", [])
        
        if not resource_changes:
            logger.warning("No resource_changes found in plan file")
            return []
        
        parsed_changes = []
        
        for resource in resource_changes:
            try:
                parsed = self._parse_resource_change(resource)
                if parsed:
                    parsed_changes.append(parsed)
            except Exception as e:
                logger.error(f"Error parsing resource {resource.get('address', 'unknown')}: {e}")
                continue
        
        return parsed_changes
    
    def _parse_resource_change(self, resource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single resource change entry.
        
        Args:
            resource: Resource change object from Terraform plan
            
        Returns:
            Parsed resource change data or None if not actionable
        """
        address = resource.get("address", "")
        resource_type = resource.get("type", "")
        name = resource.get("name", "")
        change = resource.get("change", {})
        
        actions = change.get("actions", [])
        
        # Filter out "no-op" actions
        if actions == ["no-op"] or not actions:
            return None
        
        # Determine primary action (create, delete, update, replace)
        primary_action = self._determine_primary_action(actions)
        
        # Get before and after configurations
        before = change.get("before")
        after = change.get("after")
        
        parsed_change = {
            "address": address,
            "type": resource_type,
            "name": name,
            "action": primary_action,
            "before": before,
            "after": after,
            "actions": actions
        }
        
        return parsed_change
    
    def _determine_primary_action(self, actions: List[str]) -> str:
        """
        Determine the primary action from a list of actions.
        
        Args:
            actions: List of action strings (e.g., ["delete", "create"] for replace)
            
        Returns:
            Primary action string: "create", "delete", "update", or "replace"
        """
        if "delete" in actions and "create" in actions:
            return "replace"
        elif "create" in actions:
            return "create"
        elif "delete" in actions:
            return "delete"
        elif "update" in actions:
            return "update"
        else:
            return "unknown"
    
    def extract_resource_attributes(self, resource_change: Dict[str, Any], action: str) -> Dict[str, Any]:
        """
        Extract relevant attributes from a resource change based on action.
        
        Args:
            resource_change: Parsed resource change data
            action: The action being performed (create, delete, update, replace)
            
        Returns:
            Dictionary of relevant resource attributes
        """
        if action == "create" or action == "replace":
            return resource_change.get("after", {}) or {}
        elif action == "delete":
            return resource_change.get("before", {}) or {}
        elif action == "update":
            # For updates, we need both before and after
            return {
                "before": resource_change.get("before", {}),
                "after": resource_change.get("after", {})
            }
        return {}
