#!/usr/bin/env bash
# =============================================================================
# WMD Plotter — Ubuntu 22.04 VPS Deployment Script
# Run as root or with sudo.
#
# Usage:
#   bash deploy.sh --domain your.domain.com --email you@example.com \
#                  --git-url https://github.com/you/wmd-plotter.git
#
#   --domain   Your domain name (required for HTTPS)
#   --email    Email for Let's Encrypt certificate (required with --domain)
#   --git-url  Git repo URL; clones into APP_DIR and enables update.sh
#   --port     Internal uvicorn port (default: 8000)
# =============================================================================
set -euo pipefail

PORT=8000
DOMAIN=""
EMAIL=""
GIT_URL=""
APP_USER="wmdplotter"
APP_DIR="/opt/wmd-plotter"
SERVICE="wmd-plotter"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)    PORT="$2";    shift 2 ;;
    --domain)  DOMAIN="$2";  shift 2 ;;
    --email)   EMAIL="$2";   shift 2 ;;
    --git-url) GIT_URL="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ -n "$DOMAIN" && -z "$EMAIL" ]]; then
  echo "ERROR: --email is required when --domain is set (needed for Let's Encrypt)."
  exit 1
fi

echo "=== WMD Plotter Deployment ==="
echo "Port:    $PORT"
echo "Domain:  ${DOMAIN:-<not set, nginx will use server IP>}"
echo "Git URL: ${GIT_URL:-<not set, copying from script directory>}"

# ── 1. System packages ────────────────────────────────────────────────────────
echo "→ Installing system packages…"
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv nginx curl git

# ── 2. App user ───────────────────────────────────────────────────────────────
echo "→ Creating app user…"
id -u "$APP_USER" &>/dev/null || useradd -r -s /bin/false -d "$APP_DIR" "$APP_USER"
mkdir -p "$APP_DIR"

# ── 3. Code deployment ────────────────────────────────────────────────────────
if [[ -n "$GIT_URL" ]]; then
  if [[ -d "$APP_DIR/.git" ]]; then
    echo "→ Repo already cloned — pulling latest…"
    git -C "$APP_DIR" pull
  else
    echo "→ Cloning repository into $APP_DIR…"
    git clone --depth 1 "$GIT_URL" "$APP_DIR"
  fi
else
  echo "→ Copying project files…"
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cp -r "$SCRIPT_DIR/backend"  "$APP_DIR/"
  cp -r "$SCRIPT_DIR/frontend" "$APP_DIR/"
  cp    "$SCRIPT_DIR/requirements.txt" "$APP_DIR/"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ── 4. Python virtualenv & deps ───────────────────────────────────────────────
echo "→ Installing Python dependencies…"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ── 5. Systemd service ────────────────────────────────────────────────────────
echo "→ Installing systemd service…"
cat > /etc/systemd/system/${SERVICE}.service <<EOF
[Unit]
Description=WMD Plotter — Hazmat & Plume Modeling API
After=network.target

[Service]
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}/backend
Environment="PORT=${PORT}"
ExecStart=${APP_DIR}/.venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
echo "→ Service started ($(systemctl is-active $SERVICE))"

# ── 6. Nginx reverse proxy ────────────────────────────────────────────────────
echo "→ Configuring nginx…"
SERVER_NAME=${DOMAIN:-_}

cat > /etc/nginx/sites-available/wmd-plotter <<EOF
server {
    listen 80;
    server_name ${SERVER_NAME};

    client_max_body_size 10M;

    gzip on;
    gzip_types text/plain application/json application/vnd.google-earth.kml+xml;

    location / {
        proxy_pass         http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }

    location /kml/live.kml {
        proxy_pass http://127.0.0.1:${PORT}/kml/live.kml;
        add_header Cache-Control "no-cache";
    }
}
EOF

ln -sf /etc/nginx/sites-available/wmd-plotter /etc/nginx/sites-enabled/wmd-plotter
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 7. Firewall ───────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null; then
  echo "→ Configuring UFW firewall…"
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  # Block direct access to uvicorn — all traffic must go through nginx
  ufw deny "${PORT}/tcp"
  ufw --force enable
fi

# ── 8. HTTPS via Let's Encrypt ────────────────────────────────────────────────
if [[ -n "$DOMAIN" ]]; then
  echo "→ Installing Certbot and requesting certificate for ${DOMAIN}…"
  apt-get install -y -q certbot python3-certbot-nginx
  certbot --nginx \
    -d "$DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    --redirect
  echo "→ HTTPS configured (auto-renews via certbot.timer)"
fi

# ── 9. Install update.sh ──────────────────────────────────────────────────────
if [[ -n "$GIT_URL" ]]; then
  echo "→ Installing update script at /usr/local/bin/wmd-update…"
  cat > /usr/local/bin/wmd-update <<'UPDATESCRIPT'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/wmd-plotter"
SERVICE="wmd-plotter"
echo "→ Pulling latest code…"
git -C "$APP_DIR" pull
echo "→ Updating Python dependencies…"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
echo "→ Restarting service…"
systemctl restart "$SERVICE"
echo "✓ Updated! Service: $(systemctl is-active $SERVICE)"
UPDATESCRIPT
  chmod +x /usr/local/bin/wmd-update
fi

# ── Done ──────────────────────────────────────────────────────────────────────
PROTO="http"
[[ -n "$DOMAIN" ]] && PROTO="https"
BASE="${PROTO}://${DOMAIN:-<server-ip>}"

echo ""
echo "✓ WMD Plotter deployed!"
echo ""
echo "  App:               ${BASE}/"
echo "  API docs:          ${BASE}/docs"
echo "  Live KML:          ${BASE}/kml/live.kml"
echo "  Network Link KML:  ${BASE}/kml/network.kml"
echo ""
echo "  Manage service:"
echo "    systemctl status  $SERVICE"
echo "    systemctl restart $SERVICE"
echo "    journalctl -u $SERVICE -f"
if [[ -n "$GIT_URL" ]]; then
  echo ""
  echo "  Deploy updates:"
  echo "    sudo wmd-update"
fi
echo ""
