"""
Azure Retail Prices API Client
Fetches pricing data from Azure Retail Prices API.
"""

import requests
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class AzurePriceFetcher:
    """Client for Azure Retail Prices API."""
    
    BASE_URL = "https://prices.azure.com/api/retail/prices"
    
    def __init__(self):
        """Initialize the price fetcher with caching."""
        self._cache: Dict[str, Any] = {}
        self.session = requests.Session()
    
    def get_price(
        self,
        service_name: str,
        region: str,
        sku_name: Optional[str] = None,
        product_name: Optional[str] = None,
        meter_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get pricing information for a specific Azure resource.
        
        Args:
            service_name: Azure service name (e.g., "Virtual Machines")
            region: Azure region (e.g., "eastus")
            sku_name: SKU name (e.g., "D2s v3")
            product_name: Product name for additional filtering
            meter_name: Meter name for additional filtering
            
        Returns:
            Pricing information dictionary or None if not found
        """
        cache_key = f"{service_name}|{region}|{sku_name}|{product_name}|{meter_name}"
        
        if cache_key in self._cache:
            logger.debug(f"Cache hit for {cache_key}")
            return self._cache[cache_key]
        
        try:
            filter_parts = [
                f"serviceName eq '{service_name}'",
                f"armRegionName eq '{region}'"
            ]
            
            if sku_name:
                filter_parts.append(f"skuName eq '{sku_name}'")
            
            if product_name:
                filter_parts.append(f"productName eq '{product_name}'")
            
            if meter_name:
                filter_parts.append(f"meterName eq '{meter_name}'")
            
            # Add filter for consumption pricing type
            filter_parts.append("priceType eq 'Consumption'")
            
            filter_query = " and ".join(filter_parts)
            
            logger.info(f"Querying Azure Retail Prices API: {filter_query}")
            
            params = {
                "$filter": filter_query
            }
            
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("Items", [])
            
            if not items:
                logger.warning(f"No pricing data found for {cache_key}")
                self._cache[cache_key] = None
                return None
            
            # Return the first matching item (could be enhanced with better selection logic)
            price_info = self._select_best_price(items)
            self._cache[cache_key] = price_info
            
            return price_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching price data: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_price: {e}")
            return None
    
    def get_prices(self, service_name: str, region: str, sku_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all consumption price items for given filters (no selection)."""
        filter_parts = [f"serviceName eq '{service_name}'", f"armRegionName eq '{region}'", "priceType eq 'Consumption'"]
        if sku_name:
            filter_parts.append(f"skuName eq '{sku_name}'")
        filter_query = " and ".join(filter_parts)
        params = {"$filter": filter_query}
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            items = data.get("Items", [])
            return [item for item in items if item.get("type") == "Consumption"]
        except Exception as e:
            logger.error(f"Error fetching prices list: {e}")
            return []
    
    def _select_best_price(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select the most appropriate price from multiple results.
        
        Args:
            items: List of price items from API response
            
        Returns:
            Best matching price item
        """
        # Filter out Reservation pricing - we only want Consumption pricing
        consumption_items = [item for item in items if item.get("type") == "Consumption"]
        
        if not consumption_items:
            # Fallback to all items if no consumption pricing found
            consumption_items = items
        
        # Override logic for Redis Cache to prefer 'Cache' meter over 'Cache Instance'
        if items and items[0].get("serviceName") == "Redis Cache":
            consumption_items = [item for item in items if item.get("type") == "Consumption"] or items
            cache_meter = [i for i in consumption_items if i.get("meterName", "").endswith("Cache") and not i.get("meterName", "").endswith("Cache Instance")]
            if cache_meter:
                # Prefer primary among cache_meter
                primary = [i for i in cache_meter if i.get("isPrimaryMeterRegion")]
                return primary[0] if primary else cache_meter[0]
        
        # Filter for primary meter region if available
        primary_items = [item for item in consumption_items if item.get("isPrimaryMeterRegion", False)]
        
        if primary_items:
            return primary_items[0]
        
        # Otherwise return the first consumption item
        return consumption_items[0]
    
    def get_monthly_cost(
        self,
        service_name: str,
        region: str,
        sku_name: Optional[str] = None,
        product_name: Optional[str] = None,
        meter_name: Optional[str] = None
    ) -> Optional[float]:
        """
        Get the monthly cost for a resource.
        
        Args:
            service_name: Azure service name
            region: Azure region
            sku_name: SKU name
            product_name: Product name
            meter_name: Meter name
            
        Returns:
            Monthly cost in USD or None if not available
        """
        price_info = self.get_price(service_name, region, sku_name, product_name, meter_name)
        
        if not price_info:
            return None
        
        retail_price = price_info.get("retailPrice", 0.0)
        unit_of_measure = price_info.get("unitOfMeasure", "").lower()
        
        # Convert to monthly cost based on unit of measure
        monthly_cost = self._convert_to_monthly(retail_price, unit_of_measure)
        
        return monthly_cost
    
    def _convert_to_monthly(self, price: float, unit_of_measure: str) -> float:
        """
        Convert price to monthly cost based on unit of measure.
        
        Args:
            price: Price per unit
            unit_of_measure: Unit of measure (e.g., "1 Hour", "1 Day", "1 Month")
            
        Returns:
            Monthly cost
        """
        unit_lower = unit_of_measure.lower()
        
        if "hour" in unit_lower:
            # 730 hours per month (365 days / 12 months * 24 hours)
            return price * 730
        elif "day" in unit_lower:
            # ~30.42 days per month
            return price * 30.42
        elif "month" in unit_lower:
            return price
        else:
            # Default to hourly if unknown
            logger.warning(f"Unknown unit of measure: {unit_of_measure}, assuming hourly")
            return price * 730
    
    def clear_cache(self):
        """Clear the pricing cache."""
        self._cache.clear()
        logger.info("Price cache cleared")
