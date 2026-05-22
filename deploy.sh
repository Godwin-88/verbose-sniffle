#!/usr/bin/env bash
# deploy.sh — One-shot setup for Job Hunter KE on a fresh Ubuntu 22.04 Vultr VPS
# Run as root: bash deploy.sh
set -euo pipefail

API_DOMAIN="${API_DOMAIN:-api.yourdomain.com}"
N8N_DOMAIN="${N8N_DOMAIN:-n8n.yourdomain.com}"
EMAIL="${DEPLOY_EMAIL:-admin@yourdomain.com}"
REPO_URL="${REPO_URL:-https://github.com/YOUR_USERNAME/jobappagent.git}"
APP_DIR="/opt/jobhunter"

echo "==> Installing system dependencies"
apt-get update -q
apt-get install -y --no-install-recommends \
    git curl ufw nginx-light certbot python3-certbot-nginx \
    ca-certificates gnupg lsb-release

echo "==> Installing Docker"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -q
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

echo "==> Configuring firewall"
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable

echo "==> Cloning repository"
git clone "$REPO_URL" "$APP_DIR" || (cd "$APP_DIR" && git pull)
cd "$APP_DIR"

echo "==> Setting up .env"
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "!! ACTION REQUIRED: Edit $APP_DIR/.env and fill in all secrets."
    echo "   Then re-run: cd $APP_DIR && bash deploy.sh --skip-install"
    echo ""
    exit 1
fi

echo "==> Patching nginx.conf with actual domains"
sed -i "s/API_DOMAIN/$API_DOMAIN/g" nginx/nginx.conf
sed -i "s/N8N_DOMAIN/$N8N_DOMAIN/g" nginx/nginx.conf

echo "==> Starting stack (HTTP only first, for Certbot challenge)"
# Temporarily serve HTTP only to get SSL certs
docker compose up -d postgres
docker compose up -d api n8n

# Start Nginx with HTTP-only config for cert issuance
docker compose up -d nginx

echo "==> Obtaining SSL certificates"
docker compose run --rm certbot certonly \
    --webroot -w /var/www/certbot \
    --non-interactive --agree-tos \
    -m "$EMAIL" \
    -d "$API_DOMAIN" -d "$N8N_DOMAIN"

echo "==> Reloading Nginx with SSL"
docker compose exec nginx nginx -s reload

echo "==> Starting certbot auto-renew"
docker compose up -d certbot

echo ""
echo "✓ Deployment complete!"
echo "  API  → https://$API_DOMAIN"
echo "  n8n  → https://$N8N_DOMAIN"
echo ""
echo "Next steps:"
echo "  1. Import your n8n workflows via the n8n UI"
echo "  2. Update VITE_API_BASE_URL=https://$API_DOMAIN in Vercel → jobappagent → Settings → Environment Variables"
echo "  3. Check logs: docker compose logs -f api"
