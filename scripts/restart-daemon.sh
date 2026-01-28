#!/bin/bash
set -e

echo "🔄 Restarting Michael Daemon..."

# 데몬 중지
launchctl stop com.michael.daemon 2>/dev/null || true

# 잠시 대기
sleep 1

# 데몬 시작 (KeepAlive가 true이므로 자동으로 재시작됨)
echo "✅ Daemon will restart automatically"

# 상태 확인
sleep 2
if launchctl list | grep -q "com.michael.daemon"; then
    echo "✅ Daemon is running"
else
    echo "❌ Daemon is not running"
    exit 1
fi
