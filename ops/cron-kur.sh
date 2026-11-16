#!/usr/bin/env bash
# Yedek cron kaydını kurar (sunucuda, idempotent). Saat başı çalışır; yedek.sh günde bir kez yedek alır.
set -euo pipefail
REPO="${REPO:-$HOME/ascendia-crm}"
SATIR="7 * * * * $REPO/ops/yedek.sh >> \$HOME/twenty/backups/gunluk/yedek.log 2>&1"
mkdir -p "$HOME/twenty/backups/gunluk"
mevcut="$(crontab -l 2>/dev/null || true)"
if grep -qF "$REPO/ops/yedek.sh" <<<"$mevcut"; then
  echo "cron kaydı zaten var"
else
  { [[ -n "$mevcut" ]] && echo "$mevcut"; echo "$SATIR"; } | crontab -
  echo "cron kaydı eklendi"
fi
crontab -l | grep -F "$REPO/ops/yedek.sh"
