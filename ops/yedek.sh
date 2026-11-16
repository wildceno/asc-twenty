#!/usr/bin/env bash
# Twenty günlük yedeği (sunucuda çalışır).
#   - Veritabanı: pg_dumpall (gzip)
#   - Ek dosyalar: server-local-data birimi (tar.gz)
#   - .env (sırlar; yalnız sunucuda, 600)
# Saatlik cron ile çağrılır; o güne ait yedek varsa hiçbir şey yapmaz
# (makine gece kapalı olabildiği için sabit saat yerine "günde bir kez").
# Kullanım: yedek.sh [--zorla]   (--zorla: bugünkü yedek olsa da yeniden al)
set -euo pipefail
umask 077

TWENTY_DIR="${TWENTY_DIR:-$HOME/twenty}"
HEDEF="${YEDEK_DIR:-$TWENTY_DIR/backups/gunluk}"
SAKLA_GUN="${SAKLA_GUN:-14}"
DB_CONTAINER="${DB_CONTAINER:-twenty-db-1}"
DOSYA_BIRIMI="${DOSYA_BIRIMI:-twenty_server-local-data}"
GUN="$(date +%F)"

mkdir -p "$HEDEF"
exec 9>"$HEDEF/.kilit"
flock -n 9 || { echo "$(date -Is) başka bir yedek çalışıyor"; exit 0; }

if [[ "${1:-}" != "--zorla" ]] && compgen -G "$HEDEF/db-$GUN-*.sql.gz" >/dev/null; then
  exit 0
fi

TAG="$(grep -E '^TAG=' "$TWENTY_DIR/.env" | cut -d= -f2)"
AD="$GUN-${TAG:-bilinmiyor}"
GECICI="$HEDEF/.db-$AD.sql.gz.tmp"

docker exec "$DB_CONTAINER" pg_dumpall -U postgres | gzip -6 > "$GECICI"

# Doğrulama: core şeması ve en az bir çalışma alanı şeması dökümde olmalı
gzip -t "$GECICI"
zgrep -q 'CREATE SCHEMA core;' "$GECICI" || { echo "HATA: core şeması yok"; rm -f "$GECICI"; exit 1; }
zgrep -qE 'CREATE SCHEMA workspace_[a-z0-9]+;' "$GECICI" || { echo "HATA: workspace şeması yok"; rm -f "$GECICI"; exit 1; }
mv "$GECICI" "$HEDEF/db-$AD.sql.gz"

docker run --rm -v "$DOSYA_BIRIMI":/veri:ro postgres:16 tar czf - -C /veri . > "$HEDEF/.dosyalar-$AD.tar.gz.tmp"
mv "$HEDEF/.dosyalar-$AD.tar.gz.tmp" "$HEDEF/dosyalar-$AD.tar.gz"

cp "$TWENTY_DIR/.env" "$HEDEF/env-$AD.bak"

# Döngü: SAKLA_GUN günden eski yedekleri sil
find "$HEDEF" -maxdepth 1 -type f \( -name 'db-*.sql.gz' -o -name 'dosyalar-*.tar.gz' -o -name 'env-*.bak' \) \
  -mtime +"$SAKLA_GUN" -delete

echo "$(date -Is) yedek tamam: db-$AD.sql.gz ($(du -h "$HEDEF/db-$AD.sql.gz" | cut -f1)), dosyalar-$AD.tar.gz"
# Sistem Durumu'na son yedek zamanı (liste 7). Twenty erişilemezse yedek yine başarılıdır; motor 26 saatte alarm açar.
python3 "$(dirname "$0")/yedek-durumu.py" || echo "$(date -Is) uyarı: Sistem Durumu güncellenemedi"
