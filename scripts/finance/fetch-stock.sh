#!/bin/bash
# Fetch single stock quote (yfinance preferred, with fallbacks)
# Usage: ./fetch-stock.sh AAPL
#        ./fetch-stock.sh 005930.KS  (Samsung Electronics)
#
# Sources (in order of priority):
# 1. yfinance (Python library - most reliable)
# 2. Yahoo Finance direct API (fallback)
# 3. Alpha Vantage (requires API key)

SYMBOL="${1:-AAPL}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# === Try yfinance (Python - most reliable) ===
try_yfinance() {
  # Check if python3 is available
  if ! command -v python3 &> /dev/null; then
    return 1
  fi

  # Check if yfinance is installed
  if ! python3 -c "import yfinance" 2>/dev/null; then
    return 1
  fi

  python3 "$SCRIPT_DIR/fetch-stock.py" "$SYMBOL" 2>/dev/null
}

# === Try Yahoo Finance direct API (fallback) ===
try_yahoo_direct() {
  local USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

  local DATA=$(curl -s -A "$USER_AGENT" \
    "https://query1.finance.yahoo.com/v7/finance/quote?symbols=${SYMBOL}" 2>/dev/null)

  if [ -z "$DATA" ] || echo "$DATA" | grep -q "Too Many"; then
    return 1
  fi

  local RESULT=$(echo "$DATA" | jq -c '.quoteResponse.result[0]' 2>/dev/null)
  if [ "$RESULT" = "null" ] || [ -z "$RESULT" ]; then
    return 1
  fi

  echo "$DATA" | jq -c '.quoteResponse.result[0] | {
    symbol: .symbol,
    name: (.shortName // .longName),
    price: .regularMarketPrice,
    previousClose: .regularMarketPreviousClose,
    change: .regularMarketChange,
    changePercent: .regularMarketChangePercent,
    currency: .currency,
    exchange: .exchange,
    marketState: .marketState,
    dayHigh: .regularMarketDayHigh,
    dayLow: .regularMarketDayLow,
    volume: .regularMarketVolume,
    marketCap: .marketCap,
    source: "yahoo-api"
  }' 2>/dev/null
}

# === Try Alpha Vantage (requires API key) ===
try_alpha_vantage() {
  # Skip for Korean stocks
  if [[ "$SYMBOL" == *".KS"* ]] || [[ "$SYMBOL" == *".KQ"* ]]; then
    return 1
  fi

  local API_KEY="${ALPHA_VANTAGE_API_KEY:-demo}"

  local DATA=$(curl -s "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${SYMBOL}&apikey=${API_KEY}" 2>/dev/null)

  if [ -z "$DATA" ] || echo "$DATA" | grep -q '"Note"' || echo "$DATA" | grep -q '"Error"'; then
    return 1
  fi

  local QUOTE=$(echo "$DATA" | jq '.["Global Quote"]' 2>/dev/null)
  if [ "$QUOTE" = "null" ] || [ -z "$QUOTE" ] || [ "$QUOTE" = "{}" ]; then
    return 1
  fi

  echo "$DATA" | jq -c '.["Global Quote"] | {
    symbol: .["01. symbol"],
    price: (.["05. price"] | tonumber),
    previousClose: (.["08. previous close"] | tonumber),
    change: (.["09. change"] | tonumber),
    changePercent: (.["10. change percent"] | gsub("%"; "") | tonumber),
    dayHigh: (.["03. high"] | tonumber),
    dayLow: (.["04. low"] | tonumber),
    volume: (.["06. volume"] | tonumber),
    source: "alphavantage"
  }' 2>/dev/null
}

# === Main: Try sources in order ===

# 1. Try yfinance (most reliable)
RESULT=$(try_yfinance)
if [ $? -eq 0 ] && [ -n "$RESULT" ] && ! echo "$RESULT" | grep -q '"error"'; then
  echo "$RESULT"
  exit 0
fi

# 2. Try Yahoo Finance direct API
RESULT=$(try_yahoo_direct)
if [ $? -eq 0 ] && [ -n "$RESULT" ] && ! echo "$RESULT" | grep -q '"error"'; then
  echo "$RESULT"
  exit 0
fi

# 3. Try Alpha Vantage
RESULT=$(try_alpha_vantage)
if [ $? -eq 0 ] && [ -n "$RESULT" ] && ! echo "$RESULT" | grep -q '"error"'; then
  echo "$RESULT"
  exit 0
fi

# All sources failed
echo "{\"error\": \"Failed to fetch data for ${SYMBOL} from all sources\"}"
exit 1
