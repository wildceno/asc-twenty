#!/usr/bin/env python3
"""Hesap motoru uçtan uca testi (deneme ortamı): hesaplar, aşama kuralları, kapanış, kilit, sözleşme, Won.
Karar: kararlar/2026-11-11-satis-sureci-ve-hesap-motoru.md. Motoru değiştirmeden önce ve sonra aynı sonucu vermeli (7c).

Kullanım (sunucuda): python3 ops/hesap-testi.py        # çalıştırır, sonunda test kayıtlarını siler
                     python3 ops/hesap-testi.py temizle # yalnız siler
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
ETIKET = "TEST hesap - silinecek"
SONUC = []


def istek(m, yol, govde=None, ham=None, tur="application/json"):
    veri = ham if ham is not None else (json.dumps(govde).encode() if govde is not None else None)
    r = urllib.request.Request(yol if yol.startswith("http") else B + yol, method=m, data=veri,
                               headers={"Authorization": "Bearer " + K, "Content-Type": tur})
    for _ in range(8):
        try:
            return json.loads(urllib.request.urlopen(r, timeout=60).read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429:   # API sınırı (motorla aynı anahtar): bekle, yeniden dene
                time.sleep(15)
                continue
            raise SystemExit(f"{m} {yol}: {e.code} {e.read().decode()[:300]}")


def gql(q, v=None):
    d = istek("POST", "/metadata", {"query": q, "variables": v or {}})
    if d.get("errors"):
        raise SystemExit(json.dumps(d["errors"])[:400])
    return d["data"]


def liste(plural, filtre=""):
    return istek("GET", f"/rest/{plural}?limit=200{filtre}")["data"][plural]


def firsat(oid):
    return istek("GET", f"/rest/opportunities/{oid}")["data"]["opportunity"]


def para(tutar, kod):
    return {"amountMicros": int(round(tutar * 1e6)), "currencyCode": kod}


def deger(c):
    return None if not c or c.get("amountMicros") in (None, "") else float(c["amountMicros"]) / 1e6


def bekle(oid, kosul, sure=60):
    for _ in range(sure // 3):
        time.sleep(3)
        o = firsat(oid)
        if kosul(o):
            return o
    return firsat(oid)


def kontrol(ad, ok, ayrinti=""):
    SONUC.append((ad, bool(ok)))
    print(("GEÇTİ " if ok else "KALDI ") + ad + (f"  [{ayrinti}]" if not ok and ayrinti else ""))


def yakin(a, b, tol=0.01):
    return a is not None and b is not None and abs(a - b) <= tol


def dosya_yukle(alan, ad):
    """FILES alanına küçük bir metin dosyası yükler (motorun dosya kopyalama yolunu da sınar)."""
    alan_id = next(f["node"]["id"] for e in gql("{ objects(paging:{first:200}) { edges { node { nameSingular "
                                                 "fields(paging:{first:500}) { edges { node { id name } } } } } } }")["objects"]["edges"]
                   if e["node"]["nameSingular"] == "opportunity" for f in e["node"]["fields"]["edges"] if f["node"]["name"] == alan)
    icerik = f"{ETIKET} {ad}".encode()
    t = gql("mutation($n:String!,$s:Float!,$a:String!){ createFileUpload(filename:$n,size:$s,fileFolder:FilesField,"
            "fieldMetadataId:$a){ fileId uploadUrl contentType } }", {"n": ad, "s": len(icerik), "a": alan_id})["createFileUpload"]
    url = "http://localhost:3010" + "/" + t["uploadUrl"].split("/", 3)[3]
    urllib.request.urlopen(urllib.request.Request(url, method="PUT", data=icerik, headers={"Content-Type": t["contentType"]}), timeout=60)
    gql("mutation($f:String!){ completeFileUpload(fileId:$f){ id } }", {"f": t["fileId"]})
    return [{"fileId": t["fileId"], "label": ad}]


def calistir():
    if [o for o in liste("opportunities") if o["name"].startswith(ETIKET)]:
        raise SystemExit("Önceki test kayıtları duruyor: önce 'temizle'.")
    bugun = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).date()
    kapanis = (bugun + dt.timedelta(days=10)).isoformat() + "T12:00:00.000Z"
    sirket = istek("POST", "/rest/companies", {"name": ETIKET})["data"]["createCompany"]["id"]

    # 1) Hesaplar (USD): TCV = 1000 + 100 × 12 = 2200; maliyet = 200 + 20 × 12 = 440; GP 1760; GM %80; MRR 100; ARR 1200
    A = istek("POST", "/rest/opportunities", {
        "name": f"{ETIKET} A", "companyId": sirket, "stage": "PIPELINE", "closeDate": kapanis, "contractMonths": 12,
        "oneTimeFee": para(1000, "USD"), "monthlyRecurring": para(100, "USD"),
        "oneTimeCost": para(200, "USD"), "monthlyCost": para(20, "USD")})["data"]["createOpportunity"]["id"]
    o = bekle(A, lambda o: deger(o.get("amount")) is not None and o.get("reportingPeriodName"))
    kontrol("TCV 2200", yakin(deger(o.get("amount")), 2200), o.get("amount"))
    kontrol("Toplam maliyet 440", yakin(deger(o.get("totalCost")), 440))
    kontrol("Gross Profit 1760", yakin(deger(o.get("grossProfit")), 1760))
    kontrol("Gross Margin %80", o.get("grossMarginPercent") == 80.0, o.get("grossMarginPercent"))
    kontrol("MRR 100, ARR 1200", yakin(deger(o.get("mrr")), 100) and yakin(deger(o.get("arr")), 1200))
    kontrol("Raporlama tutarı 2200 USD", yakin(deger(o.get("amountReporting")), 2200)
            and (o.get("amountReporting") or {}).get("currencyCode") == "USD")
    kontrol("Çeyrek ve dönem dolu", bool(o.get("expectedCloseQuarter")) and bool(o.get("reportingPeriodName")),
            f"{o.get('expectedCloseQuarter')} / {o.get('reportingPeriodName')}")
    kontrol("Aşama Geçmişi: ilk kayıt", any(s.get("toStage") == "PIPELINE" for s in liste("stageChanges", f"&filter=opportunityId[eq]:{A}")))

    # 2) Kur çevirisi: 1000 EUR → USD (TCMB döviz alış, son kur)
    kur = {}
    for r in sorted(liste("exchangeRates"), key=lambda r: r.get("rateDate") or ""):
        kur[r["foreignCurrency"]] = float(r["rateTry"])
    E = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} E", "companyId": sirket, "stage": "PIPELINE",
                                              "closeDate": kapanis, "oneTimeFee": para(1000, "EUR")})["data"]["createOpportunity"]["id"]
    e = bekle(E, lambda o: deger(o.get("amountReporting")) is not None)
    beklenen = 1000 * kur["EUR"] / kur["USD"]
    kontrol("EUR → USD çevirisi", yakin(deger(e.get("amountReporting")), beklenen, 0.05), f"{deger(e.get('amountReporting'))} ≠ {beklenen:.2f}")
    kontrol("TCV kalem para biriminde (EUR)", (e.get("amount") or {}).get("currencyCode") == "EUR")

    # 3) Belgesiz Audit → geri alınır, uyarı yazılır
    istek("PATCH", f"/rest/opportunities/{A}", {"stage": "AUDIT"})
    o = bekle(A, lambda o: o["stage"] != "AUDIT" and o.get("systemWarning"))
    kontrol("Belgesiz Audit geri alındı", o["stage"] == "PIPELINE" and "Sipariş" in (o.get("systemWarning") or ""), o["stage"])

    # 4) Belgelerle Audit → kapanış, sözleşme, belgeler, kapanış değerleri
    istek("PATCH", f"/rest/opportunities/{A}", {"orderDocument": dosya_yukle("orderDocument", "siparis.txt"),
                                                "approvedProposal": dosya_yukle("approvedProposal", "teklif.txt")})
    time.sleep(4)
    istek("PATCH", f"/rest/opportunities/{A}", {"stage": "AUDIT"})
    o = bekle(A, lambda o: o.get("realCloseDate"))
    kontrol("Audit: Gerçek Kapanış Tarihi bugün", (o.get("realCloseDate") or "")[:10] == bugun.isoformat(), o.get("realCloseDate"))
    kontrol("Audit: uyarı temizlendi", not o.get("systemWarning"))
    kontrol("Audit: durumlar başladı", o.get("contractStatus") == "SIGNING" and o.get("deliveryStatus") == "NOT_STARTED")
    for _ in range(20):   # motor API sınırı içinde sıra bekleyebilir: belgeleri 60 sn'ye kadar bekle
        time.sleep(3)
        soz = liste("contracts", f"&filter=opportunityId[eq]:{A}")
        if soz and len(liste("contractDocuments", f"&filter=contractId[eq]:{soz[0]['id']}")) >= 2:
            break
    kontrol("Sözleşme oluştu (İmzada, TCV 2200)", len(soz) == 1 and soz[0].get("status") == "SIGNING"
            and yakin(deger(soz[0].get("totalValue")), 2200))
    belge = liste("contractDocuments", f"&filter=contractId[eq]:{soz[0]['id']}") if soz else []
    kontrol("Sözleşme belgeleri kopyalandı (2)", sorted(b.get("documentType") for b in belge) == ["APPROVED_PROPOSAL", "ORDER"]
            and all(b.get("file") for b in belge))
    kapanis_kaydi = [s for s in liste("stageChanges", f"&filter=opportunityId[eq]:{A}") if s.get("toStage") == "AUDIT" and s.get("closingSnapshot")]
    kontrol("Kapanış değerleri Aşama Geçmişi'nde", bool(kapanis_kaydi))

    # 5) Kilit: kapanmış fırsatta tutar değişikliği geri alınır
    istek("PATCH", f"/rest/opportunities/{A}", {"oneTimeFee": para(5000, "USD")})
    o = bekle(A, lambda o: yakin(deger(o.get("oneTimeFee")), 1000))
    kontrol("Kilit: değişiklik geri alındı", yakin(deger(o.get("oneTimeFee")), 1000) and yakin(deger(o.get("amount")), 2200))

    # 6) Commit'e dönüş: kapanış silinir; yeniden Audit
    istek("PATCH", f"/rest/opportunities/{A}", {"stage": "COMMIT"})
    o = bekle(A, lambda o: not o.get("realCloseDate"))
    kontrol("Commit'e dönüş: kapanış tarihi silindi", not o.get("realCloseDate") and o["stage"] == "COMMIT")
    istek("PATCH", f"/rest/opportunities/{A}", {"stage": "AUDIT"})
    bekle(A, lambda o: o.get("realCloseDate"))

    # 7) Durumlar: imza → Delivery; teslimat + faturalama tamam → Won
    istek("PATCH", f"/rest/opportunities/{A}", {"contractStatus": "SIGNED"})
    o = bekle(A, lambda o: o["stage"] == "DELIVERY")
    kontrol("İmza → Delivery", o["stage"] == "DELIVERY", o["stage"])
    time.sleep(4)
    kontrol("İmza → sözleşme Aktif", (liste("contracts", f"&filter=opportunityId[eq]:{A}") or [{}])[0].get("status") == "ACTIVE")
    istek("PATCH", f"/rest/opportunities/{A}", {"deliveryStatus": "DONE", "invoicingStatus": "DONE"})
    o = bekle(A, lambda o: o["stage"] == "WON")
    kontrol("Üçü tamam → Won", o["stage"] == "WON", o["stage"])

    # 8) Son aşamalardan çıkış geri alınır
    istek("PATCH", f"/rest/opportunities/{A}", {"stage": "PIPELINE"})
    o = bekle(A, lambda o: o["stage"] == "WON" and o.get("systemWarning"))
    kontrol("Won'dan çıkış geri alındı", o["stage"] == "WON")
    istek("PATCH", f"/rest/opportunities/{E}", {"stage": "LOST"})
    bekle(E, lambda o: o.get("realCloseDate"))
    istek("PATCH", f"/rest/opportunities/{E}", {"stage": "PIPELINE"})
    e = bekle(E, lambda o: o["stage"] == "LOST" and o.get("systemWarning"))
    kontrol("Lost: kapanış ve çıkışın geri alınması", e["stage"] == "LOST" and bool(e.get("realCloseDate")))


def uye(ad):
    return next(m["id"] for m in liste("workspaceMembers") if f"{m['name']['firstName']} {m['name']['lastName']}" == ad)


def sorumlular():
    """Liste 12: şirket sorumlularının fırsata kopyalanması ve şirketteki değişikliğin açık fırsatlara yansıması."""
    yon, sat, sup, sup_u = uye("Test Yönetici"), uye("Test Satış"), uye("Test Support"), uye("Test Super-user")
    kapanis = (dt.date.today() + dt.timedelta(days=10)).isoformat() + "T12:00:00.000Z"
    sirket = istek("POST", "/rest/companies", {"name": f"{ETIKET} S", "accountManagerId": yon, "preSalesId": sat,
                                               "serviceManagerId": sup})["data"]["createCompany"]["id"]
    time.sleep(3)
    S1 = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} S1", "companyId": sirket, "stage": "PIPELINE",
                                               "closeDate": kapanis})["data"]["createOpportunity"]["id"]
    S2 = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} S2", "companyId": sirket, "stage": "PIPELINE",
                                               "closeDate": kapanis, "accountManagerId": sup_u})["data"]["createOpportunity"]["id"]
    o1 = bekle(S1, lambda o: o.get("accountManagerId"))
    o2 = bekle(S2, lambda o: o.get("preSalesId"))
    kontrol("Yeni fırsat: AM ve Pre-sales şirketten", o1.get("accountManagerId") == yon and o1.get("preSalesId") == sat)
    kontrol("Yeni fırsat: Service Manager henüz boş", not o1.get("serviceManagerId"))
    kontrol("Elle yazılmış AM korundu", o2.get("accountManagerId") == sup_u and o2.get("preSalesId") == sat)
    sahip = os.environ.get("HESAP_TESTI_UYE_ID") or next(   # test kullanıcısı olmayan ilk üye (çalışma alanı sahibi)
        m["id"] for m in liste("workspaceMembers") if not m["name"]["firstName"].startswith("Test"))
    istek("PATCH", f"/rest/companies/{sirket}", {"accountManagerId": sahip})
    o1 = bekle(S1, lambda o: o.get("accountManagerId") == sahip, 90)
    o2 = firsat(S2)
    kontrol("Şirket AM değişti → açık fırsata yansıdı", o1.get("accountManagerId") == sahip, o1.get("accountManagerId"))
    kontrol("Elle yazılmış AM'e dokunulmadı", o2.get("accountManagerId") == sup_u)
    istek("PATCH", f"/rest/opportunities/{S1}", {"orderDocument": dosya_yukle("orderDocument", "siparis2.txt"),
                                                 "approvedProposal": dosya_yukle("approvedProposal", "teklif2.txt")})
    time.sleep(4)
    istek("PATCH", f"/rest/opportunities/{S1}", {"stage": "AUDIT"})
    o1 = bekle(S1, lambda o: o.get("serviceManagerId"))
    kontrol("Audit'e alınınca Service Manager şirketten", o1.get("serviceManagerId") == sup)
    # 12b: Hesap Durumu sözleşmeden
    def durum(beklenen):
        for _ in range(20):
            time.sleep(3)
            d = istek("GET", f"/rest/companies/{sirket}")["data"]["company"].get("accountStatus")
            if d == beklenen:
                return d
        return d
    kontrol("Hesap Durumu: imzada sözleşme → Aday", durum("PROSPECT") == "PROSPECT")
    istek("PATCH", f"/rest/opportunities/{S1}", {"contractStatus": "SIGNED"})
    kontrol("Hesap Durumu: imza → Müşteri", durum("CUSTOMER") == "CUSTOMER")
    soz = liste("contracts", f"&filter=opportunityId[eq]:{S1}")[0]
    istek("PATCH", f"/rest/contracts/{soz['id']}", {"status": "ENDED"})
    kontrol("Hesap Durumu: sözleşme bitti → Eski müşteri", durum("FORMER") == "FORMER")


def temizle():
    for o in [o for o in liste("opportunities") if o["name"].startswith(ETIKET)]:
        for c in liste("contracts", f"&filter=opportunityId[eq]:{o['id']}"):
            for b in liste("contractDocuments", f"&filter=contractId[eq]:{c['id']}"):
                istek("DELETE", f"/rest/contractDocuments/{b['id']}")
            istek("DELETE", f"/rest/contracts/{c['id']}")
        for s in liste("stageChanges", f"&filter=opportunityId[eq]:{o['id']}"):
            istek("DELETE", f"/rest/stageChanges/{s['id']}")
        for h in liste("taskTargets", f"&filter=targetOpportunityId[eq]:{o['id']}"):
            istek("DELETE", f"/rest/tasks/{h['taskId']}")
            istek("DELETE", f"/rest/taskTargets/{h['id']}")
        istek("DELETE", f"/rest/opportunities/{o['id']}")
    for c in liste("companies"):
        if c["name"].startswith(ETIKET):
            istek("DELETE", f"/rest/companies/{c['id']}")
    print("temizlik tamam")


if len(sys.argv) > 1 and sys.argv[1] == "temizle":
    temizle()
else:
    try:
        calistir()
        time.sleep(30)   # API sınırı: iki bölüm arasında nefes
        sorumlular()
    finally:
        temizle()
    gecen = sum(ok for _, ok in SONUC)
    print(f"SONUÇ: {gecen}/{len(SONUC)} geçti")
    sys.exit(0 if gecen == len(SONUC) else 1)
