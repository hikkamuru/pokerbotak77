#!/bin/bash
# deploy/setup.sh — первичная установка на чистый Ubuntu/Debian VPS
# Запуск: bash deploy/setup.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Determine working directory ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
log "Project directory: $PROJECT_DIR"

# ── Check .env ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    warn ".env not found — copying from .env.example"
    cp .env.example .env
    warn "Please edit .env before continuing:"
    warn "  nano $PROJECT_DIR/.env"
    read -p "Press Enter after editing .env to continue..."
fi

source .env
[ -z "$BOT_TOKEN" ] && err "BOT_TOKEN is not set in .env"
[ -z "$WEBAPP_URL" ] && err "WEBAPP_URL is not set in .env"
DOMAIN="${WEBAPP_URL#https://}"
DOMAIN="${DOMAIN#http://}"
DOMAIN="${DOMAIN%%/*}"
log "Domain: $DOMAIN"

# ── System packages ──────────────────────────────────────────────────────────
log "Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx -qq
log "System packages installed"

# ── Python venv ──────────────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    python3 -m venv venv
    log "Virtual environment created"
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
log "Python dependencies installed"

# ── Nginx ────────────────────────────────────────────────────────────────────
NGINX_CONF="/etc/nginx/sites-available/poker_bot"
sudo bash -c "cat > $NGINX_CONF" << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    location / {
        proxy_pass         http://127.0.0.1:${WEBAPP_PORT:-8080};
        proxy_http_version 1.1;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
    }
}
NGINXEOF

sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/poker_bot
sudo rm -f /etc/nginx/sites-enabled/default

# Get SSL cert
log "Obtaining SSL certificate for $DOMAIN..."
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
    -m "admin@${DOMAIN}" --redirect 2>/dev/null || \
    warn "SSL cert failed — you can run 'sudo certbot --nginx -d $DOMAIN' manually"

sudo nginx -t && sudo systemctl reload nginx
log "Nginx configured"

# ── systemd ──────────────────────────────────────────────────────────────────
CURRENT_USER="$(whoami)"
SERVICE_FILE="/etc/systemd/system/poker_bot.service"

sudo bash -c "cat > $SERVICE_FILE" << SERVICEEOF
[Unit]
Description=Poker Bot + Mini App
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python main.py
Restart=always
RestartSec=5
EnvironmentFile=$PROJECT_DIR/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable poker_bot
sudo systemctl restart poker_bot
log "systemd service installed and started"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Деплой завершён!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Статус бота:   sudo systemctl status poker_bot"
echo "  Логи:          journalctl -u poker_bot -f"
echo "  Mini App:      https://$DOMAIN"
echo ""
echo -e "${YELLOW}  Не забудь в @BotFather:${NC}"
echo "  /mybots → твой бот → Bot Settings → Menu Button"
echo "  URL: https://$DOMAIN"
echo ""
