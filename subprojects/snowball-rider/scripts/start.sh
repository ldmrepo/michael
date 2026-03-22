#!/bin/bash
# Snowball Rider — Start / Restart
cd "$(dirname "$0")/.."

PID_FILE="data/snowball.pid"
LOG_FILE="data/snowball.log"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[OK] Already running (PID $OLD_PID)"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

mkdir -p data
echo "" >> "$LOG_FILE"
echo "=== Start $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG_FILE"

nohup .venv/bin/python -m snowball_rider >> "$LOG_FILE" 2>&1 &
sleep 3

if [ -f "$PID_FILE" ]; then
    echo "[START] PID $(cat "$PID_FILE")"
else
    echo "[ERROR] Failed — check $LOG_FILE"
    exit 1
fi
