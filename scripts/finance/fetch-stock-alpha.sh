#!/bin/bash
# Fetch stock quote from Alpha Vantage (more reliable than Yahoo Finance)
# Usage: ./fetch-stock-alpha.sh AAPL
#        ./fetch-stock-alpha.sh IBM
#
# Rate Limit: 5 requests/minute, 500 requests/day (free tier)
# Get API key: https://www.alphavantage.co/support/#api-key

SYMBOL="${1:-AAPL}"

# Alpha Vantage API key (free tier)
# Set via environment variable or use demo key for testing
API_KEY="${ALPHA_VANTAGE_API_KEY:-demo}"

# Fetch global quote
DATA=$(curl -s "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${SYMBOL}&apikey=${API_KEY}" 2>/dev/null)

# Check for errors
if [ -z "$DATA" ]; then
  echo "{\"error\": \"Failed to fetch data for ${SYMBOL}\"}"
  exit 1
fi

# Check for API error messages
if echo "$DATA" | grep -q '"Note"'; then
  echo "{\"error\": \"Alpha Vantage rate limit exceeded\"}"
  exit 1
fi

if echo "$DATA" | grep -q '"Error Message"'; then
  echo "{\"error\": \"Invalid symbol: ${SYMBOL}\"}"
  exit 1
fi

# Check if Global Quote exists
QUOTE=$(echo "$DATA" | jq '.["Global Quote"]' 2>/dev/null)
if [ "$QUOTE" = "null" ] || [ -z "$QUOTE" ] || [ "$QUOTE" = "{}" ]; then
  echo "{\"error\": \"No data found for ${SYMBOL}\"}"
  exit 1
fi

# Parse Alpha Vantage response
echo "$DATA" | jq -c '.["Global Quote"] | {
  symbol: .["01. symbol"],
  price: (.["05. price"] | tonumber),
  previousClose: (.["08. previous close"] | tonumber),
  change: (.["09. change"] | tonumber),
  changePercent: (.["10. change percent"] | gsub("%"; "") | tonumber),
  open: (.["02. open"] | tonumber),
  high: (.["03. high"] | tonumber),
  low: (.["04. low"] | tonumber),
  volume: (.["06. volume"] | tonumber),
  latestTradingDay: .["07. latest trading day"],
  source: "alphavantage"
}' 2>/dev/null || echo "{\"error\": \"Failed to parse data for ${SYMBOL}\"}"
