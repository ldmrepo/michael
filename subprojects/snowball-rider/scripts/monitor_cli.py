#!/usr/bin/env python3
"""Snowball Rider — Terminal Monitor with visual gauges"""

import os
import sys
import time
import unicodedata
import argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from dotenv import load_dotenv
load_dotenv(override=True)

W = 56
_tick = 0
_SPINNER = "|/-\\"

# ANSI colors
R = "\033[0m"   # reset
G = "\033[32m"  # green
RD = "\033[31m" # red
Y = "\033[33m"  # yellow
C = "\033[36m"  # cyan
B = "\033[1m"   # bold
D = "\033[2m"   # dim


def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r'\033\[[0-9;]*m', '', text)


def _display_width(text: str) -> int:
    """Calculate display width, stripping ANSI codes."""
    clean = _strip_ansi(text)
    w = 0
    for ch in clean:
        cat = unicodedata.east_asian_width(ch)
        w += 2 if cat in ('F', 'W') else 1
    return w


def bar(pct: float, width: int = 10) -> str:
    pct = max(0, min(100, pct))
    filled = round(pct * width / 100)
    return "█" * filled + "░" * (width - filled)


def pnl_bar(pct: float, width: int = 20) -> str:
    pct = max(-50, min(50, pct))
    mid = width // 2
    filled = round(abs(pct) * mid / 50)
    if pct >= 0:
        left = "░" * mid
        right = "█" * filled + "░" * (mid - filled)
    else:
        right = "░" * mid
        left = "░" * (mid - filled) + "█" * filled
    return f"{left}|{right}"


def row(text: str = "") -> str:
    pad = W - _display_width(text)
    return f"| {text}{' ' * max(0, pad)} |"


def sep(style: str = "mid") -> str:
    if style == "top": return "+" + "-" * (W + 2) + "+"
    if style == "bot": return "+" + "-" * (W + 2) + "+"
    return "+" + "-" * (W + 2) + "+"


