#!/usr/bin/env python3
"""Takip Kuralları başlangıç kayıtları (nesne ve alanlar Ascendia Pano uygulamasında: src/takip/).

Kullanıcı kararı (13 Kas 2026, kararlar/2026-11-13-takip-kurallari.md): aşama bazında temassız gün eşiği,
organizasyon değiştirir, boş = kapalı. Başlangıç: Lead-Gen 7, Lead-inTouch 7, Pipeline 14, Upside 10, Commit 7.
Idempotent: yalnız eksik aşama satırı eklenir; var olan satırın gün değerine dokunulmaz (kullanıcı değiştirmiş olabilir).
Önce: apps/ascendia-pano → twenty app apply.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import KEY_FILE, URL  # noqa: E402

BASLANGIC = [("LEAD_GEN", "Lead-Gen", 7), ("LEAD_IN_TOUCH", "Lead-inTouch", 7), ("PIPELINE", "Pipeline", 14),
             ("UPSIDE", "Upside", 10), ("COMMIT", "Commit", 7)]
KOK = URL[: -len("/metadata")]
TOKEN = open(KEY_FILE).read().strip()


def rest(yol, yontem="GET", govde=None):
    r = urllib.request.Request(KOK + yol, method=yontem, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read() or b"{}")


var = {k.get("stage"): k for k in rest("/rest/followUpRules?limit=60")["data"]["followUpRules"]}
for asama, ad, gun in BASLANGIC:
    if asama in var:
        print("var:", ad, var[asama].get("days"), "gün")
        continue
    rest("/rest/followUpRules", "POST", {"name": ad, "stage": asama, "days": gun})
    print("eklendi:", ad, gun, "gün")
print("kurallar:", {k["stage"]: k.get("days") for k in rest("/rest/followUpRules?limit=60")["data"]["followUpRules"]})
