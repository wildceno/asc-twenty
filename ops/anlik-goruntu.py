#!/usr/bin/env python3
"""Motorun ürettiği tüm alanların anlık görüntüsü (7c: paketlere ayırmadan önce/sonra karşılaştırma).

Kullanım (sunucuda): python3 ops/anlik-goruntu.py al <dosya.json>
                     python3 ops/anlik-goruntu.py karsilastir <once.json> <sonra.json>
Zamanla kendiliğinden değişenler (kalp atışı, güncellenme zamanı) alınmaz."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

B = "http://localhost:3010"
K = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
ALANLAR = {
    "opportunities": ["name", "stage", "amount", "totalCost", "grossProfit", "grossMarginPercent", "amountReporting",
                      "grossProfitReporting", "mrr", "arr", "mrrReporting", "arrReporting", "expectedCloseQuarter",
                      "reportingPeriodName", "inCurrentPeriod", "realCloseDate", "ownerId", "systemWarning",
                      "lastTouchAt", "daysWithoutTouch", "followUpStatus", "fxRateDate"],
    "targetLines": ["name", "metric", "targetAmount", "actualAmount", "attainmentPercent", "forecastAmount",
                    "forecastAttainmentPercent", "inCurrentPeriod"],
    "targets": ["name", "periodId", "attainmentPercent", "forecastAttainmentPercent"],
    "reportingPeriods": ["name", "periodType", "startDate", "endDate", "fiscalYear", "isCurrent"],
    "forecastRates": ["stage", "manualRate", "historicalRate", "closedCount", "effectiveRate", "rateSource"],
    "contracts": ["name", "status", "totalValue", "remainingDays"],
}


def liste(plural):
    out, imlec = [], None
    while True:
        yol = f"/rest/{plural}?limit=60" + (f"&starting_after={imlec}" if imlec else "")
        for _ in range(8):
            try:
                d = json.loads(urllib.request.urlopen(urllib.request.Request(B + yol, headers={"Authorization": "Bearer " + K})).read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                time.sleep(15)   # API sınırı: bekle, yeniden dene
        out += d["data"][plural]
        if not d["pageInfo"]["hasNextPage"]:
            return out
        imlec = d["pageInfo"]["endCursor"]


def al(dosya):
    g = {p: {r["id"]: {a: r.get(a) for a in alanlar} for r in liste(p)} for p, alanlar in ALANLAR.items()}
    json.dump(g, open(dosya, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    print(dosya, {p: len(v) for p, v in g.items()})


def karsilastir(a, b):
    x, y = json.load(open(a)), json.load(open(b))
    fark = 0
    for p in ALANLAR:
        for k in sorted(set(x[p]) | set(y[p])):
            if x[p].get(k) != y[p].get(k):
                fark += 1
                print(f"FARK {p} {k}:\n  önce : {x[p].get(k)}\n  sonra: {y[p].get(k)}")
    print("fark yok" if not fark else f"{fark} kayıtta fark")
    sys.exit(1 if fark else 0)


{"al": lambda: al(sys.argv[2]), "karsilastir": lambda: karsilastir(sys.argv[2], sys.argv[3])}[sys.argv[1]]()
