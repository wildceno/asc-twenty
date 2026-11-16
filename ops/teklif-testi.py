#!/usr/bin/env python3
"""Teklif modülü uçtan uca testi (liste 14a, deneme ortamı; test kayıtlarını siler).
Plan: kararlar/2026-11-13-teklif-modulu-plan.md. Kullanım (sunucuda): python3 ops/teklif-testi.py [temizle]

Elle hesap: Katalog "ÖRNEK eğitim günü" 1.500 USD / maliyet 500 USD, 2 gün → gelir 3.000, maliyet 1.000.
Özel kalem aylık 100 USD / maliyet 40 USD, 12 ay → gelir 1.200, maliyet 480. Toplam 4.200 / 1.480, brüt 2.720, marj %64,8.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

B, ORIGIN = "http://localhost:3010", os.environ.get("TWENTY_ORIGIN") or next((l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/twenty/.env")) if l.startswith("SERVER_URL=")), "http://localhost:3010")
K = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
ETIKET = "TEST teklif - silinecek"
SONUC = []


def istek(m, yol, govde=None, tok=None):
    baslik = {"Content-Type": "application/json"}
    if tok != "-":   # "-" = oturum açma isteği, yetki başlığı yok
        baslik["Authorization"] = "Bearer " + (tok or K)
    r = urllib.request.Request(B + yol, method=m, data=json.dumps(govde).encode() if govde is not None else None, headers=baslik)
    for _ in range(8):
        try:
            return json.loads(urllib.request.urlopen(r, timeout=60).read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15)
                continue
            raise SystemExit(f"{m} {yol}: {e.code} {e.read().decode()[:300]}")


def gql(q, v=None, tok=None):
    d = istek("POST", "/metadata", {"query": q, "variables": v or {}}, tok)
    if d.get("errors"):
        raise SystemExit(str(d["errors"])[:300])
    return d["data"]


def giris(eposta, sifre):
    lt = gql("mutation($e:String!,$p:String!,$o:String!){ getLoginTokenFromCredentials(email:$e,password:$p,origin:$o){ loginToken { token } } }",
             {"e": eposta, "p": sifre, "o": ORIGIN}, tok="-")
    t = gql("mutation($t:String!,$o:String!){ getAuthTokensFromLoginToken(loginToken:$t,origin:$o){ tokens { accessOrWorkspaceAgnosticToken { token } } } }",
            {"t": lt["getLoginTokenFromCredentials"]["loginToken"]["token"], "o": ORIGIN}, tok="-")
    return t["getAuthTokensFromLoginToken"]["tokens"]["accessOrWorkspaceAgnosticToken"]["token"]


def liste(p, f=""):
    return istek("GET", f"/rest/{p}?limit=200{f}")["data"][p]


def tek(p, tekil, i):
    return istek("GET", f"/rest/{p}/{i}")["data"][tekil]


def para(t, k):
    return {"amountMicros": int(round(t * 1e6)), "currencyCode": k}


def deger(c):
    return None if not c or c.get("amountMicros") in (None, "") else float(c["amountMicros"]) / 1e6


def bekle(f, kosul, sure=90):
    for _ in range(sure // 3):
        time.sleep(3)
        x = f()
        if kosul(x):
            return x
    return f()


def kontrol(ad, ok, ayrinti=""):
    SONUC.append(bool(ok))
    print(("GEÇTİ " if ok else "KALDI ") + ad + (f"  [{ayrinti}]" if not ok and ayrinti else ""))


def uye(ad):
    return next(m["id"] for m in liste("workspaceMembers") if f"{m['name']['firstName']} {m['name']['lastName']}" == ad)


def calistir():
    kul = {l.split("\t")[0]: l.strip().split("\t") for l in open(os.path.expanduser("~/twenty/.test-kullanicilar"))}
    yon, satis = uye("Test Yönetici"), uye("Test Satış")
    sirket = istek("POST", "/rest/companies", {"name": ETIKET})["data"]["createCompany"]["id"]
    kat = istek("POST", "/rest/catalogItems", {"name": f"ÖRNEK eğitim günü ({ETIKET})", "kind": "SERVICE", "unit": "gün",
                                               "unitCost": para(500, "USD"), "listPrice": para(1500, "USD"),
                                               "billing": "ONE_TIME", "costType": "PERSONNEL", "active": True})["data"]["createCatalogItem"]["id"]
    kapanis = (dt.date.today() + dt.timedelta(days=20)).isoformat() + "T12:00:00.000Z"
    F = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} F", "companyId": sirket, "stage": "PIPELINE",
                                              "closeDate": kapanis, "contractMonths": 12, "ownerId": satis})["data"]["createOpportunity"]["id"]
    Q1 = istek("POST", "/rest/quotes", {"opportunityId": F})["data"]["createQuote"]["id"]
    q = bekle(lambda: tek("quotes", "quote", Q1), lambda q: q.get("version") and q.get("status"))
    kontrol("Yeni teklif: Taslak, Sürüm 1, ad ve süre fırsattan", q.get("status") == "DRAFT" and q.get("version") == 1
            and (q.get("name") or "").endswith("Sürüm 1") and q.get("contractMonths") == 12, q)
    L1 = istek("POST", "/rest/quoteLines", {"quoteId": Q1, "catalogItemId": kat, "quantity": 2, "sortOrder": 1})["data"]["createQuoteLine"]["id"]
    istek("POST", "/rest/quoteLines", {"quoteId": Q1, "name": "Özel destek", "quantity": 1, "sortOrder": 2, "billing": "MONTHLY",
                                       "unitPrice": para(100, "USD"), "unitCost": para(40, "USD"), "costType": "PERSONNEL"})
    l1 = bekle(lambda: tek("quoteLines", "quoteLine", L1), lambda l: deger(l.get("lineRevenue")) == 3000)
    kontrol("Katalogdan kopya: ad, birim, fiyat 1.500, maliyet 500", l1.get("unit") == "gün" and deger(l1.get("unitPrice")) == 1500
            and deger(l1.get("unitCost")) == 500 and "ÖRNEK" in (l1.get("name") or ""), l1)
    q = bekle(lambda: tek("quotes", "quote", Q1), lambda q: deger(q.get("revenueReporting")) == 4200)
    kontrol("Toplam 4.200 / 1.480, brüt 2.720, marj %64,8", deger(q.get("revenueReporting")) == 4200 and deger(q.get("costReporting")) == 1480
            and deger(q.get("grossProfitReporting")) == 2720 and q.get("marginPercent") == 64.8,
            (q.get("revenueReporting"), q.get("costReporting"), q.get("marginPercent")))

    # Marj kuralı %70 → onay Test Yönetici
    kural = istek("POST", "/rest/marginRules", {"name": f"{ETIKET} %70", "thresholdPercent": 70, "approverId": yon})["data"]["createMarginRule"]["id"]
    q = bekle(lambda: tek("quotes", "quote", Q1), lambda q: q.get("approverId") == yon)
    kontrol("Marj kuralı: onaylayıcı atandı", q.get("approverId") == yon)
    istek("PATCH", f"/rest/quotes/{Q1}", {"status": "SENT"})
    q = bekle(lambda: tek("quotes", "quote", Q1), lambda q: q.get("status") == "PENDING_APPROVAL")
    kontrol("Onaysız gönderim → Onay bekliyor", q.get("status") == "PENDING_APPROVAL" and not q.get("sentAt"))
    gorev = bekle(lambda: [g for g in liste("tasks", f"&filter=assigneeId[eq]:{yon}") if g["title"].startswith("Teklif onayı") and ETIKET in g["title"]], bool)
    kontrol("Onaylayıcıya görev", len(gorev) == 1)
    istek("PATCH", f"/rest/quotes/{Q1}", {"status": "APPROVED"}, tok=giris(kul["Satış"][1], kul["Satış"][2]))
    q = bekle(lambda: tek("quotes", "quote", Q1), lambda q: q.get("status") == "PENDING_APPROVAL" and q.get("systemWarning"))
    kontrol("Yetkisiz onay geri alındı (Satış)", q.get("status") == "PENDING_APPROVAL" and not q.get("approvedById"))
    istek("PATCH", f"/rest/quotes/{Q1}", {"status": "APPROVED"}, tok=giris(kul["Yönetici"][1], kul["Yönetici"][2]))
    q = bekle(lambda: tek("quotes", "quote", Q1), lambda q: q.get("approvedById") == yon)
    kontrol("Onaylayıcı onayladı", q.get("approvedById") == yon and q.get("status") == "APPROVED")
    istek("PATCH", f"/rest/quotes/{Q1}", {"status": "SENT"})
    q = bekle(lambda: tek("quotes", "quote", Q1), lambda q: q.get("sentAt"))
    kontrol("Onaylı teklif gönderildi (kur tarihi sabit)", q.get("status") == "SENT" and q.get("fxRateDate"))
    f = bekle(lambda: tek("opportunities", "opportunity", F), lambda f: deger(f.get("amount")) == 4200)
    kontrol("Fırsat: geçerli teklif, TCV 4.200, maliyet 1.480, GP 2.720", f.get("currentQuoteId") == Q1 and deger(f.get("amount")) == 4200
            and deger(f.get("totalCost")) == 1480 and deger(f.get("grossProfit")) == 2720, (f.get("amount"), f.get("totalCost")))
    kontrol("Fırsat: tek seferlik 3.000, aylık 100, süre 12", deger(f.get("oneTimeFee")) == 3000 and deger(f.get("monthlyRecurring")) == 100
            and f.get("contractMonths") == 12)
    istek("PATCH", f"/rest/opportunities/{F}", {"oneTimeFee": para(9999, "USD")})
    f = bekle(lambda: tek("opportunities", "opportunity", F), lambda f: deger(f.get("oneTimeFee")) == 3000)
    kontrol("Fırsattaki tutar kilitli (geri alındı)", deger(f.get("oneTimeFee")) == 3000)

    # Revizyon: Sürüm 2 (kural kapsamı dışında kalsın diye kuralı kaldır)
    istek("DELETE", f"/rest/marginRules/{kural}")
    Q2 = istek("POST", "/rest/quotes", {"opportunityId": F, "validUntil": (dt.date.today() + dt.timedelta(days=2)).isoformat()})["data"]["createQuote"]["id"]
    istek("POST", "/rest/quoteLines", {"quoteId": Q2, "catalogItemId": kat, "quantity": 3})
    bekle(lambda: tek("quotes", "quote", Q2), lambda q: deger(q.get("revenueReporting")) == 4500)
    istek("PATCH", f"/rest/quotes/{Q2}", {"status": "SENT"})
    q1 = bekle(lambda: tek("quotes", "quote", Q1), lambda q: q.get("status") == "REVISED")
    f = bekle(lambda: tek("opportunities", "opportunity", F), lambda f: f.get("currentQuoteId") == Q2 and deger(f.get("amount")) == 4500)
    kontrol("Sürüm 2 gönderildi: Sürüm 1 Revize edildi, fırsat Sürüm 2'den (4.500)", q1.get("status") == "REVISED"
            and f.get("currentQuoteId") == Q2 and deger(f.get("amount")) == 4500 and tek("quotes", "quote", Q2).get("version") == 2)
    hat = bekle(lambda: [g for g in liste("tasks", f"&filter=assigneeId[eq]:{satis}") if "Teklif geçerliliği" in g["title"] and ETIKET in g["title"]], bool, 120)
    kontrol("Geçerlilik hatırlatması fırsat sahibine (2 gün kala)", len(hat) == 1 and "2 gün" in hat[0]["title"], [g["title"] for g in hat])

    # Kabul → Audit'te Onaylanan Teklif şartı karşılanır (yalnız sipariş dokümanı yeter)
    istek("PATCH", f"/rest/quotes/{Q2}", {"status": "ACCEPTED"})
    time.sleep(5)
    alan = next(fl["node"]["id"] for e in gql("{ objects(paging:{first:200}) { edges { node { nameSingular fields(paging:{first:500}) { edges { node { id name } } } } } } }")["objects"]["edges"]
                if e["node"]["nameSingular"] == "opportunity" for fl in e["node"]["fields"]["edges"] if fl["node"]["name"] == "orderDocument")
    icerik = b"siparis"
    t = gql("mutation($n:String!,$s:Float!,$a:String!){ createFileUpload(filename:$n,size:$s,fileFolder:FilesField,fieldMetadataId:$a){ fileId uploadUrl contentType } }",
            {"n": "siparis.txt", "s": len(icerik), "a": alan})["createFileUpload"]
    urllib.request.urlopen(urllib.request.Request(B + "/" + t["uploadUrl"].split("/", 3)[3], method="PUT", data=icerik,
                                                  headers={"Content-Type": t["contentType"]}), timeout=60)
    gql("mutation($f:String!){ completeFileUpload(fileId:$f){ id } }", {"f": t["fileId"]})
    istek("PATCH", f"/rest/opportunities/{F}", {"orderDocument": [{"fileId": t["fileId"], "label": "siparis.txt"}]})
    time.sleep(4)
    istek("PATCH", f"/rest/opportunities/{F}", {"stage": "AUDIT"})
    f = bekle(lambda: tek("opportunities", "opportunity", F), lambda f: f.get("realCloseDate"))
    kontrol("Kabul edilen teklif Audit şartını karşıladı", f["stage"] == "AUDIT" and bool(f.get("realCloseDate")), (f["stage"], f.get("systemWarning")))


def temizle():
    for f in [o for o in liste("opportunities") if o["name"].startswith(ETIKET)]:
        istek("PATCH", f"/rest/opportunities/{f['id']}", {"currentQuoteId": None})
        for c in liste("contracts", f"&filter=opportunityId[eq]:{f['id']}"):
            for b in liste("contractDocuments", f"&filter=contractId[eq]:{c['id']}"):
                istek("DELETE", f"/rest/contractDocuments/{b['id']}")
            istek("DELETE", f"/rest/contracts/{c['id']}")
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
    for p, a in (("catalogItems", "name"), ("marginRules", "name"), ("companies", "name")):
        for r in liste(p):
            if ETIKET in (r.get(a) or ""):
                istek("DELETE", f"/rest/{p}/{r['id']}")
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
