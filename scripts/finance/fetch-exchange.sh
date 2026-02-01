#!/bin/bash
# Fetch exchange rate
# Usage: ./fetch-exchange.sh USD KRW
#        ./fetch-exchange.sh EUR USD

FROM="${1:-USD}"
TO="${2:-KRW}"

# Use exchangerate-api.com (free tier: 1500 requests/month)
# Alternative: use frankfurter.app (free, no key required)
DATA=$(curl -s "https://api.frankfurter.app/latest?from=${FROM}&to=${TO}" 2>/dev/null)

# Check if request was successful
if [ -z "$DATA" ] || echo "$DATA" | grep -q '"error"'; then
  # Fallback to exchangerate.host
  DATA=$(curl -s "https://api.exchangerate.host/latest?base=${FROM}&symbols=${TO}" 2>/dev/null)

  if [ -z "$DATA" ] || echo "$DATA" | grep -q '"error"'; then
    echo "{\"error\": \"Failed to fetch exchange rate for ${FROM}/${TO}\"}"
    exit 1
  fi

  # Parse exchangerate.host format
  RATE=$(echo "$DATA" | jq -r ".rates.${TO}")
  echo "{\"from\": \"${FROM}\", \"to\": \"${TO}\", \"rate\": ${RATE}, \"source\": \"exchangerate.host\"}"
  exit 0
fi

# Parse frankfurter.app format
RATE=$(echo "$DATA" | jq -r ".rates.${TO}")
DATE=$(echo "$DATA" | jq -r ".date")

echo "{\"from\": \"${FROM}\", \"to\": \"${TO}\", \"rate\": ${RATE}, \"date\": \"${DATE}\", \"source\": \"frankfurter.app\"}"
