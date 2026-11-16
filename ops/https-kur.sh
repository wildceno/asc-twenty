#!/usr/bin/env bash
# HTTPS (liste 25): Tailscale serve tailnet içinde geçerli sertifikayla Twenty'nin önünde; SERVER_URL bu adrese.
# Ön koşul (bir kez, kullanıcı): Tailscale yönetim panelinde HTTPS açık; Monster'da `sudo tailscale set --operator=$USER`.
# Idempotent. .env değişirse yedeklenir ve server + worker yeniden oluşturulur (~1 dk kesinti).
# Geri dönüş: `tailscale serve --https=443 off` ve .env.yedek-* dosyasını geri koyup `docker compose up -d server worker`.
set -euo pipefail
AD="$(tailscale status --json | python3 -c 'import sys,json; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
URL="https://$AD"
if ! tailscale serve status 2>/dev/null | grep -q "$URL"; then
  tailscale serve --bg --https=443 http://127.0.0.1:3010
fi
ENV="$HOME/twenty/.env"
if ! grep -qx "SERVER_URL=$URL" "$ENV"; then
  cp -p "$ENV" "$ENV.yedek-$(date +%Y%m%d%H%M)"
  sed -i "s|^SERVER_URL=.*|SERVER_URL=$URL|" "$ENV"
  (cd "$HOME/twenty" && docker compose up -d server worker)
  for _ in $(seq 60); do curl -sf localhost:3010/healthz >/dev/null && break; sleep 5; done
  echo "SERVER_URL değişti: $URL"
else
  echo "zaten: SERVER_URL=$URL"
fi
curl -sf -o /dev/null "$URL/healthz" && echo "HTTPS sağlıklı: $URL"
