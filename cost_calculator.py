"""
Cost Calculator
Calculates cost impact for Terraform resource changes.
"""

import logging
from typing import Dict, Any, Optional
from azure_price_fetcher import AzurePriceFetcher
from resource_mapper import ResourceMapper
from tfplan_parser import TerraformPlanParser

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculates cost impact for resource changes."""
    
    def __init__(self, price_fetcher: AzurePriceFetcher, resource_mapper: ResourceMapper):
        """
        Initialize the cost calculator.
        
        Args:
            price_fetcher: Azure price fetcher instance
            resource_mapper: Resource mapper instance
        """
        self.price_fetcher = price_fetcher
        self.resource_mapper = resource_mapper
        self.parser = TerraformPlanParser()
    
    def calculate_cost_impact(self, resource_change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calculate the cost impact of a resource change.
        
        Args:
            resource_change: Parsed resource change from Terraform plan
            
        Returns:
            Cost impact details or None if calculation fails
        """
        address = resource_change.get("address", "unknown")
        resource_type = resource_change.get("type", "")
        action = resource_change.get("action", "")
        
        logger.info(f"Calculating cost for {action} on {address}")
        
        try:
            if action == "create":
                return self._calculate_create_cost(resource_change)
            elif action == "delete":
                return self._calculate_delete_cost(resource_change)
            elif action == "update":
                return self._calculate_update_cost(resource_change)
            elif action == "replace":
                return self._calculate_replace_cost(resource_change)
            else:
                logger.warning(f"Unknown action type: {action}")
                return None
                
        except Exception as e:
            logger.error(f"Error calculating cost for {address}: {e}")
            return {
                "address": address,
                "action": action,
                "cost_impact": 0.0,
                "error": str(e),
                "details": {}
            }
    
    def _calculate_create_cost(self, resource_change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Calculate cost for a CREATE action (positive impact)."""
        config = resource_change.get("after", {})
        return self._get_resource_cost(resource_change, config, multiplier=1.0)
    
    def _calculate_delete_cost(self, resource_change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Calculate cost for a DELETE action (negative impact)."""
        config = resource_change.get("before", {})
        return self._get_resource_cost(resource_change, config, multiplier=-1.0)
    
    def _calculate_update_cost(self, resource_change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Calculate cost for an UPDATE action (delta)."""
        before_config = resource_change.get("before", {})
        after_config = resource_change.get("after", {})
        
        # Get cost before and after
        before_result = self._get_resource_cost(resource_change, before_config, multiplier=1.0)
        after_result = self._get_resource_cost(resource_change, after_config, multiplier=1.0)
        
        if not before_result or not after_result:
            return None
        
        cost_before = before_result.get("monthly_cost", 0.0)
        cost_after = after_result.get("monthly_cost", 0.0)
        cost_delta = cost_after - cost_before
        
        return {
            "address": resource_change.get("address", "unknown"),
            "action": "update",
            "cost_impact": cost_delta,
            "details": {
                "Resource Type": resource_change.get("type", "unknown"),
                "Location": self._get_location(resource_change, after_config),
                "Before": self._get_sku_display(resource_change, before_config),
                "After": self._get_sku_display(resource_change, after_config),
                "Cost Before": f"${cost_before:,.2f}",
                "Cost After": f"${cost_after:,.2f}"
            }
        }
    
    def _calculate_replace_cost(self, resource_change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Calculate cost for a REPLACE action (delete + create)."""
        # Replace is essentially delete old + create new
        # We'll calculate the delta similar to update
        return self._calculate_update_cost(resource_change)
    
    def _get_resource_cost(
        self,
        resource_change: Dict[str, Any],
        config: Dict[str, Any],
        multiplier: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get the monthly cost for a resource configuration.
        
        Args:
            resource_change: Resource change information
            config: Resource configuration
            multiplier: Cost multiplier (1.0 for create, -1.0 for delete)
            
        Returns:
            Cost details or None
        """
        resource_type = resource_change.get("type", "")
        address = resource_change.get("address", "unknown")
        
        # Get Azure service name
        service_name = self.resource_mapper.get_azure_service_name(resource_type)
        if not service_name:
            logger.warning(f"No service mapping for {resource_type}")
            return None
        
        # Extract SKU and region
        sku = self.resource_mapper.extract_sku(resource_type, config)
        region = self.resource_mapper.extract_region(resource_type, config)
        
        if not region:
            logger.warning(f"No region found for {address}")
            return None
        
        # Normalize region
        normalized_region = self.resource_mapper.normalize_region(region)
        
        # Get monthly cost from API
        monthly_cost = self.price_fetcher.get_monthly_cost(
            service_name=service_name,
            region=normalized_region,
            sku_name=sku
        )
        # Derive hourly from monthly if present
        hourly_price = None
        if monthly_cost is not None and monthly_cost > 0:
            hourly_price = monthly_cost / 730
        # Handle Redis multi-node pricing
        node_count = 1
        if resource_type == "azurerm_redis_cache":
            # Basic family = B -> 1 node, others (C/P) have 2 primary replicas for cost basis
            family = config.get("family")
            if family in ("C", "P"):
                node_count = 2
            # If we selected per-node instance pricing (Cache Instance) we multiply
            if monthly_cost is not None and monthly_cost > 0:
                # Fetch all prices to see if we picked instance price (endswith 'Cache Instance')
                all_prices = self.price_fetcher.get_prices(service_name, normalized_region, sku)
                chosen_is_instance = False
                for item in all_prices:
                    if item.get("meterName") == "P1 Cache":
                        # Use that as per cluster price, override monthly_cost
                        if sku and sku.startswith("P"):
                            monthly_cost = item.get("retailPrice", 0.0) * 730
                            hourly_price = item.get("retailPrice", 0.0)
                            chosen_is_instance = False
                        break
                    if item.get("meterName") == f"{sku} Cache Instance":
                        chosen_is_instance = True
                if chosen_is_instance:
                    monthly_cost = monthly_cost * node_count
                    hourly_price = hourly_price * node_count if hourly_price else None
        
        # Handle AKS node count multiplication
        if resource_type == "azurerm_kubernetes_cluster":
            # Get node count from default_node_pool
            default_pool = config.get("default_node_pool", {})
            if isinstance(default_pool, dict):
                aks_node_count = default_pool.get("node_count", 1)
                if monthly_cost is not None and aks_node_count > 0:
                    monthly_cost = monthly_cost * aks_node_count
                    hourly_price = hourly_price * aks_node_count if hourly_price else None
        elif resource_type == "azurerm_kubernetes_cluster_node_pool":
            # Additional node pools
            aks_node_count = config.get("node_count", 1)
            if monthly_cost is not None and aks_node_count > 0:
                monthly_cost = monthly_cost * aks_node_count
                hourly_price = hourly_price * aks_node_count if hourly_price else None
        
        # Handle VM Scale Sets
        if resource_type in ["azurerm_linux_virtual_machine_scale_set", "azurerm_windows_virtual_machine_scale_set"]:
            instances = config.get("instances", 1)
            if monthly_cost is not None and instances > 0:
                monthly_cost = monthly_cost * instances
                hourly_price = hourly_price * instances if hourly_price else None
        
        if monthly_cost is None:
            logger.warning(f"No pricing data found for {address}")
            monthly_cost = 0.0
        cost_impact = monthly_cost * multiplier
        return {
            "address": address,
            "action": resource_change.get("action", "unknown"),
            "cost_impact": cost_impact,
            "monthly_cost": monthly_cost,
            "details": {
                "Resource Type": resource_type,
                "Location": region,
                "SKU": sku or "N/A",
                "Service Name": service_name,
                "Hourly Price": f"${hourly_price:.3f}" if hourly_price else "N/A",
                "Node Count": node_count if resource_type == "azurerm_redis_cache" else "N/A"
            }
        }
    
    def _get_location(self, resource_change: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Get location from config."""
        resource_type = resource_change.get("type", "")
        location = self.resource_mapper.extract_region(resource_type, config)
        return location or "N/A"
    
    def _get_sku_display(self, resource_change: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Get SKU display string from config."""
        resource_type = resource_change.get("type", "")
        sku = self.resource_mapper.extract_sku(resource_type, config)
        return sku or "N/A"
