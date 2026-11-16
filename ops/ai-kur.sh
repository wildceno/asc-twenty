#!/usr/bin/env bash
# Twenty içi AI sohbeti (Ayarlar → AI) için Claude (Anthropic API). Kullanıcı kararı 16 Kas 2026: Ollama yerine Claude;
# kullanım başına ücretli (console.anthropic.com, harcama sınırı orada). Girdi: ~/twenty/.anthropic-api-key (600, pbpaste ile).
# Twenty v2.57.1 ai-providers.json: anthropic sağlayıcısı {{ANTHROPIC_API_KEY}} okur (16 Kas'ta okundu).
# Idempotent; .env değişirse yedeklenir, server + worker yeniden oluşur. Geri dönüş: anahtar dosyasını sil, betiği çalıştır.
set -euo pipefail
TW="$HOME/twenty"; ENV="$TW/.env"; KF="$TW/.anthropic-api-key"
ANAHTAR=""; [[ -f "$KF" ]] && ANAHTAR="$(tr -d '[:space:]' < "$KF")"
chmod 600 "$ENV"
YENI="$(mktemp)"; cp "$ENV" "$YENI"
if grep -qE "^ANTHROPIC_API_KEY=" "$YENI"; then sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$ANAHTAR|" "$YENI"; else echo "ANTHROPIC_API_KEY=$ANAHTAR" >> "$YENI"; fi
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
docker exec twenty-server-1 sh -c '[ -n "$ANTHROPIC_API_KEY" ] && echo "ANTHROPIC_API_KEY: dolu" || echo "ANTHROPIC_API_KEY: BOŞ"; [ -n "$AUTH_GOOGLE_CLIENT_ID" ] && echo "Google: dolu" || echo "Google: BOŞ"'
