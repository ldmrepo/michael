#!/bin/bash
# Fetch market summary - combines key data sources
# Usage: ./fetch-market-summary.sh
# Returns: JSON object with key market indicators

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get top cryptos (faster, more reliable than stocks during rate limits)
CRYPTOS=$("$SCRIPT_DIR/fetch-cryptos.sh" 2>/dev/null | head -20)

# Get USD/KRW exchange rate
EXCHANGE=$("$SCRIPT_DIR/fetch-exchange.sh" USD KRW 2>/dev/null)

# Combine into summary
cat << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "cryptos": $CRYPTOS,
  "exchange": $EXCHANGE
}
EOF
