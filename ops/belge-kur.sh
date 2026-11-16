#!/usr/bin/env bash
# Belge servisini sunucuda kurar/günceller (idempotent). Önce: ops/dagit.sh
# Derler, birim testlerini konteynerde çalıştırır (başarısızsa durur), kütüphane lisanslarını yazar, başlatır.
set -euo pipefail
cd "$HOME/ascendia-crm/belge"
export UID_GID="$(id -u):$(id -g)"
docker compose build -q
docker compose run --rm --no-deps -T belge-servisi python3 -m unittest discover -s testler -t . 2>&1 | tail -3
docker compose run --rm --no-deps -T belge-servisi sh -c 'pip show python-docx python-pptx 2>/dev/null | grep -E "^(Name|Version|License):"'
docker compose up -d
for _ in $(seq 20); do docker exec belge-servisi python3 -c "import urllib.request;urllib.request.urlopen('http://localhost:8090/saglik',timeout=3)" 2>/dev/null && { echo "belge servisi sağlıklı"; exit 0; }; sleep 2; done
echo "belge servisi yanıt vermiyor"; exit 1
