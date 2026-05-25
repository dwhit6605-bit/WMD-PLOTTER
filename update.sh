#!/usr/bin/env bash
# =============================================================================
# WMD Plotter — Update Script
# Pulls latest code and restarts the service. Run as root or with sudo.
# =============================================================================
set -euo pipefail

APP_DIR="/opt/wmd-plotter"
SERVICE="wmd-plotter"

echo "=== WMD Plotter Update ==="

echo "→ Pulling latest code…"
git -C "$APP_DIR" pull

echo "→ Updating Python dependencies…"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "→ Restarting service…"
systemctl restart "$SERVICE"

echo ""
echo "✓ Done! Service status: $(systemctl is-active $SERVICE)"
echo "  Logs: journalctl -u $SERVICE -f"
echo ""
