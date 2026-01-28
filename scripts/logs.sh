#!/bin/bash

# 프로젝트 디렉토리
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_DIR="$PROJECT_DIR/data/logs"

# 로그 타입 선택
if [ "$1" = "error" ] || [ "$1" = "stderr" ]; then
    tail -f "$LOG_DIR/stderr.log"
elif [ "$1" = "all" ]; then
    tail -f "$LOG_DIR/stdout.log" "$LOG_DIR/stderr.log"
else
    tail -f "$LOG_DIR/stdout.log"
fi
