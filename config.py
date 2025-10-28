# Azure Retail Prices API
AZURE_PRICES_API_URL = "https://prices.azure.com/api/retail/prices"

# Default hours per month for cost calculation
HOURS_PER_MONTH = 730  # 365 days / 12 months * 24 hours

# Request timeout in seconds
API_TIMEOUT = 30

# Cache settings
ENABLE_PRICE_CACHE = True

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Output
OUTPUT_FILE = "result.txt"
INPUT_FILE = "plan.json"

# Currency
CURRENCY_CODE = "USD"
CURRENCY_SYMBOL = "$"

# Resource filtering
INCLUDE_COST_TYPES = ["fixed", "mixed"]  # Exclude "consumption" and "free"

# Pricing preferences
# When multiple prices are available, prefer primary meter region
PREFER_PRIMARY_METER_REGION = True

# Price type filter (Consumption = pay-as-you-go, Reservation = reserved instances)
PRICE_TYPE = "Consumption"
