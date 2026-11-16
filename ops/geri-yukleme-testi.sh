#!/usr/bin/env bash
# Geri yükleme testi (sunucuda çalışır). Canlı veritabanına DOKUNMAZ.
# En yeni (ya da verilen) yedeği geçici, ağsız bir PostgreSQL konteynerine yükler,
# canlı veritabanıyla şema ve kayıt sayılarını karşılaştırır, sonra konteyneri siler.
# Kullanım: geri-yukleme-testi.sh [yedek.sql.gz]
set -euo pipefail

TWENTY_DIR="${TWENTY_DIR:-$HOME/twenty}"
HEDEF="${YEDEK_DIR:-$TWENTY_DIR/backups/gunluk}"
DB_CONTAINER="${DB_CONTAINER:-twenty-db-1}"
YEDEK="${1:-$(ls -1t "$HEDEF"/db-*.sql.gz | head -1)}"
TEST="twenty-geri-yukleme-testi"
IMAJ="$(docker inspect "$DB_CONTAINER" --format '{{.Config.Image}}')"

temizle() { docker rm -f "$TEST" >/dev/null 2>&1 || true; }
trap temizle EXIT
temizle

echo "Yedek: $YEDEK"
docker run -d --name "$TEST" --network none -e POSTGRES_PASSWORD="$(head -c 18 /dev/urandom | base64)" "$IMAJ" >/dev/null
for _ in $(seq 60); do docker exec "$TEST" pg_isready -U postgres -q && break; sleep 1; done

# "role postgres already exists" hatası beklenir; diğer hataları say
HATA="$(zcat "$YEDEK" | docker exec -i "$TEST" psql -U postgres -q -v ON_ERROR_STOP=0 2>&1 >/dev/null \
  | grep -E '^(psql:.*)?ERROR' | grep -v 'role "postgres" already exists' || true)"
[[ -n "$HATA" ]] && { echo "Geri yüklemede hata:"; echo "$HATA" | head -20; }

SAYIM="
select n.nspname||'.'||c.relname||'='||(xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', n.nspname, c.relname), false, true, '')))[1]::text
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where c.relkind='r' and (n.nspname='core' or n.nspname like 'workspace_%' or n.nspname='metadata')
order by 1;"

canli="$(docker exec "$DB_CONTAINER" psql -U postgres -d default -tAc "$SAYIM")"
test="$(docker exec "$TEST" psql -U postgres -d default -tAc "$SAYIM")"

tablo=$(echo "$canli" | grep -c . || true)
echo "Karşılaştırılan tablo: $tablo"
if diff <(echo "$canli") <(echo "$test") >/tmp/geri-yukleme-fark.$$; then
  echo "SONUÇ: BAŞARILI (tüm tablolar ve kayıt sayıları canlıyla aynı)"
  rm -f /tmp/geri-yukleme-fark.$$
else
  echo "SONUÇ: FARK VAR (yedekten sonra canlıda değişiklik olduysa beklenir):"
  head -40 /tmp/geri-yukleme-fark.$$; rm -f /tmp/geri-yukleme-fark.$$
fi
[[ -z "$HATA" ]] || exit 1
