#!/bin/bash
# Fetch single cryptocurrency quote from CoinGecko
# Usage: ./fetch-crypto.sh bitcoin
#        ./fetch-crypto.sh ethereum

COIN_ID="${1:-bitcoin}"

# CoinGecko API (free, no key required)
DATA=$(curl -s "https://api.coingecko.com/api/v3/coins/${COIN_ID}?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false" 2>/dev/null)

# Check if request was successful
if [ -z "$DATA" ] || echo "$DATA" | grep -q '"error"'; then
  echo "{\"error\": \"Failed to fetch data for ${COIN_ID}\"}"
  exit 1
fi

# Parse and format response
echo "$DATA" | jq -c '{
  id: .id,
  symbol: .symbol,
  name: .name,
  price_usd: .market_data.current_price.usd,
  price_krw: .market_data.current_price.krw,
  change_24h: .market_data.price_change_percentage_24h,
  change_7d: .market_data.price_change_percentage_7d,
  market_cap_usd: .market_data.market_cap.usd,
  volume_24h_usd: .market_data.total_volume.usd,
  high_24h_usd: .market_data.high_24h.usd,
  low_24h_usd: .market_data.low_24h.usd,
  ath_usd: .market_data.ath.usd,
  ath_change_percent: .market_data.ath_change_percentage.usd
}' 2>/dev/null || echo "{\"error\": \"Failed to parse data for ${COIN_ID}\"}"
