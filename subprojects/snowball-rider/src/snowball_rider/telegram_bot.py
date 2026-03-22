"""Telegram bot — /status, /kill, /unkill, /close, /report, /help."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import structlog

from . import executor, state, notify, feeds
from .indicators import compute_ema, compute_rsi

log = structlog.get_logger(__name__)

DATA_DIR = Path("data")


class TelegramBot:
    def __init__(self, shutdown: threading.Event) -> None:
        self._shutdown = shutdown
        self._token = os.environ.get("SCALPER_BOT_TOKEN", "")
        self._chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self._offset = 0

    def _send(self, text: str) -> None:
        if not self._token or not self._chat_id:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception:
            pass

    def _cmd_status(self) -> str:
        try:
            pos = state.get_open_position()
            wallet = executor.get_wallet_balance()
            killed = state.get_config("killed") == "true"

            lines = [f"<b>Snowball Rider</b>"]
            lines.append(f"Wallet: ${wallet:,.2f}")
            lines.append(f"Kill: {'ON' if killed else 'OFF'}")

            if pos:
                ep = executor.get_position("BTCUSDT", position_side=pos["side"])
                mark = float(ep["markPrice"]) if ep else 0
                pnl = float(ep.get("unRealizedProfit", 0)) if ep else 0
                lines.append(f"\nBTCUSDT {pos['side']} {pos['leverage']}x")
                lines.append(f"Entry: ${pos['entry_price']:.4f}")
                lines.append(f"Mark: ${mark:.4f}")
                lines.append(f"PnL: ${pnl:+.2f}")
            else:
                lines.append("\nNo position")
            return "\n".join(lines)
        except Exception as e:
            return f"Status error: {e}"

    def _cmd_kill(self) -> str:
        state.set_config("killed", "true")
        return "Kill switch ON — new entries blocked"

    def _cmd_unkill(self) -> str:
        state.set_config("killed", "false")
        return "Kill switch OFF — trading resumed"

    def _cmd_close(self) -> str:
        pos = state.get_open_position()
        if not pos:
            return "No position to close"
        side = "SELL" if pos["side"] == "LONG" else "BUY"
        try:
            # Get current mark price for accurate PnL tracking
            ep = executor.get_position("BTCUSDT", position_side=pos["side"])
            mark = float(ep["markPrice"]) if ep else 0
            entry = pos["entry_price"]
            lev = pos["leverage"]
            pnl_pct = 0.0
            if entry > 0 and mark > 0:
                pnl_pct = ((mark / entry - 1) if pos["side"] == "LONG" else (entry / mark - 1)) * 100 * lev
            close_qty = abs(float(ep.get("positionAmt", 0))) if ep else pos["qty"]
            if close_qty <= 0:
                close_qty = pos["qty"]
            executor.place_market_order("BTCUSDT", side, pos["side"], close_qty)
            state.close_position(pos["id"], mark if mark > 0 else entry, pnl_pct)
            return f"Closed {pos['side']} {close_qty} BTCUSDT @ ${mark:.2f} PnL {pnl_pct:+.1f}%"
        except Exception as e:
            return f"Close failed: {e}"

    def _cmd_report(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = DATA_DIR / f"trades-{today}.jsonl"
        if not path.exists():
            return "No trades today"
        trades = []
        with path.open() as f:
            for line in f:
                trades.append(json.loads(line))
        entries = [t for t in trades if t["event_type"] == "entry"]
        exits = [t for t in trades if t["event_type"] == "exit"]
        total_pnl = sum(t.get("pnl", 0) for t in exits)
        return f"Today: {len(entries)} entries, {len(exits)} exits, PnL ${total_pnl:+.2f}"

    def _daily_report(self) -> str:
        """Daily report: wallet, position, indicators, conditions."""
        lines = ["<b>Daily Report</b>"]

        # Wallet
        wallet = executor.get_wallet_balance()
        lines.append(f"Wallet: ${wallet:,.2f}")

        # Position
        pos = state.get_open_position()
        if pos:
            ep = executor.get_position("BTCUSDT", position_side=pos["side"])
            mark = float(ep["markPrice"]) if ep else 0
            pnl = float(ep.get("unRealizedProfit", 0)) if ep else 0
            entry = pos["entry_price"]
            lev = pos["leverage"]
            pnl_pct = ((mark / entry - 1) if pos["side"] == "LONG" else (entry / mark - 1)) * 100 * lev if entry > 0 else 0
            lines.append(f"\nBTCUSDT {pos['side']} {lev}x")
            lines.append(f"Entry ${entry:.4f} -> ${mark:.4f}")
            lines.append(f"PnL ${pnl:+.2f} ({pnl_pct:+.1f}%)")
        else:
            lines.append("\nNo position")

        # Indicators
        closes = feeds.get_daily_closes(250)
        if len(closes) >= 30:
            ema10 = compute_ema(closes, 10)
            ema26 = compute_ema(closes, 26)
            rsi21 = compute_rsi(closes, 21)
            i = len(closes) - 1
            e10 = ema10[i] or 0
            e26 = ema26[i] or 0
            r = rsi21[i] or 0
            price = closes[i]
            cross = "Golden" if e10 > e26 else "Dead"

            lines.append(f"\nEMA10/26 [{cross}]")
            lines.append(f"RSI(21) {r:.1f}")

            if e10 > e26:
                met = sum([e10 > e26, r > 45])
                lines.append(f"LONG {met}/2 conditions")
            else:
                met = sum([e10 < e26, r < 55])
                lines.append(f"SHORT {met}/2 conditions")

        # Today trades
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = DATA_DIR / f"trades-{today}.jsonl"
        if path.exists():
            trades = [json.loads(l) for l in path.read_text().strip().split("\n") if l]
            entries = sum(1 for t in trades if t["event_type"] == "entry")
            exits = sum(1 for t in trades if t["event_type"] == "exit")
            lines.append(f"\nToday: {entries} entries, {exits} exits")
        else:
            lines.append("\nToday: no trades")

        return "\n".join(lines)

    def _cmd_help(self) -> str:
        return (
            "/status — Position & balance\n"
            "/kill — Block new entries\n"
            "/unkill — Resume trading\n"
            "/close — Close all positions\n"
            "/report — Today's P&L\n"
            "/help — This message"
        )

    def _handle(self, text: str) -> str | None:
        cmd = text.strip().split()[0].lower()
        return {
            "/status": self._cmd_status,
            "/kill": self._cmd_kill,
            "/unkill": self._cmd_unkill,
            "/close": self._cmd_close,
            "/report": self._cmd_report,
            "/help": self._cmd_help,
        }.get(cmd, lambda: None)()

    def run(self) -> None:
        if not self._token:
            log.warning("telegram_bot_disabled")
            return
        log.info("telegram_bot_started")
        self._last_daily_report = ""
        self._last_hourly_report = ""
        while not self._shutdown.is_set():
            now_utc = datetime.now(timezone.utc)
            today_key = now_utc.strftime("%Y-%m-%d")
            hour_key = now_utc.strftime("%Y-%m-%d-%H")

            # Daily report at 09:00 KST (00:00 UTC)
            if now_utc.hour == 0 and self._last_daily_report != today_key:
                try:
                    self._send(self._daily_report())
                    self._last_daily_report = today_key
                    log.info("daily_report_sent")
                except Exception:
                    pass

            # Hourly status
            if self._last_hourly_report != hour_key:
                self._last_hourly_report = hour_key
                try:
                    self._send(self._cmd_status())
                    log.info("hourly_report_sent")
                except Exception as e:
                    log.error("hourly_report_failed", error=str(e))
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{self._token}/getUpdates",
                    params={"offset": self._offset, "timeout": 30},
                    timeout=35,
                )
                for update in r.json().get("result", []):
                    self._offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    if chat_id != self._chat_id:
                        continue
                    text = msg.get("text", "")
                    if text.startswith("/"):
                        reply = self._handle(text)
                        if reply:
                            self._send(reply)
            except Exception:
                self._shutdown.wait(5)
