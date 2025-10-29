# SKU Transformation Reference

This document explains how the DiffCost tool transforms Terraform resource SKU names into Azure Retail Prices API-compatible formats.

## Overview

Different Azure services use different naming conventions between Terraform and the Azure Pricing API. This tool automatically applies transformations to ensure accurate price lookups.

## Transformation Types

### 1. `strip_standard_prefix`

**Used for:** Virtual Machines, VM Scale Sets, AKS node pools

**Transformation:**
- Removes `Standard_` prefix
- Replaces underscores with spaces

**Examples:**
```
Terraform                  → Azure API
----------------------------------------
Standard_D2s_v3           → D2s v3
Standard_B2ms             → B2ms
Standard_E4s_v5           → E4s v5
Standard_F8s_v2           → F8s v2
```

**Applicable Resources:**
- `azurerm_linux_virtual_machine`
- `azurerm_windows_virtual_machine`
- `azurerm_virtual_machine`
- `azurerm_linux_virtual_machine_scale_set`
- `azurerm_windows_virtual_machine_scale_set`
- `azurerm_kubernetes_cluster` (node pool VMs)
- `azurerm_kubernetes_cluster_node_pool`

---

### 2. `app_service_sku`

**Used for:** App Service Plans

**Transformation:**
- Adds space between SKU name and version
- Handles versioned and non-versioned SKUs

**Examples:**
```
Terraform    → Azure API
-------------------------
P1v2         → P1 v2
P1v3         → P1 v3
P2v2         → P2 v2
S1           → S1
B1           → B1
```

**Applicable Resources:**
- `azurerm_service_plan`
- `azurerm_app_service_plan`

**Special Handling:**
- FlexConsumption SKUs (FC*) are marked as consumption-based and excluded from fixed cost calculations
- Consumption SKUs (Y1, Dynamic) are also excluded

---

### 3. `redis`

**Used for:** Azure Redis Cache

**Transformation:**
- Combines `family` + `capacity` attributes
- Determines node count based on family

**Examples:**
```
Terraform Config              → Azure API  | Node Count
----------------------------------------------------------
family = "P", capacity = 1    → P1          | 2 nodes
family = "C", capacity = 2    → C2          | 2 nodes
family = "B", capacity = 0    → B0          | 1 node
```

**Node Count Logic:**
- **P (Premium)**: 2 nodes (primary + replica)
- **C (Standard)**: 2 nodes (primary + replica)
- **B (Basic)**: 1 node (no replication)

**Cost Calculation:**
The API returns the per-cluster price. If a per-instance meter is found, it's multiplied by the node count.

**Applicable Resources:**
- `azurerm_redis_cache`

---

### 4. `postgresql_sku` / `mysql_sku`

**Used for:** PostgreSQL and MySQL Servers

**Transformation:**
- Extracts vCore count from tier-based SKU names
- Converts generation-specific names to vCore-based pricing

**Examples:**
```
Terraform        → Azure API
-----------------------------
B_Gen5_1         → 1 vCore
B_Gen5_2         → 2 vCore
GP_Gen5_4        → 4 vCore
GP_Gen5_8        → 8 vCore
MO_Gen5_16       → 16 vCore
```

**SKU Format:** `{Tier}_Gen{Generation}_{vCores}`
- Tier: B (Basic), GP (General Purpose), MO (Memory Optimized)
- Generation: Gen4, Gen5
- vCores: 1, 2, 4, 8, 16, 32, 64

**Applicable Resources:**
- `azurerm_postgresql_server`
- `azurerm_postgresql_flexible_server`
- `azurerm_mysql_server`
- `azurerm_mysql_flexible_server`

---

### 5. `disk_sku`

**Used for:** Managed Disks

**Transformation:**
- Maps disk size (GB) to Azure SKU tier
- Different tiers based on storage type

**Examples:**
```
Storage Type         Disk Size   → Azure SKU
---------------------------------------------
Premium_LRS          128 GB      → P10
Premium_LRS          512 GB      → P20
Premium_LRS          1024 GB     → P30
StandardSSD_LRS      256 GB      → E15
StandardSSD_LRS      512 GB      → E20
Standard_LRS         128 GB      → S10
Standard_LRS         512 GB      → S20
```

**SKU Mapping Tables:**

#### Premium SSD (P-series)
| Size Range | SKU |
|------------|-----|
| ≤ 4 GB     | P1  |
| ≤ 8 GB     | P2  |
| ≤ 16 GB    | P3  |
| ≤ 32 GB    | P4  |
| ≤ 64 GB    | P6  |
| ≤ 128 GB   | P10 |
| ≤ 256 GB   | P15 |
| ≤ 512 GB   | P20 |
| ≤ 1024 GB  | P30 |
| ≤ 2048 GB  | P40 |
| ≤ 4096 GB  | P50 |
| ≤ 8192 GB  | P60 |
| ≤ 16384 GB | P70 |
| ≤ 32767 GB | P80 |

