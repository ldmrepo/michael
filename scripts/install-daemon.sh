#!/bin/bash
set -e

echo "🚀 Installing Michael Daemon..."

# 프로젝트 디렉토리
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# launchd plist 경로
PLIST_PATH="$HOME/Library/LaunchAgents/com.michael.daemon.plist"

# 데이터 디렉토리 생성
mkdir -p "$PROJECT_DIR/data/logs"
echo "✅ Created data directories"

# 빌드
echo "📦 Building project..."
cd "$PROJECT_DIR"
pnpm build

# launchd plist 생성
echo "📝 Creating launchd plist..."
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.michael.daemon</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/node</string>
        <string>$PROJECT_DIR/dist/index.js</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/data/logs/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/data/logs/stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>NODE_ENV</key>
        <string>production</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Created plist file: $PLIST_PATH"

# launchd에 로드
echo "🔄 Loading daemon..."
launchctl load "$PLIST_PATH"

echo ""
echo "🎉 Michael daemon installed successfully!"
echo ""
echo "Commands:"
echo "  launchctl list | grep michael     # Check status"
echo "  launchctl stop com.michael.daemon  # Stop daemon"
echo "  launchctl start com.michael.daemon # Start daemon"
echo "  tail -f $PROJECT_DIR/data/logs/stdout.log # View logs"
echo ""
