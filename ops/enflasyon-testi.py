#!/usr/bin/env python3
"""Enflasyon öngörüsü testi (liste 14c, deneme ortamı; test kayıtlarını siler ve değiştirdiği öngörüyü geri koyar).
Plan: kararlar/2026-11-13-teklif-modulu-plan.md. Kullanım (sunucuda): python3 ops/enflasyon-testi.py [temizle]

1. Kayıtlar kaynakla aynı mı: TCMB EVDS'den (ve FRED anahtarı varsa Fed'den) bu test ayrıca çeker, kendi hesabıyla karşılaştırır.
2. 36 aylık teklif, aylık 1.000 TRY maliyet / 2.000 TRY fiyat, fiyat artışı "enflasyon kadar":
   maliyet = 12 × 1.000 × (1 + (1+e1) + (1+e1)(1+e2)); gelir aynı formülle 2.000 üzerinden.
3. Enflasyonu olmayan para birimi (EUR) için teklifte uyarı.
4. "Elle sabitlendi" kaydı motor değiştirmez; açık teklif yeni değerle yeniden hesaplanır.
5. Gönderilmiş teklif, öngörü değişse de gönderim anındaki değerle kalır.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

B = "http://localhost:3010"
K = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
ETIKET = "TEST enflasyon - silinecek"
SONUC = []
GERI = {}   # değiştirilen öngörü kaydı → eski değerler


def istek(m, yol, govde=None):
    r = urllib.request.Request(B + yol, method=m, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + K})
    for _ in range(8):
        try:
            return json.loads(urllib.request.urlopen(r, timeout=60).read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15)
                continue
            raise SystemExit(f"{m} {yol}: {e.code} {e.read().decode()[:300]}")


def liste(p, f=""):
    return istek("GET", f"/rest/{p}?limit=200{f}")["data"][p]


def tek(p, tekil, i):
    return istek("GET", f"/rest/{p}/{i}")["data"][tekil]


def para(t, k):
    return {"amountMicros": int(round(t * 1e6)), "currencyCode": k}


def deger(c):
    return None if not c or c.get("amountMicros") in (None, "") else float(c["amountMicros"]) / 1e6


def bekle(f, kosul, sure=120):
    for _ in range(sure // 3):
        time.sleep(3)
        x = f()
        if kosul(x):
            return x
    return f()


def kontrol(ad, ok, ayrinti=""):
    SONUC.append(bool(ok))
    print(("GEÇTİ " if ok else "KALDI ") + ad + (f"  [{ayrinti}]" if not ok and ayrinti else ""))


def anahtar(dosya):
    yol = os.path.expanduser(f"~/twenty/{dosya}")
    return open(yol).read().strip() if os.path.exists(yol) else ""


def ongoruler():
    return {(r["forecastCurrency"], int(r["contractYear"])): r for r in liste("inflationForecasts") if r.get("forecastCurrency")}


def yakin(a, b, tol=0.01):
    return a is not None and b is not None and abs(a - b) <= tol


def kaynak_kontrol(o):
    bugun = dt.date.today()
    bas = (bugun - dt.timedelta(days=150)).strftime("%d-%m-%Y")
    seri = ["TP.PKAUO.S01.E.U", "TP.PKAUO.S01.F.U", "TP.PKAUO.S01.G.U"]
    r = urllib.request.Request(f"https://evds3.tcmb.gov.tr/igmevdsms-dis/series={'-'.join(seri)}&startDate={bas}"
                               f"&endDate={bugun.strftime('%d-%m-%Y')}&type=json", headers={"key": anahtar(".evds-anahtari")})
    son = [x for x in json.loads(urllib.request.urlopen(r, timeout=30).read())["items"]
           if all(x.get(s.replace(".", "_")) for s in seri)][-1]
    e, f, g = (float(son[s.replace(".", "_")]) for s in seri)
    beklenen = [e, f, f + (g - f) / 3, f + 2 * (g - f) / 3, g]
    gercek = [o.get(("TRY", i), {}).get("ratePercent") for i in range(1, 6)]
    kontrol(f"TRY öngörüsü TCMB anketiyle aynı ({son['Tarih']}: {e} / {f} / {g})",
            all(yakin(a, round(b, 2)) for a, b in zip(gercek, beklenen)), (gercek, [round(b, 2) for b in beklenen]))
    fk = anahtar(".fred-anahtari")
    if not fk:
        print("ATLANDI USD öngörüsü (FRED API anahtarı yok)")
        return
    def fred(s):
        v = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"https://api.stlouisfed.org/fred/series/observations?series_id={s}&api_key={fk}&file_type=json",
            headers={"User-Agent": "ascendia-test"}), timeout=30).read())
        return [(x["date"], float(x["value"])) for x in v["observations"] if x["value"] not in ("", ".")]
    yil = {int(t[:4]): v for t, v in fred("PCECTPIMD")}
    uzun = fred("PCECTPIMDLR")[-1][1]
    beklenen = []
    for i in range(5):
        ay = bugun.month - 1 + 6 + 12 * i
        beklenen.append(yil.get(bugun.year + ay // 12, uzun))
    gercek = [o.get(("USD", i), {}).get("ratePercent") for i in range(1, 6)]
    kontrol(f"USD öngörüsü Fed projeksiyonuyla aynı ({yil}, uzun dönem {uzun})",
            all(yakin(a, b) for a, b in zip(gercek, beklenen)), (gercek, beklenen))


def ongoru_degistir(kayit, yeni):
    GERI.setdefault(kayit["id"], {"ratePercent": kayit["ratePercent"], "manual": bool(kayit.get("manual"))})
    istek("PATCH", f"/rest/inflationForecasts/{kayit['id']}", yeni)


def calistir():
    o = ongoruler()
    kaynak_kontrol(o)
    e1, e2 = o[("TRY", 1)]["ratePercent"], o[("TRY", 2)]["ratePercent"]
    carpan = 1 + (1 + e1 / 100) + (1 + e1 / 100) * (1 + e2 / 100)
    sirket = istek("POST", "/rest/companies", {"name": ETIKET})["data"]["createCompany"]["id"]
    kapanis = (dt.date.today() + dt.timedelta(days=20)).isoformat() + "T12:00:00.000Z"
    F = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} F", "companyId": sirket, "stage": "PIPELINE",
                                              "closeDate": kapanis, "contractMonths": 36})["data"]["createOpportunity"]["id"]
    Q = istek("POST", "/rest/quotes", {"opportunityId": F, "priceEscalation": "INFLATION"})["data"]["createQuote"]["id"]
    L = istek("POST", "/rest/quoteLines", {"quoteId": Q, "name": "Aylık hizmet", "quantity": 1, "sortOrder": 1, "billing": "MONTHLY",
                                           "unitPrice": para(2000, "TRY"), "unitCost": para(1000, "TRY"),
                                           "costType": "PERSONNEL"})["data"]["createQuoteLine"]["id"]
    m_bek, g_bek = round(12 * 1000 * carpan, 2), round(12 * 2000 * carpan, 2)
    l = bekle(lambda: tek("quoteLines", "quoteLine", L), lambda l: yakin(deger(l.get("lineCost")), m_bek))
    kontrol(f"36 ay TRY maliyet = 12 × 1.000 × {carpan:.6f} = {m_bek:,.2f}", yakin(deger(l.get("lineCost")), m_bek),
            (deger(l.get("lineCost")), m_bek))
    kontrol(f"Fiyat 'enflasyon kadar': gelir {g_bek:,.2f}", yakin(deger(l.get("lineRevenue")), g_bek), (deger(l.get("lineRevenue")), g_bek))
    # motor önce kalemleri, sonra teklifi yazar: teklifin de yazılmasını bekle
    q = bekle(lambda: tek("quotes", "quote", Q), lambda q: ((q.get("inflationUsed") or {}).get("oranlar") or {}).get("TRY"))
    kontrol("Teklifte kullanılan enflasyon saklandı", ((q.get("inflationUsed") or {}).get("oranlar") or {}).get("TRY", [])[:2] == [e1, e2],
            q.get("inflationUsed"))

    istek("POST", "/rest/quoteLines", {"quoteId": Q, "name": "AB lisansı", "quantity": 1, "sortOrder": 2, "billing": "MONTHLY",
                                       "unitPrice": para(100, "EUR"), "unitCost": para(50, "EUR"), "costType": "LICENSE"})
    q = bekle(lambda: tek("quotes", "quote", Q), lambda q: "EUR" in (q.get("systemWarning") or ""))
    kontrol("Öngörüsü olmayan EUR için uyarı", "Enflasyon öngörüsü yok: EUR" in (q.get("systemWarning") or ""), q.get("systemWarning"))

    # Elle sabitleme: yıl 1 = %30 → açık teklif yeniden hesaplanır
    ongoru_degistir(o[("TRY", 1)], {"ratePercent": 30, "manual": True})
    m30 = round(12 * 1000 * (1 + 1.30 + 1.30 * (1 + e2 / 100)), 2)
    l = bekle(lambda: tek("quoteLines", "quoteLine", L), lambda l: yakin(deger(l.get("lineCost")), m30))
    kontrol(f"Elle sabitlenen %30 açık teklife yansıdı ({m30:,.2f})", yakin(deger(l.get("lineCost")), m30), deger(l.get("lineCost")))

    # Gönderim: değer sabitlenir; öngörü geri alınınca gönderilmiş teklif değişmez
    istek("PATCH", f"/rest/quotes/{Q}", {"status": "SENT"})
    bekle(lambda: tek("quotes", "quote", Q), lambda q: q.get("sentAt"))
    geri_al()
    time.sleep(60)   # motor değişikliği işlesin (birleştirme 30 sn)
    l = tek("quoteLines", "quoteLine", L)
    kontrol("Gönderilmiş teklif gönderim anındaki enflasyonla kaldı", yakin(deger(l.get("lineCost")), m30), deger(l.get("lineCost")))


def geri_al():
    for i, eski in list(GERI.items()):
        istek("PATCH", f"/rest/inflationForecasts/{i}", eski)
        GERI.pop(i)


def temizle():
    geri_al()
    for f in [x for x in liste("opportunities") if x["name"].startswith(ETIKET)]:
        istek("PATCH", f"/rest/opportunities/{f['id']}", {"currentQuoteId": None})
        for q in liste("quotes", f"&filter=opportunityId[eq]:{f['id']}"):
            for l in liste("quoteLines", f"&filter=quoteId[eq]:{q['id']}"):
                istek("DELETE", f"/rest/quoteLines/{l['id']}")
            for h in liste("taskTargets", f"&filter=targetQuoteId[eq]:{q['id']}"):
                istek("DELETE", f"/rest/taskTargets/{h['id']}")
            istek("DELETE", f"/rest/quotes/{q['id']}")
        for h in liste("taskTargets", f"&filter=targetOpportunityId[eq]:{f['id']}"):
            istek("DELETE", f"/rest/taskTargets/{h['id']}")
        for s in liste("stageChanges", f"&filter=opportunityId[eq]:{f['id']}"):
            istek("DELETE", f"/rest/stageChanges/{s['id']}")
        istek("DELETE", f"/rest/opportunities/{f['id']}")
    for g in liste("tasks"):
        if ETIKET in (g.get("title") or ""):
            istek("DELETE", f"/rest/tasks/{g['id']}")
    for r in liste("companies"):
        if ETIKET in (r.get("name") or ""):
            istek("DELETE", f"/rest/companies/{r['id']}")
    print("temizlik tamam")


if len(sys.argv) > 1 and sys.argv[1] == "temizle":
    temizle()
else:
    try:
        calistir()
    finally:
        temizle()
    print(f"SONUÇ: {sum(SONUC)}/{len(SONUC)} geçti")
    sys.exit(0 if all(SONUC) else 1)
