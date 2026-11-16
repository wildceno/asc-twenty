#!/usr/bin/env python3
"""Rakip sözleşme yenileme hatırlatması (liste 11, kullanıcı kararı 13 Kas 2026).

Rakip Hizmeti'nin Sözleşme Bitişi'ne N gün kala (CRM Ayarı, varsayılan 90) şirketin Account Manager'ına (yoksa Pre-sales,
yoksa Admin) bir kez görev açılır; fırsat açılmaz. Görevi hesap motoru açar (takip paketi): Rakip Hizmeti betikle
oluşturulduğu için alan kimlikleri kuruluma göre değişir, kodla tanımlı bir iş akışı taşınamazdı. Idempotent.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import KEY_FILE, URL, ensure_field, load_objects  # noqa: E402

O = load_objects()
ensure_field(O, "crmSetting", "competitorRenewalDays", "NUMBER", "Rakip Yenileme Hatırlatma (gün)")
ensure_field(O, "competitorService", "renewalRemindedFor", "DATE", "Hatırlatılan Bitiş", read_only=True)

# Mevcut ayar kaydında boşsa varsayılan 90
KOK, TOKEN = URL[: -len("/metadata")], open(KEY_FILE).read().strip()


def rest(yol, yontem="GET", govde=None):
    r = urllib.request.Request(KOK + yol, method=yontem, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read() or b"{}")


for a in rest("/rest/crmSettings?limit=5")["data"]["crmSettings"]:
    if a.get("competitorRenewalDays") is None:
        rest(f"/rest/crmSettings/{a['id']}", "PATCH", {"competitorRenewalDays": 90})
        print("varsayılan: Rakip Yenileme Hatırlatma 90 gün")
    else:
        print("var: Rakip Yenileme Hatırlatma", a["competitorRenewalDays"], "gün")
