#!/usr/bin/env bash
# Instala o launchd agent do daemon (macOS)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "$HERE/.." && pwd)"
PLIST_SRC="$BACKEND/launchd/com.llmwiki.daemon.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.llmwiki.daemon.plist"
mkdir -p "$HOME/llmwiki/logs" "$HOME/Library/LaunchAgents"
sed -e "s|__BACKEND__|$BACKEND|g" -e "s|__HOME__|$HOME|g" \
    "$PLIST_SRC" > "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "daemon instalado: $PLIST_DST"
