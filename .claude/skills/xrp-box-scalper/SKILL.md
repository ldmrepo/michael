# XRP Box-Range Scalper (Bidirectional)

Binance Futures scalping bot that trades XRP within a defined price box range. Uses Hedge mode with simultaneous LONG and SHORT positions, each with independent state machines.

## Strategy

### LONG Side
1. Wait for price to drop to LONG entry zone ($1.36)
2. Confirm with bullish candle (close > open)
3. Enter LONG via LIMIT BUY order
4. Set server-side TP (TAKE_PROFIT limit @ $1.42) and SL (STOP_MARKET @ $1.33)

### SHORT Side
1. Wait for price to rise to SHORT entry zone ($1.44)
2. Confirm with bearish candle (close < open)
3. Enter SHORT via LIMIT SELL order
4. Set server-side TP (TAKE_PROFIT limit @ $1.38) and SL (STOP_MARKET @ $1.47)

Both sides can be active simultaneously. No RSI filter (backtest showed better performance without it).

## Parameters

| Parameter | Default | Description |
|---|---|---|
| SYMBOL | XRPUSDT | Trading pair |
| LEVERAGE | 12 | Futures leverage |
| BOX_HIGH | 1.47 | Upper bound of range |
| BOX_LOW | 1.33 | Lower bound of range |
| LONG_ENTRY | 1.36 | LONG limit buy price |
| LONG_TP | 1.42 | LONG take profit trigger |
| LONG_SL | 1.33 | LONG stop loss trigger |
| SHORT_ENTRY | 1.44 | SHORT limit sell price |
| SHORT_TP | 1.38 | SHORT take profit trigger |
| SHORT_SL | 1.47 | SHORT stop loss trigger |
| RISK_PER_TRADE_PCT | 2.0 | % of balance risked per trade |
| MARGIN_PER_SIDE_PCT | 50.0 | % of balance allocated per side |
| MAX_CONSECUTIVE_SL | 3 | SL streak before cooldown (per side) |
| COOLDOWN_3SL_SECS | 7200 | 2hr cooldown after 3 SLs |
| COOLDOWN_5SL_SECS | 43200 | 12hr cooldown after 5 SLs |
| DAILY_LOSS_LIMIT_PCT | 3.0 | Max daily drawdown % (combined both sides) |
| MAX_FUNDING_RATE | 0.0003 | Skip trade if funding > 0.03% |
| POLL_INTERVAL | 10 | Seconds between ticks |
| ORDER_TIMEOUT | 900 | Cancel unfilled entry after 15min |

## Usage

```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
python3 .claude/skills/xrp-box-scalper/scripts/xrp_box_scalper.py
```

## Required Environment Variables

- `BINANCE_API_KEY` — Binance API key with Futures trading permission
- `BINANCE_API_SECRET` — Binance API secret

## State Machine

Each side (LONG/SHORT) has an independent state machine:

```
IDLE -> ENTRY_SIGNAL -> IN_POSITION -> EXIT_EVAL -> IDLE
                                    \-> COOLDOWN -> IDLE
```

Global states that affect both sides:
- `stopped=true` — box breakout or daily loss limit (manual restart needed)

State is persisted to `/tmp/xrp_scalper_state.json`:
```json
{
    "long": {"state": "IDLE", "trade_log": [], ...},
    "short": {"state": "IN_POSITION", "trade_log": [], ...},
    "daily_start_balance": 1353,
    "stopped": false
}
```

The bot resumes from saved state on restart.

## Risk Management

- **Per-side cooldown**: 3 consecutive SLs on LONG doesn't affect SHORT (and vice versa)
- **Combined daily limit**: Total PnL across both sides triggers STOPPED
- **Box breakout**: Stops BOTH sides, market-closes any open positions
- **Position sizing**: Each side gets 50% of available margin to avoid over-leverage
- **Funding rate**: Checked independently per side before entry

## Logs

- stdout: INFO level
- `/tmp/xrp_scalper.log`: DEBUG level (all details)
- All log messages prefixed with `[LONG]` or `[SHORT]` for clarity

## Risk Warnings

- This bot trades with real money on Binance Futures with leverage
- 12x leverage amplifies both gains and losses
- Running both sides simultaneously doubles exposure within the box
- Box range parameters must be updated when market structure changes
- The bot will STOP automatically on box breakout — manual review required
- Always monitor the bot; do not run unattended without understanding the risks
- Past performance does not guarantee future results

## Dependencies

- Python 3.10+ standard library only (urllib, json, hmac, etc.)
- No third-party packages required

## Binance Hedge Mode Notes

- LONG orders use `positionSide=LONG`, entry side=`BUY`, exit side=`SELL`
- SHORT orders use `positionSide=SHORT`, entry side=`SELL`, exit side=`BUY`
- SL uses `STOP_MARKET` with `workingType=MARK_PRICE` (works for both sides)
- TP uses `TAKE_PROFIT` (limit type), NOT `TAKE_PROFIT_MARKET` (known to be broken)
- LONG TP: `price=TP*0.999` (limit slightly below stop for fill)
- SHORT TP: `price=TP*1.001` (limit slightly above stop for fill)
