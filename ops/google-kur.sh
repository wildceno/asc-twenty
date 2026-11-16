#!/usr/bin/env bash
# Gmail ve Google Takvim eşitleme (liste 19). Google Cloud'da OAuth istemcisi (Web) ve test kullanıcısı hazır olmalı.
# Girdi: ~/twenty/.google-client-id (sır değil), ~/twenty/.google-client-secret (600). Adresler SERVER_URL'den.
# "Google ile giriş" (AUTH_GOOGLE_ENABLED) açılmaz: posta / takvim bağlantısını yalnız iki sağlayıcı bayrağı açar
# (v2.57.1 google-apis-oauth guard'ları, 14 Kas'ta okundu). Idempotent; .env değişirse yedeklenir, server + worker yeniden oluşur.
# Geri dönüş: iki bayrağı false yapıp betiği çalıştır ya da .env.yedek-* dosyasını geri koy.
set -euo pipefail
TW="$HOME/twenty"; ENV="$TW/.env"
ID="$(tr -d '[:space:]' < "$TW/.google-client-id")"; SIR="$(tr -d '[:space:]' < "$TW/.google-client-secret")"
URL="$(grep -E '^SERVER_URL=' "$ENV" | cut -d= -f2-)"
chmod 600 "$ENV"   # .env sır içerir (APP_SECRET, veritabanı parolası, Google secret)
YENI="$(mktemp)"; cp "$ENV" "$YENI"
ayarla() { if grep -qE "^$1=" "$YENI"; then sed -i "s|^$1=.*|$1=$2|" "$YENI"; else echo "$1=$2" >> "$YENI"; fi; }
ayarla AUTH_GOOGLE_CLIENT_ID "$ID"
ayarla AUTH_GOOGLE_CLIENT_SECRET "$SIR"
ayarla AUTH_GOOGLE_CALLBACK_URL "$URL/auth/google/redirect"
ayarla AUTH_GOOGLE_APIS_CALLBACK_URL "$URL/auth/google-apis/get-access-token"
ayarla MESSAGING_PROVIDER_GMAIL_ENABLED true
ayarla CALENDAR_PROVIDER_GOOGLE_ENABLED true
DEGISTI=0
if ! cmp -s "$YENI" "$ENV"; then cp -p "$ENV" "$ENV.yedek-$(date +%Y%m%d%H%M)"; cat "$YENI" > "$ENV"; DEGISTI=1; fi
rm -f "$YENI"
if ! cmp -s "$HOME/ascendia-crm/ops/twenty/docker-compose.override.yml" "$TW/docker-compose.override.yml"; then
  cp "$HOME/ascendia-crm/ops/twenty/docker-compose.override.yml" "$TW/docker-compose.override.yml"; DEGISTI=1
fi
if [[ $DEGISTI == 1 ]]; then
  (cd "$TW" && docker compose up -d server worker)
  for _ in $(seq 60); do curl -sf localhost:3010/healthz >/dev/null && break; sleep 5; done
fi
# Doğrulama (değer yazdırılmaz): konteynerde değişkenler dolu mu
docker exec twenty-server-1 sh -c 'for v in AUTH_GOOGLE_CLIENT_ID AUTH_GOOGLE_CLIENT_SECRET AUTH_GOOGLE_APIS_CALLBACK_URL MESSAGING_PROVIDER_GMAIL_ENABLED CALENDAR_PROVIDER_GOOGLE_ENABLED; do eval "x=\$$v"; [ -n "$x" ] && echo "$v: dolu" || echo "$v: BOŞ"; done; echo "geri dönüş adresi: $AUTH_GOOGLE_APIS_CALLBACK_URL"'