def render() -> str:
    global _tick
    _tick += 1
    now = time.strftime("%H:%M:%S")
    spinner = _SPINNER[_tick % len(_SPINNER)]

    try:
        from snowball_rider import executor, state, feeds
        from snowball_rider.indicators import compute_ema, compute_rsi

        state.init_db()
        wallet = executor.get_wallet_balance()
        pos = state.get_open_position()
        killed = state.get_config("killed") == "true"
        closes = feeds.get_daily_closes(250)
    except Exception as e:
        return "\n".join([sep("top"), row(f"ERROR: {e}"), sep("bot")])

    lines = [sep("top")]
    lines.append(row(f" {spinner} {B}Snowball Rider{R}              {D}{now}{R}"))
    lines.append(sep())
    kill_txt = f"{RD}ON{R}" if killed else f"{G}OFF{R}"
    price_now = closes[-1] if closes else 0
    lines.append(row(f" BTC {B}${price_now:.4f}{R}  Wallet {B}${wallet:,.2f}{R}  Kill {kill_txt}"))

    # -- Position + PnL bar --
    lines.append(sep())
    if pos:
        ep = executor.get_position("BTCUSDT")
        mark = float(ep["markPrice"]) if ep else 0
        pnl = float(ep.get("unRealizedProfit", 0)) if ep else 0
        entry = pos["entry_price"]
        lev = pos["leverage"]
        pnl_pct = ((mark / entry - 1) if pos["side"] == "LONG" else (entry / mark - 1)) * 100 * lev if entry > 0 else 0

        side_color = G if pos["side"] == "LONG" else RD
        lines.append(row(f" BTCUSDT {side_color}{pos['side']}{R} {lev}x"))
        lines.append(row(f" Entry ${entry:.4f} -> Mark ${mark:.4f}"))
        pc = G if pnl >= 0 else RD
        lines.append(row(f" PnL {pc}${pnl:+.2f}{R} ({pc}{pnl_pct:+.1f}%{R})"))
        lines.append(row(f" {pnl_bar(pnl_pct)} {pc}{pnl_pct:+.1f}%{R}"))
        if pnl_pct >= 20:
            lines.append(row(f" {Y}>> TP watch active (20%+ reached){R}"))
    else:
        lines.append(row(f" {D}No position -- waiting{R}"))

    # -- Indicators --
    lines.append(sep())
    if len(closes) >= 30:
        ema10 = compute_ema(closes, 10)
        ema26 = compute_ema(closes, 26)
        rsi = compute_rsi(closes, 21)
        i = len(closes) - 1
        e10 = ema10[i] or 0
        e26 = ema26[i] or 0
        r = rsi[i] or 0
        price = closes[i]

        cross_name = "Golden" if e10 > e26 else "Dead"
        cross_color = G if e10 > e26 else RD
        lines.append(row(f" EMA10 ${e10:.0f} vs EMA26 ${e26:.0f} [{cross_color}{cross_name}{R}]"))

        # RSI gauge
        rsi_filled = round(r / 100 * 20)
        rsi_bar = "█" * rsi_filled + "░" * (20 - rsi_filled)
        if r > 70:
            rsi_zone = f"{RD}OVERBOUGHT{R}"
        elif r < 30:
            rsi_zone = f"{G}OVERSOLD{R}"
        else:
            rsi_zone = ""
        rsi_color = RD if r > 70 else G if r < 30 else Y if r > 55 or r < 45 else ""
        rsi_reset = R if rsi_color else ""
        lines.append(row(f" RSI {rsi_color}{r:5.1f}{rsi_reset} {rsi_bar} {rsi_zone}"))
        lines.append(row(f"          0    25   50   75  100"))

        # RSI trend (last 3 days)
        if len(rsi) >= 4:
            deltas = []
            for j in range(-3, 0):
                prev_r = rsi[j-1]
                cur_r = rsi[j]
                if prev_r is not None and cur_r is not None:
                    deltas.append(cur_r - prev_r)
            if deltas:
                avg_delta = sum(deltas) / len(deltas)
                arrow = "^" if avg_delta > 1 else "v" if avg_delta < -1 else "~"
                trend_color = G if avg_delta < -1 else RD if avg_delta > 1 else D
                lines.append(row(f" RSI trend {trend_color}{arrow} {avg_delta:+.1f}/d{R}"))

        # -- Entry conditions --
        lines.append(sep())

        def chk(ok: bool) -> str:
            return f"{G}[v]{R}" if ok else f"{D}[ ]{R}"

        if e10 > e26:
            c1 = e10 > e26
            c2 = r > 45
            met = sum([c1, c2])
            pct = met / 2 * 100
            lines.append(row(f" {G}LONG{R} entry {bar(pct, 10)} {B}{met}/2{R}"))
            gap1 = (e10 / e26 - 1) * 100
            lines.append(row(f"  {chk(c1)} EMA10>26 gap {gap1:+.1f}%"))
            lines.append(row(f"  {chk(c2)} RSI>45   {r:.0f}/45"))
        else:
            c1 = e10 < e26
            c2 = r < 55
            met = sum([c1, c2])
            pct = met / 2 * 100
            lines.append(row(f" {RD}SHORT{R} entry {bar(pct, 10)} {B}{met}/2{R}"))
            gap1 = (e26 / e10 - 1) * 100
            lines.append(row(f"  {chk(c1)} EMA10<26 gap {gap1:+.1f}%"))
            lines.append(row(f"  {chk(c2)} RSI<55   {r:.0f}/55"))
    else:
        lines.append(row(f" Need 30+ candles ({len(closes)})"))
        lines.append(row(f" {bar(len(closes)/30*100, 20)} {len(closes)}/30"))

    lines.append(sep("bot"))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    prev: list[str] = []
    os.system("clear")
    try:
        while True:
            output = render()
            lines = output.split("\n")
            buf = "\033[H"
            for line in lines:
                buf += line + "\033[K\n"
            for _ in range(max(0, len(prev) - len(lines))):
                buf += "\033[K\n"
            prev = lines
            sys.stdout.write(buf)
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
