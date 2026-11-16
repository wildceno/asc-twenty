#!/usr/bin/env python3
"""Çalışma alanı ayarı (CRM Ayarı nesnesinde tek kayıt).

Raporlama para birimi, mali yıl başlangıcı ve hedef dönemi her müşteriye göre seçilir (kullanıcı, 11 Kas 2026).
Forecast dönüşüm oranları müşteri kurulumunda elle girilir; geçmiş veri eşiği aşılınca motor geçmişe geçer.
Ascendia: USD, Ocak (M01), çeyreklik (QUARTER), eşik 20, metrik Revenue (kullanıcı, 11 Kas).
  Dönüşüm oranları VARSAYIM (kullanıcı 11 Kas: "Ascendia için sen bir şeyler giriver"; kaynak yok):
  Pipeline %20, Upside %50, Commit %80 — Commit'in büyük olasılıkla, Upside'ın kesinlik olmadan kapanacak
  fırsatlar olduğu forecast kategorisi tanımına göre sıralı tutuldu. Gerçek veriyle değiştirilmeli.
Kullanım: python3 metadata/06_calisma_alani_ayari.py --raporlama USD --mali-yil M01 --hedef-donemi QUARTER \
          --esik 20 --metrik REVENUE --oran PIPELINE=20 --oran UPSIDE=50 --oran COMMIT=80
Idempotent: kayıt yoksa oluşturur, değer farklıysa günceller.
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import KEY_FILE, URL  # noqa: E402


def rest(path, method="GET", body=None):
    with open(KEY_FILE) as fh:
        token = fh.read().strip()
    req = urllib.request.Request(URL[: -len("/metadata")] + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["data"]


p = argparse.ArgumentParser()
p.add_argument("--raporlama", required=True, choices=["TRY", "EUR", "USD", "GBP"])
p.add_argument("--mali-yil", required=True, choices=[f"M{i:02d}" for i in range(1, 13)])
p.add_argument("--hedef-donemi", required=True, choices=["MONTH", "QUARTER", "YEAR"])
p.add_argument("--metrik", required=True, choices=["REVENUE", "GROSS_PROFIT", "ARR", "MRR"],
               help="dashboard'da raporlanan değer (Ascendia: REVENUE)")
p.add_argument("--esik", type=int, required=True, help="geçmiş veriye geçiş için aşama başına kapanmış fırsat")
p.add_argument("--oran", action="append", default=[], help="AŞAMA=yüzde, ör. PIPELINE=20")
a = p.parse_args()
istenen = {"reportingCurrency": a.raporlama, "fiscalYearStartMonth": a.mali_yil, "targetPeriodType": a.hedef_donemi,
           "historyThreshold": a.esik, "reportingMetric": a.metrik}

kayitlar = rest("/rest/crmSettings?limit=10")["crmSettings"]
if len(kayitlar) > 1:
    raise SystemExit(f"{len(kayitlar)} CRM Ayarı kaydı var, tek olmalı: elle incele")
if not kayitlar:
    rest("/rest/crmSettings", "POST", {"name": "Çalışma alanı ayarı", **istenen})
    print("oluşturuldu:", istenen)
else:
    fark = {k: v for k, v in istenen.items() if kayitlar[0].get(k) != v}
    if fark:
        rest(f"/rest/crmSettings/{kayitlar[0]['id']}", "PATCH", fark)
        print("güncellendi:", fark)
    else:
        print("değişiklik yok:", istenen)

# --- Dönüşüm oranları (manuel başlangıç) ---
mevcut = {r.get("stage"): r for r in rest("/rest/forecastRates?limit=20")["forecastRates"]}
for parca in a.oran:
    asama, yuzde = parca.split("=")
    yuzde = float(yuzde)
    if asama not in mevcut:
        rest("/rest/forecastRates", "POST", {"name": asama, "stage": asama, "manualRate": yuzde})
        print("oluşturuldu: dönüşüm oranı", asama, yuzde)
    elif float(mevcut[asama].get("manualRate") or -1) != yuzde:
        rest(f"/rest/forecastRates/{mevcut[asama]['id']}", "PATCH", {"manualRate": yuzde})
        print("güncellendi: dönüşüm oranı", asama, yuzde)
    else:
        print("değişiklik yok: dönüşüm oranı", asama, yuzde)
