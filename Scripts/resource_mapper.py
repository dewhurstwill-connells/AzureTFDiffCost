"""
Resource Mapper
Maps Terraform azurerm resource types to Azure service names and pricing information.
"""

import json
import logging
import os
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class ResourceMapper:
    """Maps Terraform resources to Azure pricing service names."""
    
    def __init__(self, mapping_file: Optional[str] = None):
        """
        Initialize the resource mapper.
        
        Args:
            mapping_file: Optional mapping file path. When omitted, the mapper loads Scripts/resource_mapping.json relative to this module (instead of current working directory),
        """
        self.mapping_file = mapping_file or os.path.join(os.path.dirname(__file__), "resource_mapping.json")
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict[str, Any]:
        """
        Load resource mappings from JSON file.
        
        Returns:
            Dictionary of resource type mappings
        """
        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                mappings = json.load(f)
            logger.info(f"Loaded {len(mappings)} resource mappings")
            return mappings
        except FileNotFoundError:
            logger.warning(f"Mapping file {self.mapping_file} not found, using default mappings")
            return self._get_default_mappings()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing mapping file: {e}")
            return self._get_default_mappings()
    
    def _get_default_mappings(self) -> Dict[str, Any]:
        """
        Get default resource mappings if mapping file is not available.
        
        Returns:
            Dictionary of default mappings
        """
        return {
            "azurerm_linux_virtual_machine": {
                "azure_service_name": "Virtual Machines",
                "cost_type": "fixed",
                "sku_attribute": "size",
                "region_attribute": "location",
                "description": "Linux Virtual Machine"
            },
            "azurerm_windows_virtual_machine": {
                "azure_service_name": "Virtual Machines",
                "cost_type": "fixed",
                "sku_attribute": "size",
                "region_attribute": "location",
                "description": "Windows Virtual Machine"
            },
            "azurerm_mssql_database": {
                "azure_service_name": "SQL Database",
                "cost_type": "mixed",  # Can be fixed or serverless
                "sku_attribute": "sku_name",
                "region_attribute": "server_location",
                "description": "Azure SQL Database"
            },
            "azurerm_postgresql_server": {
                "azure_service_name": "Azure Database for PostgreSQL",
                "cost_type": "fixed",
                "sku_attribute": "sku_name",
                "region_attribute": "location",
                "description": "PostgreSQL Server"
            },
            "azurerm_mysql_server": {
                "azure_service_name": "Azure Database for MySQL",
                "cost_type": "fixed",
                "sku_attribute": "sku_name",
                "region_attribute": "location",
                "description": "MySQL Server"
            },
            "azurerm_redis_cache": {
                "azure_service_name": "Redis Cache",
                "cost_type": "fixed",
                "sku_attribute": "sku_name",
                "region_attribute": "location",
                "description": "Azure Redis Cache"
            },
            "azurerm_app_service_plan": {
                "azure_service_name": "Azure App Service",
                "cost_type": "fixed",
                "sku_attribute": "sku",
                "region_attribute": "location",
                "description": "App Service Plan"
            },
            "azurerm_service_plan": {
                "azure_service_name": "Azure App Service",
                "cost_type": "fixed",
                "sku_attribute": "sku_name",
                "region_attribute": "location",
                "description": "App Service Plan (newer resource)"
            },
            # Consumption-based resources to exclude
            "azurerm_storage_account": {
                "azure_service_name": "Storage",
                "cost_type": "consumption",
                "description": "Storage Account (consumption-based)"
            },
            "azurerm_function_app": {
                "azure_service_name": "Functions",
                "cost_type": "consumption",
                "description": "Function App (consumption plan)"
            },
            "azurerm_application_insights": {
                "azure_service_name": "Application Insights",
                "cost_type": "consumption",
                "description": "Application Insights"
            }
        }
    
    def get_mapping(self, resource_type: str) -> Optional[Dict[str, Any]]:
        """
        Get mapping information for a resource type.
        
        Args:
            resource_type: Terraform resource type (e.g., "azurerm_linux_virtual_machine")
            
        Returns:
            Mapping information or None if not found
        """
        mapping = self.mappings.get(resource_type)
        if mapping:
            return mapping
        
        # Fallback: Try to infer mapping from resource type
        if resource_type.startswith("azurerm_"):
            logger.warning(f"No mapping found for {resource_type}, attempting to infer service name")
            return self._infer_mapping(resource_type)
        
        return None
    
    def _infer_mapping(self, resource_type: str) -> Dict[str, Any]:
        """
        Attempt to infer mapping for an unmapped resource type.
        
        Args:
            resource_type: Terraform resource type
            
        Returns:
            Inferred mapping (may not be accurate)
        """
        # Strip azurerm_ prefix and convert to title case
        service_name = resource_type.replace("azurerm_", "").replace("_", " ").title()
        
        logger.info(f"Inferred service name '{service_name}' for {resource_type}")
        
        return {
            "azure_service_name": service_name,
            "cost_type": "unknown",  # Mark as unknown
            "description": f"Inferred mapping for {resource_type}",
            "sku_attribute": "sku",  # Try common attribute
            "region_attribute": "location",  # Standard attribute
            "notes": "This is an inferred mapping and may not be accurate. Please add proper mapping to resource_mapping.json"
        }
    
    def is_fixed_cost(self, resource_type: str, config: Dict[str, Any] = None) -> bool:
        """
        Check if a resource type has fixed costs.
        
        Args:
            resource_type: Terraform resource type
            config: Resource configuration (optional, used for dynamic checks)
            
        Returns:
            True if resource has fixed costs, False otherwise
        """
        mapping = self.get_mapping(resource_type)
        if not mapping:
            logger.debug(f"Unknown resource type: {resource_type}, assuming consumption")
            return False
        
        cost_type = mapping.get("cost_type", "consumption")
        
        # Special handling for App Service Plans
        if resource_type in ["azurerm_service_plan", "azurerm_app_service_plan"] and config:
            # Check if it's FlexConsumption (FC* SKUs are serverless/consumption)
            sku = config.get("sku_name") or (config.get("sku", {}) if isinstance(config.get("sku"), dict) else {}).get("size")
            if sku and (sku.startswith("FC") or sku.lower() in ["y1", "dynamic"]):
                logger.debug(f"Detected consumption-based App Service Plan SKU: {sku}")
                return False
        
        return cost_type == "fixed" or cost_type == "mixed"
    
    def get_azure_service_name(self, resource_type: str) -> Optional[str]:
        """
        Get the Azure service name for API queries.
        
        Args:
            resource_type: Terraform resource type
            
        Returns:
            Azure service name or None
        """
        mapping = self.get_mapping(resource_type)
        if not mapping:
            return None
        return mapping.get("azure_service_name")
    
    def extract_sku(self, resource_type: str, config: Dict[str, Any]) -> Optional[str]:
        """
        Extract SKU information from resource configuration.
        
        Args:
            resource_type: Terraform resource type
            config: Resource configuration attributes
            
        Returns:
            SKU string or None
        """
        mapping = self.get_mapping(resource_type)
        if not mapping:
            return None
        
        # Special handling for Redis Cache (combines family + capacity)
        if resource_type == "azurerm_redis_cache":
            family = config.get("family")
            capacity = config.get("capacity")
            if family and capacity is not None:
                # Azure API expects format like "P1", "C2", "B0"
                return f"{family}{capacity}"
        
        sku_attribute = mapping.get("sku_attribute")
        if not sku_attribute:
            return None
        
        # Handle nested attributes (e.g., "sku.tier")
        if "." in sku_attribute:
            parts = sku_attribute.split(".")
            value = config
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
        else:
            value = config.get(sku_attribute)
        
        if not value:
            return None
        
        # Apply transformations
        transform = mapping.get("sku_transform")
        if transform == "strip_standard_prefix":
            # Standard_D2s_v3 → D2s v3
            value = value.replace("Standard_", "").replace("_", " ")
        elif transform == "app_service_sku":
            # P1v2 → P1 v2, P1v3 → P1 v3
            import re
            # Match patterns like P1v2, P1v3, S1, etc.
            match = re.match(r'([A-Z]\d+)(v\d+)?', value)
            if match:
                base = match.group(1)
                version = match.group(2)
                if version:
                    value = f"{base} {version}"
                else:
                    value = base
        elif transform == "postgresql_sku" or transform == "mysql_sku":
            # B_Gen5_1 → 1 vCore, GP_Gen5_2 → 2 vCore
            import re
            match = re.match(r'([A-Z]+)_Gen\d+_(\d+)', value)
            if match:
                vcores = match.group(2)
                value = f"{vcores} vCore"
        elif transform == "disk_sku":
            # Map disk size to SKU tier based on storage type
            storage_type = value  # storage_account_type like "Premium_LRS"
            disk_size_gb = config.get("disk_size_gb", 0)
            
            if "Premium" in storage_type:
                # Premium SSD (P-series)
                if disk_size_gb <= 4: value = "P1"
                elif disk_size_gb <= 8: value = "P2"
                elif disk_size_gb <= 16: value = "P3"
                elif disk_size_gb <= 32: value = "P4"
                elif disk_size_gb <= 64: value = "P6"
                elif disk_size_gb <= 128: value = "P10"
                elif disk_size_gb <= 256: value = "P15"
                elif disk_size_gb <= 512: value = "P20"
                elif disk_size_gb <= 1024: value = "P30"
                elif disk_size_gb <= 2048: value = "P40"
                elif disk_size_gb <= 4096: value = "P50"
                elif disk_size_gb <= 8192: value = "P60"
                elif disk_size_gb <= 16384: value = "P70"
                elif disk_size_gb <= 32767: value = "P80"
            elif "StandardSSD" in storage_type:
                # Standard SSD (E-series)
                if disk_size_gb <= 4: value = "E1"
                elif disk_size_gb <= 8: value = "E2"
                elif disk_size_gb <= 16: value = "E3"
                elif disk_size_gb <= 32: value = "E4"
                elif disk_size_gb <= 64: value = "E6"
                elif disk_size_gb <= 128: value = "E10"
                elif disk_size_gb <= 256: value = "E15"
                elif disk_size_gb <= 512: value = "E20"
                elif disk_size_gb <= 1024: value = "E30"
                elif disk_size_gb <= 2048: value = "E40"
                elif disk_size_gb <= 4096: value = "E50"
                elif disk_size_gb <= 8192: value = "E60"
                elif disk_size_gb <= 16384: value = "E70"
                elif disk_size_gb <= 32767: value = "E80"
            elif "Standard_LRS" in storage_type or "Standard_ZRS" in storage_type:
                # Standard HDD (S-series)
                if disk_size_gb <= 32: value = "S4"
                elif disk_size_gb <= 64: value = "S6"
                elif disk_size_gb <= 128: value = "S10"
                elif disk_size_gb <= 256: value = "S15"
                elif disk_size_gb <= 512: value = "S20"
                elif disk_size_gb <= 1024: value = "S30"
                elif disk_size_gb <= 2048: value = "S40"
                elif disk_size_gb <= 4096: value = "S50"
                elif disk_size_gb <= 8192: value = "S60"
                elif disk_size_gb <= 16384: value = "S70"
                elif disk_size_gb <= 32767: value = "S80"
        
        return value
    
    def extract_region(self, resource_type: str, config: Dict[str, Any]) -> Optional[str]:
        """
        Extract region information from resource configuration.
        
        Args:
            resource_type: Terraform resource type
            config: Resource configuration attributes
            
        Returns:
            Region string or None
        """
        mapping = self.get_mapping(resource_type)
        if not mapping:
            return None
        
        region_attribute = mapping.get("region_attribute", "location")
        return config.get(region_attribute)
    
    def normalize_region(self, terraform_location: str) -> str:
        """
        Normalize Terraform location to Azure armRegionName.
        
        Args:
            terraform_location: Terraform location (e.g., "East US", "eastus")
            
        Returns:
            Normalized region name for API queries
        """
        # Remove spaces and convert to lowercase
        normalized = terraform_location.lower().replace(" ", "")
        return normalized
