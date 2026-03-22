#!/usr/bin/env python3
"""Backtest with risk overlay: vol targeting + monthly stop + regime filter.
Compares: baseline (no overlay) vs overlay ON."""

import sys, os, json, math
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from snowball_rider.indicators import compute_ema, compute_rsi

# Config
INITIAL = 818.0
LEV = 2
ALLOC = 0.6
SL = -70.0
TP = 20.0
FEE = 0.0005
FUND = 0.0003
EMA_F, EMA_S = 10, 26
RSI_P = 21
RSI_L, RSI_S = 45, 55
TP_EF, TP_ES, TP_CD = 7, 14, 2

# Overlay params
MONTHLY_LOSS_LIMIT = -15.0
VOL_TARGET = 0.02
ATR_THRESHOLD = 0.01


def compute_atr(highs, lows, closes, period=14):
    results = []
    for i in range(len(closes)):
        if i < 1 or i + 1 < period:
            results.append(None)
            continue
        trs = []
        for j in range(i + 1 - period, i + 1):
            if j < 1:
                trs.append(highs[j] - lows[j])
            else:
                tr = max(highs[j] - lows[j], abs(highs[j] - closes[j-1]), abs(lows[j] - closes[j-1]))
                trs.append(tr)
        results.append(sum(trs) / period)
    return results


def run(candles, overlay=False):
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    dates = [c["date"] for c in candles]
    n = len(closes)

    ema_f = compute_ema(closes, EMA_F)
    ema_s = compute_ema(closes, EMA_S)
    rsi = compute_rsi(closes, RSI_P)
    ema_tf = compute_ema(closes, TP_EF)
    ema_ts = compute_ema(closes, TP_ES)
    atr = compute_atr(highs, lows, closes, 14)

    warmup = max(EMA_S, RSI_P, TP_ES) + 1
    wallet = INITIAL
    peak = wallet
    mdd = 0.0
    in_pos = False
    side = ""
    entry = 0.0
    entry_idx = 0
    alloc = 0.0
    tp_act = False
    tp_cnt = 0
    trades = []
    month_start_wallet = wallet
    current_month = ""
    overlay_skips = {"monthly": 0, "regime": 0, "vol_adj": 0}

    for i in range(n):
        # Equity
        if in_pos:
            if side == "LONG":
                ur = ((closes[i] / entry) - 1) * 100 * LEV
            else:
                ur = ((entry / closes[i]) - 1) * 100 * LEV
            eq = (wallet - alloc) + alloc * (1 + ur / 100)
        else:
            eq = wallet
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > mdd:
            mdd = dd

        if i < warmup:
            continue
        if any(v is None for v in [ema_f[i], ema_s[i], rsi[i], ema_tf[i], ema_ts[i]]):
            continue

        # EXIT
        if in_pos:
            if side == "LONG":
                iw = ((lows[i] / entry) - 1) * 100 * LEV
                cp = ((closes[i] / entry) - 1) * 100 * LEV
            else:
                iw = ((entry / highs[i]) - 1) * 100 * LEV
                cp = ((entry / closes[i]) - 1) * 100 * LEV

            if iw <= -100:
                wallet -= alloc
                if wallet < 0: wallet = 0
                trades.append({"d": dates[i], "s": side, "pnl": -100, "w": wallet, "r": "LIQ"})
                in_pos = False; tp_act = False; tp_cnt = 0
                continue

            if iw <= SL:
                fc = FEE * LEV * 2 * 100
                np_ = SL - fc
                wallet = (wallet - alloc) + alloc * (1 + np_ / 100)
                if wallet < 0: wallet = 0
                trades.append({"d": dates[i], "s": side, "pnl": np_, "w": wallet, "r": "SL"})
                in_pos = False; tp_act = False; tp_cnt = 0
                continue

            if cp >= TP:
                tp_act = True
            if tp_act:
                cross = (side == "LONG" and ema_tf[i] < ema_ts[i]) or (side == "SHORT" and ema_tf[i] > ema_ts[i])
                if cross:
                    tp_cnt += 1
                else:
                    tp_cnt = 0
                if tp_cnt >= TP_CD:
                    fc = FEE * LEV * 2 * 100
                    np_ = cp - fc
                    wallet = (wallet - alloc) + alloc * (1 + np_ / 100)
                    trades.append({"d": dates[i], "s": side, "pnl": np_, "w": wallet, "r": "TP"})
                    in_pos = False; tp_act = False; tp_cnt = 0
                    continue

            # Funding
            wallet -= alloc * LEV * FUND
            continue

        # ENTRY
        if wallet <= 10:
            break

        # Overlay checks
        if overlay:
            # 1. Monthly loss limit
            m = dates[i][:7]
            if m != current_month:
                current_month = m
                month_start_wallet = wallet
            if month_start_wallet > 0:
                m_pnl = (wallet / month_start_wallet - 1) * 100
                if m_pnl <= MONTHLY_LOSS_LIMIT:
                    overlay_skips["monthly"] += 1
                    continue

            # 2. Regime filter
            if atr[i] is not None and closes[i] > 0:
                atr_ratio = atr[i] / closes[i]
                if atr_ratio < ATR_THRESHOLD:
                    overlay_skips["regime"] += 1
                    continue

        # Vol targeting
        vol_scale = 1.0
        if overlay and i >= 21:
            rets = [(closes[j] / closes[j-1] - 1) for j in range(i-19, i+1)]
            rv = (sum(r**2 for r in rets) / len(rets)) ** 0.5
            if rv > 0:
                vol_scale = min(1.0, VOL_TARGET / rv)
                if vol_scale < 1.0:
                    overlay_skips["vol_adj"] += 1

        if ema_f[i] > ema_s[i] and rsi[i] > RSI_L:
            alloc = wallet * ALLOC * vol_scale
            entry = closes[i]
            entry_idx = i
            side = "LONG"
            in_pos = True; tp_act = False; tp_cnt = 0
            continue

        if ema_f[i] < ema_s[i] and rsi[i] < RSI_S:
            alloc = wallet * ALLOC * vol_scale
            entry = closes[i]
            entry_idx = i
            side = "SHORT"
            in_pos = True; tp_act = False; tp_cnt = 0
            continue

    # Close open
    if in_pos and wallet > 0:
        if side == "LONG":
            cp = ((closes[-1] / entry) - 1) * 100 * LEV
        else:
            cp = ((entry / closes[-1]) - 1) * 100 * LEV
        fc = FEE * LEV * 2 * 100
        np_ = cp - fc
        wallet = (wallet - alloc) + alloc * (1 + np_ / 100)
        trades.append({"d": dates[-1], "s": side, "pnl": np_, "w": wallet, "r": "END"})

    ret = (wallet / INITIAL - 1) * 100
    years = (datetime.strptime(dates[-1], "%Y-%m-%d") - datetime.strptime(dates[warmup], "%Y-%m-%d")).days / 365.25
    cagr = ((wallet / INITIAL) ** (1 / years) - 1) * 100 if years > 0 and wallet > 0 else 0
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    calmar = cagr / mdd if mdd > 0 else 0

    return {
        "wallet": wallet, "ret": ret, "cagr": cagr, "mdd": mdd, "calmar": calmar,
        "trades": len(trades), "wins": wins, "losses": losses,
        "wr": wins / len(trades) * 100 if trades else 0,
        "avg_win": sum(t["pnl"] for t in trades if t["pnl"] > 0) / wins if wins else 0,
        "avg_loss": sum(t["pnl"] for t in trades if t["pnl"] <= 0) / losses if losses else 0,
        "trade_list": trades, "skips": overlay_skips, "years": years,
    }


