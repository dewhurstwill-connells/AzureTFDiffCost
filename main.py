"""
Azure Terraform Cost Diff Calculator
Main orchestration script that coordinates parsing, pricing, and cost calculation.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from tfplan_parser import TerraformPlanParser
from azure_price_fetcher import AzurePriceFetcher
from resource_mapper import ResourceMapper
from cost_calculator import CostCalculator

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format=f"\033[31m%(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function."""
    try:
        logger.info("Starting Azure Terraform Cost Diff analysis...")
        
        # Initialize components
        parser = TerraformPlanParser()
        price_fetcher = AzurePriceFetcher()
        resource_mapper = ResourceMapper()
        calculator = CostCalculator(price_fetcher, resource_mapper)
        
        # Parse Terraform plan
        logger.info("Parsing plan.json...")
        resource_changes = parser.parse_plan("plan/plan.json")
        logger.info(f"Found {len(resource_changes)} resource changes")
        
        # Filter for fixed-cost resources only
        fixed_cost_changes = []
        skipped_resources = []
        
        for change in resource_changes:
            resource_type = change.get("type", "")
            # Get config for dynamic SKU checking
            config = change.get("after", change.get("before", {}))
            if resource_mapper.is_fixed_cost(resource_type, config):
                fixed_cost_changes.append(change)
            else:
                skipped_resources.append({
                    "address": change.get("address", "unknown"),
                    "type": resource_type
                })
        
        logger.info(f"Processing {len(fixed_cost_changes)} fixed-cost resources")
        logger.info(f"Skipping {len(skipped_resources)} consumption-based resources")
        
        # Calculate costs for each resource change
        cost_breakdown = []
        total_cost_impact = 0.0
        
        for change in fixed_cost_changes:
            try:
                result = calculator.calculate_cost_impact(change)
                if result:
                    cost_breakdown.append(result)
                    total_cost_impact += result.get("cost_impact", 0.0)
            except Exception as e:
                logger.error(f"Error calculating cost for {change.get('address', 'unknown')}: {e}")
                cost_breakdown.append({
                    "address": change.get("address", "unknown"),
                    "action": change.get("action", "unknown"),
                    "cost_impact": 0.0,
                    "error": str(e)
                })
        
        # Generate output file
        logger.info("Generating result.txt...")
        sign = "+" if total_cost_impact > 0 else ""
        color = "\033[31m" if total_cost_impact > 0 else "\033[32m"  # Red for positive, green for negative
        generate_output(cost_breakdown, skipped_resources, total_cost_impact, sign)
        
        logger.info("Analysis complete!")
        logger.error(f"Estimated monthly cost impact: {color}\033[1m{sign}${total_cost_impact:,.2f}\033[1m \nSee artifacts for full breakdown")

    except FileNotFoundError:
        logger.error("plan.json not found. Please ensure the Terraform plan file exists.")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in plan.json: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise


def generate_output(cost_breakdown: List[Dict], skipped_resources: List[Dict], total_cost: float, sign: str):
    """
    Generate the result.txt file with detailed cost breakdown.
    
    Args:
        cost_breakdown: List of cost calculation results per resource
        skipped_resources: List of consumption-based resources that were skipped
        total_cost: Total monthly cost impact
    """
    with open("result.txt", "w", encoding="utf-8") as f:
        # Warning
        f.write("WARNING: This calculation EXCLUDES consumption-based resources.\nOnly resources with a monthly fixed cost are included in the total.\n")
        f.write("\n")

        # Total summary
        f.write("=" * 80 + "\n")
        sign = "+" if total_cost > 0 else ""
        f.write(f"ESTIMATED MONTHLY COST IMPACT: {sign}${total_cost:,.2f}\n")
        f.write("=" * 80 + "\n\n")
        
        # Cost breakdown section
        f.write("COST BREAKDOWN BY RESOURCE\n")
        f.write("=" * 80 + "\n\n")
        
        if not cost_breakdown:
            f.write("No fixed-cost resource changes found.\n\n")
        else:
            for item in cost_breakdown:
                action = item.get("action", "UNKNOWN").upper()
                address = item.get("address", "unknown")
                cost_impact = item.get("cost_impact", 0.0)
                details = item.get("details", {})
                error = item.get("error")
                
                f.write(f"[{action}] {address}\n")
                
                # Write resource details
                if details:
                    for key, value in details.items():
                        f.write(f"  {key}: {value}\n")
                
                # Write cost impact
                if error:
                    f.write(f"  Monthly Cost: ERROR - {error}\n")
                else:
                    sign = "+" if cost_impact > 0 else ""
                    f.write(f"  Monthly Cost: {sign}${cost_impact:,.2f}\n")
                
                f.write("\n")
        
        # Skipped resources section
        if skipped_resources:
            f.write("-" * 80 + "\n")
            f.write("SKIPPED RESOURCES (Consumption-based):\n")
            f.write("-" * 80 + "\n")
            for resource in skipped_resources:
                f.write(f"  - {resource.get('address', 'unknown')} ({resource.get('type', 'unknown')})\n")
            f.write("\n")

        # Footer
        f.write("=" * 80 + "\n")
        f.write("Azure Terraform Cost Diff Report\n")
        f.write(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write("=" * 80)
        
    
    logger.info("result.txt generated successfully")


if __name__ == "__main__":
    main()
