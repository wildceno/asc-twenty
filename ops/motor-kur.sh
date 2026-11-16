#!/usr/bin/env bash
# Hesap motorunu sunucuda kurar/günceller (idempotent). Önce: ops/dagit.sh
#  1. Webhook sırrı yoksa üretir (600)
#  2. Twenty'ye compose ekini koyar; değiştiyse server ve worker yeniden oluşturulur
#  3. Motoru derleyip başlatır
#  4. Twenty'de webhook yoksa oluşturur, varsa olay listesini eşitler (Admin rolü)
set -euo pipefail
TW="$HOME/twenty"; REPO="$HOME/ascendia-crm"
SIR="$TW/.hesap-motoru-webhook-secret"
umask 077
[[ -s "$SIR" ]] || { head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$SIR"; echo "webhook sırrı üretildi"; }

if ! cmp -s "$REPO/ops/twenty/docker-compose.override.yml" "$TW/docker-compose.override.yml"; then
  cp "$REPO/ops/twenty/docker-compose.override.yml" "$TW/docker-compose.override.yml"
  (cd "$TW" && docker compose up -d server worker)
  echo "Twenty compose eki uygulandı; sağlık bekleniyor"
  for _ in $(seq 60); do curl -sf localhost:3010/healthz >/dev/null && break; sleep 5; done
fi

# Portal (crm-support) anahtarı: dosya boşsa gönderim kapalı. Adres ayrı, gizli olmayan dosyada.
PORTAL_ANAHTAR="$TW/.crm-support-anahtari"; [[ -e "$PORTAL_ANAHTAR" ]] || { : > "$PORTAL_ANAHTAR"; chmod 600 "$PORTAL_ANAHTAR"; }
PORTAL_URL="$(cat "$TW/.crm-support-adresi" 2>/dev/null || true)"
# EVDS anahtarı (enflasyon öngörüsü, liste 14c): yoksa boş dosya; TRY öngörüsü alınamaz ve alarm açılır
# FRED API anahtarı (USD öngörüsü) aynı kuralla
for f in "$TW/.evds-anahtari" "$TW/.fred-anahtari" "$TW/.docusign-private-key"; do [[ -e "$f" ]] || { : > "$f"; chmod 600 "$f"; }; done
# DocuSign ayarı (liste 20): yoksa boş JSON; IMZA paketi "ayar yok" der
[[ -e "$TW/.docusign.json" ]] || { echo '{}' > "$TW/.docusign.json"; chmod 600 "$TW/.docusign.json"; }
# Paraşüt (liste 21): ayar ve sır yoksa boş; oturum klasörü motorun yazabileceği tek yer (700)
[[ -e "$TW/.parasut.json" ]] || { echo '{}' > "$TW/.parasut.json"; chmod 600 "$TW/.parasut.json"; }
[[ -e "$TW/.parasut-client-secret" ]] || { : > "$TW/.parasut-client-secret"; chmod 600 "$TW/.parasut-client-secret"; }
mkdir -p "$TW/parasut" && chmod 700 "$TW/parasut"
(cd "$REPO/motor" && UID_GID="$(id -u):$(id -g)" PORTAL_URL="$PORTAL_URL" docker compose up -d --build)

python3 - "$SIR" <<'PY'
import json, os, sys, urllib.request
key = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
secret = open(sys.argv[1]).read().strip()
def gql(q, v=None):
    r = urllib.request.Request("http://localhost:3010/metadata", method="POST",
        data=json.dumps({"query": q, "variables": v or {}}).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(r).read())
    if d.get("errors"): raise SystemExit(json.dumps(d["errors"])[:500])
    return d["data"]
URL = "http://hesap-motoru:8080/webhook"
OPS = ["opportunity.created", "opportunity.updated", "crmSetting.created", "crmSetting.updated",
       "reportingPeriod.updated", "target.created", "target.updated", "targetLine.created",
       "targetLine.updated", "targetLine.deleted", "teamMember.created", "teamMember.updated",
       "teamMember.deleted", "forecastRate.created", "forecastRate.updated",
       # Takip (13 Kas): temas, görev, görev bağlantısı ve kural değişikliklerinde yeniden hesap
       "touchpoint.created", "touchpoint.updated", "touchpoint.deleted", "task.created", "task.updated",
       "task.deleted", "taskTarget.created", "taskTarget.deleted", "followUpRule.created", "followUpRule.updated",
       # Şirket sorumluları (13 Kas, liste 12): şirkette AM / Pre-sales değişince açık fırsatlara yansır
       "company.updated",
       # Hesap Durumu (13 Kas, liste 12b): sözleşme ve yeni şirket
       "company.created", "contract.created", "contract.updated", "contract.deleted",
       # Rakip sözleşme yenileme (13 Kas, liste 11)
       "competitorService.created", "competitorService.updated",
       # Teklif (13 Kas, liste 14a)
       "quote.created", "quote.updated", "quoteLine.created", "quoteLine.updated", "quoteLine.deleted",
       "marginRule.created", "marginRule.updated", "marginRule.deleted",
       # Enflasyon öngörüsü (13 Kas, liste 14c): kayıt değişince açık teklifler yeniden hesaplanır
       "inflationForecast.created", "inflationForecast.updated", "inflationForecast.deleted",
       # Teklif şablonu (14 Kas, liste 15a): dosya yüklenince belge servisi okur
       "quoteTemplate.created", "quoteTemplate.updated",
       # E-posta temas ve cevap görevi (14 Kas, liste 19): eşitlenen posta
       "messageChannelMessageAssociation.created", "message.created", "person.created",
       # Takvim teması (15 Kas, liste 19)
       "calendarEvent.created", "calendarEvent.updated", "calendarEventParticipant.created", "calendarEventParticipant.updated"]
# quote.updated zaten listede: İmza İsteği (liste 20) onunla gelir
hooks = [w for w in gql("{ webhooks { id targetUrl operations } }")["webhooks"] if w["targetUrl"] == URL]
if hooks:
    if sorted(hooks[0]["operations"]) != sorted(OPS):
        gql("mutation($i: UpdateWebhookInput!) { updateWebhook(input: $i) { id } }",
            {"i": {"id": hooks[0]["id"], "update": {"operations": OPS}}})
        print("webhook olayları güncellendi")
    else:
        print("webhook zaten var")
else:
    role = next(r["id"] for r in gql("{ getRoles { id label } }")["getRoles"] if r["label"] == "Admin")
    gql("mutation($i: CreateWebhookInput!) { createWebhook(input: $i) { id } }",
        {"i": {"targetUrl": URL, "operations": OPS, "secret": secret, "roleId": role,
               "description": "Ascendia hesap motoru"}})
    print("webhook oluşturuldu")
PY