def main():
    with open(os.path.join(os.path.dirname(__file__), '..', 'data', 'btcusdt_1d_klines.json')) as f:
        candles = json.load(f)
    print(f"Data: {len(candles)} candles")

    r1 = run(candles, overlay=False)
    r2 = run(candles, overlay=True)

    print(f"\n{'='*70}")
    print(f"  BACKTEST: Baseline vs Risk Overlay")
    print(f"  Initial: ${INITIAL} | Funding included | 6.5 years")
    print(f"{'='*70}")
    print(f"")
    print(f"  {'':25} {'Baseline':>12} {'+ Overlay':>12} {'Diff':>10}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
    print(f"  {'Final wallet':25} ${r1['wallet']:>11,.0f} ${r2['wallet']:>11,.0f} {(r2['wallet']/r1['wallet']-1)*100:>+9.1f}%")
    print(f"  {'CAGR':25} {r1['cagr']:>+11.1f}% {r2['cagr']:>+11.1f}% {r2['cagr']-r1['cagr']:>+9.1f}%p")
    print(f"  {'MaxDD':25} {r1['mdd']:>11.1f}% {r2['mdd']:>11.1f}% {r2['mdd']-r1['mdd']:>+9.1f}%p")
    print(f"  {'Calmar':25} {r1['calmar']:>11.2f} {r2['calmar']:>11.2f} {r2['calmar']-r1['calmar']:>+9.2f}")
    print(f"  {'Trades':25} {r1['trades']:>12} {r2['trades']:>12} {r2['trades']-r1['trades']:>+10}")
    print(f"  {'Win rate':25} {r1['wr']:>11.0f}% {r2['wr']:>11.0f}% {r2['wr']-r1['wr']:>+9.0f}%p")
    print(f"  {'Avg win':25} {r1['avg_win']:>+11.1f}% {r2['avg_win']:>+11.1f}%")
    print(f"  {'Avg loss':25} {r1['avg_loss']:>+11.1f}% {r2['avg_loss']:>+11.1f}%")

    print(f"\n  Overlay skip counts:")
    for k, v in r2["skips"].items():
        print(f"    {k}: {v}")

    # Yearly comparison
    print(f"\n  YEARLY COMPARISON")
    print(f"  {'Year':<6} {'Base$':>10} {'Overlay$':>10} {'Diff':>8}")
    y1, y2 = {}, {}
    for t in r1["trade_list"]:
        y = t["d"][:4]
        y1[y] = t["w"]
    for t in r2["trade_list"]:
        y = t["d"][:4]
        y2[y] = t["w"]
    for y in sorted(set(list(y1.keys()) + list(y2.keys()))):
        b = y1.get(y, 0)
        o = y2.get(y, 0)
        d = (o / b - 1) * 100 if b > 0 else 0
        print(f"  {y:<6} ${b:>9,.0f} ${o:>9,.0f} {d:>+7.1f}%")

    # Half-period comparison
    print(f"\n  HALF-PERIOD (overlay impact on weak period)")
    mid = len(candles) // 2
    r1h2 = run(candles[mid:], overlay=False)
    r2h2 = run(candles[mid:], overlay=True)
    print(f"  Second half baseline:  ${r1h2['wallet']:,.0f} ({r1h2['cagr']:+.1f}% CAGR, {r1h2['mdd']:.1f}% MDD)")
    print(f"  Second half overlay:   ${r2h2['wallet']:,.0f} ({r2h2['cagr']:+.1f}% CAGR, {r2h2['mdd']:.1f}% MDD)")


if __name__ == "__main__":
    main()
