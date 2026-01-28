#!/bin/bash
set -e

echo "🛑 Uninstalling Michael Daemon..."

# launchd plist 경로
PLIST_PATH="$HOME/Library/LaunchAgents/com.michael.daemon.plist"

# launchd에서 언로드
if [ -f "$PLIST_PATH" ]; then
    echo "🔄 Unloading daemon..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    
    # plist 파일 삭제
    rm "$PLIST_PATH"
    echo "✅ Removed plist file"
else
    echo "⚠️ Daemon not found"
fi

echo ""
echo "✅ Michael daemon uninstalled successfully!"
echo ""
