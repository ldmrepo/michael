#!/bin/bash
# Fetch major cryptocurrency quotes in batch
# Usage: ./fetch-cryptos.sh
# Returns: JSON array of crypto quotes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default major cryptos to fetch
COINS=(
  "bitcoin"
  "ethereum"
  "binancecoin"
  "ripple"
  "solana"
  "cardano"
  "dogecoin"
)

echo "["
first=true
for coin in "${COINS[@]}"; do
  result=$("$SCRIPT_DIR/fetch-crypto.sh" "$coin" 2>/dev/null)

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

  # CoinGecko rate limit: ~10-30 req/min for free tier
  sleep 0.5
done
echo "]"
