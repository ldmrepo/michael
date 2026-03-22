"""Entry point: python -m snowball_rider [--dry-run]"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading

import structlog
from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description="Snowball Rider — BTC Trend Follower")
    parser.add_argument("--dry-run", action="store_true", help="No real orders")
    args = parser.parse_args()

    # Setup
    load_dotenv(override=True)
    structlog.configure(
        processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
        wrapper_class=structlog.stdlib.BoundLogger,
    )
    log = structlog.get_logger("main")

    # PID lock
    from . import state
    state.init_db()
    pid_file = "data/snowball.pid"
    os.makedirs("data", exist_ok=True)
    if os.path.exists(pid_file):
        old_pid = int(open(pid_file).read().strip())
        try:
            os.kill(old_pid, 0)
            print(f"Already running (PID {old_pid})", file=sys.stderr)
            sys.exit(1)
        except OSError:
            pass
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    dry_run = args.dry_run or os.environ.get("DRY_RUN", "true").lower() in ("true", "1")
    log.info("starting", dry_run=dry_run, pid=os.getpid())

    # Verify Hedge mode before any trading
    if not dry_run:
        from . import executor
        try:
            executor.check_hedge_mode()
            log.info("hedge_mode_verified")
            executor.set_leverage("BTCUSDT", 2)
        except Exception as e:
            log.error("startup_check_failed", error=str(e))
            print(f"FATAL: {e}", file=sys.stderr)
            sys.exit(1)

    shutdown = threading.Event()

    def _signal_handler(sig: int, frame: object) -> None:
        log.info("shutdown_signal", sig=sig)
        shutdown.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Start threads
    from . import feeds, strategy, monitor
    from .telegram_bot import TelegramBot

    threads = [
        threading.Thread(target=feeds.run, args=(shutdown,), name="feeds", daemon=True),
        threading.Thread(target=strategy.run_loop, args=(shutdown, 3600.0, dry_run), name="strategy", daemon=True),
        threading.Thread(target=monitor.run, args=(shutdown,), name="monitor", daemon=True),
        threading.Thread(target=TelegramBot(shutdown).run, name="telegram", daemon=True),
    ]

    for t in threads:
        t.start()
        log.info("thread_started", name=t.name)

    try:
        shutdown.wait()
    finally:
        shutdown.set()
        for t in threads:
            t.join(timeout=5)
        try:
            os.unlink(pid_file)
        except OSError:
            pass
        log.info("shutdown_complete")


if __name__ == "__main__":
    main()
