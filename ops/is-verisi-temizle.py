#!/usr/bin/env python3
"""Çalışma alanındaki iş verisini KALICI siler (kullanıcı kararı 15 Kas 2026: gerçek müşteri ve kişi verisi silinsin,
tanıtım verisi kurulacak; teklif şablonu kalsın). Önce pg_dumpall yedeği alınmış olmalı. Motor durdurulmuş olmalı.

Silinen: şirket, kişi, fırsat, teklif + kalem, sözleşme + belge, temas, görev + bağlantı, not + bağlantı, rakip hizmeti,
iş ortağı, aşama geçmişi, hedef + kalem, katalogdaki ÖRNEK kalemleri; çöp kutusundakiler dahil.
Kalan: teklif şablonu ve bölümleri, katalog (ÖRNEK hariç), CRM Ayarı, dönemler, kurlar, enflasyon, marj / takip kuralları,
ekip, roller, panolar, e-posta / takvim / DocuSign bağlantıları.
Kullanım (sunucuda): python3 ops/is-verisi-temizle.py EVET-SIL
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

if sys.argv[1:] != ["EVET-SIL"]:
    sys.exit(__doc__)
K = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
SEMA = subprocess.run(["docker", "exec", "twenty-db-1", "psql", "-U", "postgres", "-d", "default", "-At", "-c",
                       "select schema_name from information_schema.schemata where schema_name like 'workspace_%'"],
                      capture_output=True, text=True, check=True).stdout.split()[0]
# (REST çoğul adı, tablo) — bağımlılık sırasıyla
SIRA = [("taskTargets", "taskTarget"), ("tasks", "task"), ("noteTargets", "noteTarget"), ("notes", "note"),
        ("touchpoints", "_touchpoint"), ("quoteLines", "_quoteLine"), ("quotes", "_quote"),
        ("contractDocuments", "_contractDocument"), ("contracts", "_contract"), ("stageChanges", "_stageChange"),
        ("targetLines", "_targetLine"), ("targets", "_target"), ("competitorServices", "_competitorService"),
        ("opportunities", "opportunity"), ("people", "person"), ("partners", "_partner"), ("companies", "company")]


def sql(q):
    return subprocess.run(["docker", "exec", "twenty-db-1", "psql", "-U", "postgres", "-d", "default", "-At", "-c", q],
                          capture_output=True, text=True, check=True).stdout.split()


def sil(cogul, kimlik):
    r = urllib.request.Request(f"http://localhost:3010/rest/{cogul}/{kimlik}?soft_delete=false", method="DELETE",
                               headers={"Authorization": "Bearer " + K})
    for _ in range(8):
        try:
            urllib.request.urlopen(r, timeout=60)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15)
                continue
            if e.code == 404:
                return False
            raise


# fırsattaki geçerli teklif bağı önce kopar (teklif silinebilsin)
for oid in sql(f'select id from {SEMA}.opportunity where "currentQuoteId" is not null'):
    urllib.request.urlopen(urllib.request.Request(f"http://localhost:3010/rest/opportunities/{oid}", method="PATCH",
                                                  data=b'{"currentQuoteId": null}',
                                                  headers={"Authorization": "Bearer " + K, "Content-Type": "application/json"}))
for cogul, tablo in SIRA:
    ids = sql(f'select id from {SEMA}."{tablo}"')   # çöp kutusundakiler dahil (deletedAt dolu olanlar)
    n = sum(1 for i in ids if sil(cogul, i))
    print(f"{cogul:20} silindi: {n}")
ornek = sql(f"select id from {SEMA}.\"_catalogItem\" where name like 'ÖRNEK%'")
print("katalog ÖRNEK silindi:", sum(1 for i in ornek if sil("catalogItems", i)))
for cogul, tablo in SIRA:
    kalan = sql(f'select count(*) from {SEMA}."{tablo}"')[0]
    if kalan != "0":
        print(f"UYARI {cogul}: {kalan} satır kaldı")
print("TEMIZLIK-TAMAM")
