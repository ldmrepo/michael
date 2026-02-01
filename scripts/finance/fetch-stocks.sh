#!/bin/bash
# Fetch major stock quotes in batch (yfinance preferred)
# Usage: ./fetch-stocks.sh
#        ./fetch-stocks.sh AAPL MSFT GOOGL  (custom symbols)
# Returns: JSON array of stock quotes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default major stocks
DEFAULT_SYMBOLS=(
  "AAPL"      # Apple
  "MSFT"      # Microsoft
  "GOOGL"     # Google
  "AMZN"      # Amazon
  "NVDA"      # NVIDIA
  "TSLA"      # Tesla
  "005930.KS" # Samsung Electronics (KRX)
)

# Use provided symbols or defaults
if [ $# -gt 0 ]; then
  SYMBOLS=("$@")
else
  SYMBOLS=("${DEFAULT_SYMBOLS[@]}")
fi

# === Try yfinance batch (most efficient) ===
try_yfinance_batch() {
  if ! command -v python3 &> /dev/null; then
    return 1
  fi

  if ! python3 -c "import yfinance" 2>/dev/null; then
    return 1
  fi

  python3 "$SCRIPT_DIR/fetch-stock.py" "${SYMBOLS[@]}" 2>/dev/null
}

# === Fallback: fetch one by one ===
fetch_individually() {
  echo "["
  first=true
  for symbol in "${SYMBOLS[@]}"; do
    result=$("$SCRIPT_DIR/fetch-stock.sh" "$symbol" 2>/dev/null)

    # Skip if error
    if echo "$result" | grep -q '"error"'; then
      continue
    fi

    if [ "$first" = true ]; then
      first=false
    else
      echo ","
    fi
    echo "$result"
  done
  echo "]"
}

# === Main ===

# Try batch fetch with yfinance first
RESULT=$(try_yfinance_batch)
if [ $? -eq 0 ] && [ -n "$RESULT" ] && ! echo "$RESULT" | grep -q '"error"'; then
  echo "$RESULT"
  exit 0
fi

# Fallback to individual fetches
fetch_individually
