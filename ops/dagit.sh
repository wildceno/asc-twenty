#!/usr/bin/env bash
# Repoyu Mac'ten sunucuya kopyalar (varsayılan Monster, ~/ascendia-crm).
# Sunucudaki kopya elle değiştirilmez; her değişiklik bu repoda yapılıp buradan dağıtılır.
# Kullanım: ops/dagit.sh [ssh-hedefi]
set -euo pipefail
HEDEF="${1:-monster}"
KOK="$(cd "$(dirname "$0")/.." && pwd)"
rsync -a --delete --exclude .git --exclude .DS_Store --exclude __pycache__ --exclude eski/ --exclude node_modules --exclude .yarn \
  "$KOK"/ "$HEDEF":ascendia-crm/
ssh "$HEDEF" 'chmod +x ~/ascendia-crm/ops/*.sh && echo "dağıtıldı: $(hostname):~/ascendia-crm"'
