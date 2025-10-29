# Azure Terraform Cost Diff

A Python tool that analyzes Terraform plan files to calculate the cost impact of Azure infrastructure changes using the Azure Retail Prices API. Unlike Infracost, this tool focuses exclusively on **fixed-cost resources**, excluding consumption-based resources.

## Features

- **Comprehensive Resource Coverage**: Supports **102+ Azure resource types** including:
  - Compute: VMs, VM Scale Sets, AKS, Container Instances, Batch, Spring Apps
  - Databases: SQL, PostgreSQL, MySQL, MariaDB, Redis Cache, Managed Instances
  - Networking: Load Balancers, App Gateway, Firewall, VPN Gateway, NAT Gateway, Bastion
  - Storage: Managed Disks (with automatic size-to-SKU mapping)
  - Web & Mobile: App Service Plans, Static Web Apps
  - Integration: API Management, Service Bus, Event Hubs, SignalR
  - Analytics & AI: Databricks, Synapse, HDInsight, Cognitive Services, ML Workspaces
  - And many more...

- **Intelligent SKU Transformations**: Automatically converts Terraform SKU names to Azure API format
  - VM size normalization: `Standard_D2s_v3` → `D2s v3`
  - App Service version formatting: `P1v2` → `P1 v2`
  - Database vCore extraction: `B_Gen5_1` → `1 vCore`
  - Disk size-to-SKU mapping: 128GB → `P10` (Premium), `E10` (Standard SSD), or `S10` (Standard HDD)
  - Redis family + capacity: `family=P, capacity=1` → `P1`

- **Multi-Instance Resource Handling**: Correctly prices resources with multiple instances
  - Redis Cache: Premium/Standard = 2 nodes, Basic = 1 node
  - AKS: VM price × node_count
  - VM Scale Sets: VM price × instances

- **Smart Consumption Detection**: Automatically filters out consumption-based resources
  - FlexConsumption App Service Plans (FC* SKUs)
  - Storage Accounts, Function Apps, Serverless
  - Cosmos DB, Application Insights, Log Analytics
  - And properly classifies 21+ consumption resource types

- **Fallback Handling**: Infers service names for unmapped resources with warnings
- **Detailed Cost Breakdown**: Shows per-resource impact with SKU, location, hourly/monthly costs
- **Real-time Azure Pricing**: Queries the official [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
- **Action-Based Costing**: Handles create (+cost), delete (-cost), update (delta), and replace actions

See [SKU_TRANSFORMATIONS.md](Docs/SKU_TRANSFORMATIONS.md) for complete transformation reference.

## Installation

### Prerequisites

- Python 3.7 or higher
- `pip` package manager

### Setup

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install requests
```

## Usage

### 1. Generate Terraform Plan JSON

First, create a Terraform plan in JSON format:

```bash
# Initialize Terraform
terraform init

# Create plan
terraform plan -out=tfplan

# Convert to JSON
terraform show -json tfplan > plan.json
```

Move the plan.json to the Plan folder.

### 2. Run the Cost Analysis

```bash
python main.py
```

### 3. View Results

The tool generates `result.txt` with detailed cost breakdown:

```
================================================================================
Azure Terraform Cost Diff Report
Generated: 2025-10-27 10:30:00 UTC
Terraform Plan: plan.json
================================================================================

COST BREAKDOWN BY RESOURCE
================================================================================

[CREATE] azurerm_linux_virtual_machine.web_server
  Resource Type: azurerm_linux_virtual_machine
  Location: eastus
  SKU: Standard_D2s_v3
  Service Name: Virtual Machines
  Monthly Cost: +$70.08

[DELETE] azurerm_windows_virtual_machine.old_server
  Resource Type: azurerm_windows_virtual_machine
  Location: westus
  SKU: Standard_B2s
  Service Name: Virtual Machines
  Monthly Cost: -$30.37

--------------------------------------------------------------------------------
SKIPPED RESOURCES (Consumption-based):
  - azurerm_storage_account.logs (azurerm_storage_account)
  - azurerm_function_app.processor (azurerm_function_app)

================================================================================
TOTAL MONTHLY COST IMPACT: +$39.71
================================================================================
```

### Customizing Resource Mappings

Edit `resource_mapping.json` to add or modify resource mappings:

```json
{
  "azurerm_resource_type": {
    "azure_service_name": "Service Name for API",
    "cost_type": "fixed|consumption|mixed",
    "sku_attribute": "terraform_attribute_name",
    "region_attribute": "location",
    "description": "Human-readable description"
  }
}
```

## How It Works

1. **Parse**: Reads `plan.json` and extracts `resource_changes`
2. **Filter**: Identifies fixed-cost resources using `resource_mapping.json`
3. **Map**: Maps Terraform resource types to Azure service names
4. **Query**: Fetches prices from Azure Retail Prices API
5. **Calculate**: Computes monthly cost impact per resource:
   - **CREATE**: Add monthly cost (+)
   - **DELETE**: Subtract monthly cost (-)
   - **UPDATE**: Calculate delta (new - old)
   - **REPLACE**: Calculate delta (new - old)
6. **Report**: Generates detailed breakdown in `result.txt`

## API Reference

### Azure Retail Prices API

- **Endpoint**: `https://prices.azure.com/api/retail/prices`
- **Documentation**: [Azure Retail Prices API Docs](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
- **Rate Limits**: No authentication required, public API
- **Pricing**: Pay-as-you-go (Consumption) pricing used

### Query Example

```
GET https://prices.azure.com/api/retail/prices?$filter=serviceName eq 'Virtual Machines' and armRegionName eq 'eastus' and skuName eq 'D2s v3'
```

## Limitations

- **Azure Only**: Only supports Azure (`azurerm`) provider
- **Fixed Costs Only**: Excludes consumption-based resources
- **Estimates**: Prices are estimates based on pay-as-you-go rates
- **No Discounts**: Does not account for:
  - Reserved instances
  - Spot pricing
  - Enterprise agreements
  - Hybrid benefit
  - Promotional discounts
- **Monthly Calculation**: Assumes 730 hours/month for hourly-priced resources
- **USD Only**: Prices returned in USD

## Development

For detailed development guidance, see `INDEX.md`.

### Running Tests

```bash
# Create a sample plan.json file for testing
# Then run:
python main.py
```

### Logging

Set logging level by modifying `main.py`:

```python
logging.basicConfig(level=logging.DEBUG)  # For verbose output
```

## Troubleshooting

### No pricing data found

- Verify resource is in `resource_mapping.json`
- Check that region name is correct (lowercase, no spaces)
- Ensure SKU name matches Azure naming conventions

### Empty plan.json

- Ensure you've generated the plan with `terraform show -json`
- Verify JSON is valid

### Import errors

```bash
pip install requests
```

## Contributing

1. Add new resource mappings to `resource_mapping.json`
2. Test with real Terraform plans
3. Document any limitations

## License

This project is provided as-is for educational and operational use.

## References

- [Terraform JSON Output Format](https://www.terraform.io/docs/internals/json-format.html)
- [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
- [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
- [Infracost](https://www.infracost.io/) (inspiration)

## Support

For issues or questions, refer to `AGENT_GUIDE.md` for detailed implementation guidance.