#### Standard SSD (E-series)
| Size Range | SKU |
|------------|-----|
| ≤ 4 GB     | E1  |
| ≤ 8 GB     | E2  |
| ≤ 16 GB    | E3  |
| ≤ 32 GB    | E4  |
| ≤ 64 GB    | E6  |
| ≤ 128 GB   | E10 |
| ≤ 256 GB   | E15 |
| ≤ 512 GB   | E20 |
| ≤ 1024 GB  | E30 |
| ≤ 2048 GB  | E40 |
| ≤ 4096 GB  | E50 |
| ≤ 8192 GB  | E60 |
| ≤ 16384 GB | E70 |
| ≤ 32767 GB | E80 |

#### Standard HDD (S-series)
| Size Range | SKU |
|------------|-----|
| ≤ 32 GB    | S4  |
| ≤ 64 GB    | S6  |
| ≤ 128 GB   | S10 |
| ≤ 256 GB   | S15 |
| ≤ 512 GB   | S20 |
| ≤ 1024 GB  | S30 |
| ≤ 2048 GB  | S40 |
| ≤ 4096 GB  | S50 |
| ≤ 8192 GB  | S60 |
| ≤ 16384 GB | S70 |
| ≤ 32767 GB | S80 |

**Applicable Resources:**
- `azurerm_managed_disk`
- `azurerm_snapshot`

---

## Multi-Instance Resources

Some Azure resources automatically provision multiple instances. The tool handles this by multiplying the base cost:

### Redis Cache
- **Premium (P) & Standard (C)**: 2 instances (primary + replica)
- **Basic (B)**: 1 instance (no replication)

### Kubernetes Service (AKS)
- Cost = VM price × `default_node_pool.node_count`

### VM Scale Sets
- Cost = VM price × `instances` attribute

---

## Consumption-Based Detection

The tool automatically detects and excludes consumption-based resources from fixed cost calculations:

### App Service Plans
**Consumption SKUs (excluded from fixed costs):**
- `FC*` - FlexConsumption (serverless)
- `Y1` - Consumption plan
- `Dynamic` - Dynamic SKU

**Fixed SKUs (included):**
- `B*` - Basic tier
- `S*` - Standard tier
- `P*` - Premium tier

---

## Fallback Behavior

If a resource type is not in the mapping file, the tool will:
1. Attempt to infer the service name from the resource type
2. Use common attributes (`sku`, `location`)
3. Mark the resource as `cost_type: "unknown"`
4. Log a warning with the inferred mapping

**Example:**
```
Resource Type: azurerm_new_service
Inferred Service Name: "New Service"
Recommendation: Add proper mapping to resource_mapping.json
```

---

## Adding New Transformations

To add a new SKU transformation:

1. **Define the transform in `resource_mapping.json`:**
```json
"azurerm_my_resource": {
  "azure_service_name": "My Service",
  "cost_type": "fixed",
  "sku_attribute": "sku_name",
  "sku_transform": "my_custom_transform",
  "region_attribute": "location"
}
```

2. **Implement the transform in `resource_mapper.py`:**
```python
elif transform == "my_custom_transform":
    # Custom transformation logic
    value = transform_sku(value, config)
```

3. **Test with a real resource:**
```bash
python main.py
# Verify the transformation in result.txt
```

---

## Testing SKU Transformations

Use the provided test scripts:

```bash
# Test a specific resource type
python test_all_resources.py

# Explore available SKUs for a service
python explore_api.py
```

---

## Common Issues & Solutions

### Issue: Resource shows $0.00 cost

**Possible causes:**
1. Incorrect service name mapping
2. SKU transformation not applied or incorrect
3. Region mismatch
4. SKU not available in the specified region

**Solution:**
- Check the Azure Retail Prices API directly
- Verify the service name matches exactly
- Test the SKU transformation manually
- Try a different region

### Issue: Wrong price returned

**Possible causes:**
1. Multiple meters with the same SKU name
2. Consumption vs. Reservation pricing
3. Multi-instance resources not detected

**Solution:**
- Review `azure_price_fetcher.py` price selection logic
- Check if resource should have multi-instance handling
- Verify the meter name in the API response

---

## References

- [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
- [Terraform AzureRM Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
- [Azure VM Sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes)
- [Azure Managed Disk Types](https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types)
