#!/usr/bin/env python3
"""Teklif belgesi uçtan uca testi (liste 15b, deneme ortamı; test kayıtlarını siler).
Plan: kararlar/2026-11-13-teklif-modulu-plan.md. Kullanım (sunucuda): python3 ops/belge-testi.py [temizle]

Nötr örnek Word şablonu (belge/testler/ornek_uret.py) ile: 2 kalemli teklif (test tutarları), bir kaldırılabilir bölüm
çıkarılır, kapak (çıkarılamaz) çıkarılmak istenir, tanınmayan alan doldurulur; Word + PDF üretilir ve içerik geri okunur.
Üretilen belge belge servisinin içinde okunur (docker exec), Monster'da python-docx kurulu olması gerekmez.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

B = "http://localhost:3010"
K = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
ETIKET = "TEST belge - silinecek"
SONUC = []


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


def gql(q, v=None):
    d = istek("POST", "/metadata", {"query": q, "variables": v or {}})
    if d.get("errors"):
        raise SystemExit(str(d["errors"])[:300])
    return d["data"]


def liste(p, f=""):
    return istek("GET", f"/rest/{p}?limit=200{f}")["data"][p]


def tek(p, tekil, i):
    return istek("GET", f"/rest/{p}/{i}")["data"][tekil]


def bekle(f, kosul, sure=150):
    for _ in range(sure // 3):
        time.sleep(3)
        x = f()
        if kosul(x):
            return x
    return f()


def kontrol(ad, ok, ayrinti=""):
    SONUC.append(bool(ok))
    print(("GEÇTİ " if ok else "KALDI ") + ad + (f"  [{ayrinti}]" if not ok and ayrinti else ""))


def para(t, k):
    return {"amountMicros": int(round(t * 1e6)), "currencyCode": k}


def ornek_docx():
    subprocess.run(["docker", "exec", "belge-servisi", "python3", "-m", "testler.ornek_uret", "/tmp"], check=True, capture_output=True)
    return subprocess.run(["docker", "exec", "belge-servisi", "cat", "/tmp/ornek-sablon.docx"], check=True, capture_output=True).stdout


def yukle(sid, ad, icerik):
    alan = next(f["node"]["id"] for e in gql("{ objects(paging:{first:200}) { edges { node { nameSingular "
                                             "fields(paging:{first:500}) { edges { node { id name } } } } } } }")["objects"]["edges"]
                if e["node"]["nameSingular"] == "quoteTemplate" for f in e["node"]["fields"]["edges"] if f["node"]["name"] == "templateFile")
    t = gql("mutation($n:String!,$s:Float!,$a:String!){ createFileUpload(filename:$n,size:$s,fileFolder:FilesField,"
            "fieldMetadataId:$a){ fileId uploadUrl contentType } }", {"n": ad, "s": len(icerik), "a": alan})["createFileUpload"]
    urllib.request.urlopen(urllib.request.Request(B + "/" + t["uploadUrl"].split("/", 3)[3], method="PUT", data=icerik,
                                                  headers={"Content-Type": t["contentType"]}), timeout=60)
    gql("mutation($f:String!){ completeFileUpload(fileId:$f){ id } }", {"f": t["fileId"]})
    istek("PATCH", f"/rest/quoteTemplates/{sid}", {"templateFile": [{"fileId": t["fileId"], "label": ad}]})
    return t["fileId"]


def indir(url):
    p = url.split("/", 3)[3]
    return urllib.request.urlopen(B + "/" + p, timeout=60).read()


DOCX_INCELE = r'''
import io, json, sys
from docx import Document
from belge_servisi.oku import oku
v = sys.stdin.buffer.read()
d = Document(io.BytesIO(v))
o = oku(v)
print(json.dumps({"bolumler": [b["ad"] for b in o["bolumler"]], "yer_tutucular": o["yer_tutucular"],
                  "metin": "\n".join(p.text for p in d.paragraphs), "ust": d.sections[0].header.paragraphs[0].text,
                  "tablolar": [[[c.text for c in r.cells] for r in t.rows] for t in d.tables]}, ensure_ascii=False))
'''


def incele(veri):
    r = subprocess.run(["docker", "exec", "-i", "-w", "/app", "belge-servisi", "python3", "-c", DOCX_INCELE], input=veri,
                       capture_output=True, check=True)
    return json.loads(r.stdout)


def calistir():
    S = istek("POST", "/rest/quoteTemplates", {"name": f"{ETIKET} şablon"})["data"]["createQuoteTemplate"]["id"]
    fid = yukle(S, "ornek-sablon.docx", ornek_docx())
    bekle(lambda: tek("quoteTemplates", "quoteTemplate", S), lambda s: s.get("readFileId") == fid)
    for b in liste("templateSections", f"&filter=quoteTemplateId[eq]:{S}"):
        if b["name"] == "Mevcut durum":
            istek("PATCH", f"/rest/templateSections/{b['id']}", {"defaultText": "Varsayılan durum metni"})
    eski_varsayilan = [x["id"] for x in liste("quoteTemplates", "&filter=isDefault[eq]:true")]
    istek("PATCH", f"/rest/quoteTemplates/{S}", {"status": "ACTIVE", "isDefault": True})
    bekle(lambda: tek("quoteTemplates", "quoteTemplate", S), lambda s: s.get("status") == "ACTIVE")

    sirket = istek("POST", "/rest/companies", {"name": ETIKET})["data"]["createCompany"]["id"]
    kapanis = (dt.date.today() + dt.timedelta(days=20)).isoformat() + "T12:00:00.000Z"
    F = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} F", "companyId": sirket, "stage": "PIPELINE",
                                              "closeDate": kapanis, "contractMonths": 12})["data"]["createOpportunity"]["id"]
    Q = istek("POST", "/rest/quotes", {"opportunityId": F, "validUntil": "2026-12-31"})["data"]["createQuote"]["id"]
    istek("POST", "/rest/quoteLines", {"quoteId": Q, "name": "Test kurulum", "quantity": 1, "sortOrder": 1, "billing": "ONE_TIME",
                                       "unitPrice": para(1000, "USD"), "unitCost": para(400, "USD"), "description": "Kurulum açıklaması"})
    istek("POST", "/rest/quoteLines", {"quoteId": Q, "name": "Test destek", "quantity": 2, "sortOrder": 2, "billing": "MONTHLY",
                                       "unitPrice": para(100, "USD"), "unitCost": para(40, "USD")})
    q = bekle(lambda: tek("quotes", "quote", Q), lambda q: q.get("quoteTemplateId") and (q.get("currencyBreakdown") or {}).get("USD", {}).get("gelir") == 3400)
    kontrol("Teklife varsayılan şablon ve toplam (1.000 + 2 × 100 × 12 = 3.400 USD)", q.get("quoteTemplateId") == S
            and (q.get("currencyBreakdown") or {}).get("USD", {}).get("gelir") == 3400, (q.get("quoteTemplateId"), q.get("currencyBreakdown")))

    istek("PATCH", f"/rest/quotes/{Q}", {"documentSections": [{"sira": 1, "dahil": False}, {"sira": 2, "dahil": False}],
                                         "documentRequest": "BOTH"})
    q = bekle(lambda: tek("quotes", "quote", Q), lambda q: not q.get("documentRequest") and q.get("documentStatus"), 240)
    dosyalar = q.get("documents") or []
    kontrol("Word + PDF üretildi", (q.get("documentStatus") or "").startswith("Üretildi") and
            sorted(d["label"].rsplit(".", 1)[-1] for d in dosyalar) == ["docx", "pdf"], (q.get("documentStatus"), dosyalar))
    if len(dosyalar) < 2:
        return
    w = next(d for d in dosyalar if d["label"].endswith(".docx"))
    pdf = next(d for d in dosyalar if d["label"].endswith(".pdf"))
    kontrol("PDF geçerli", indir(pdf["url"]).startswith(b"%PDF"))
    i = incele(indir(w["url"]))
    kontrol("Bölümler: Hakkımızda çıktı, kapak (çıkarılamaz) kaldı", i["bolumler"] ==
            ["Ana kapak", "Mevcut durum", "Teklif", "Ürün açıklamaları", "Ticari koşullar"], i["bolumler"])
    kontrol("Yer tutucu kalmadı", i["yer_tutucular"] == [], i["yer_tutucular"])
    kontrol("CRM değerleri: müşteri, toplam, sürüm, geçerlilik", f"{ETIKET} için hazırlanmıştır" in i["metin"]
            and "Toplam: 3.400,00 USD" in i["metin"] and i["ust"] == "Teklif 1"
            and any(["Geçerlilik", "31.12.2026"] in t for t in i["tablolar"]), (i["metin"][:300], i["ust"]))
    kontrol("Doldurulan alan şablonun varsayılan metniyle", "Varsayılan durum metni" in i["metin"], i["metin"][:400])
    kalem = next((t for t in i["tablolar"] if t and t[0][0] == "Kalem"), [])
    kontrol("Kalem tablosu ve toplam satırı", kalem[1:] == [
        ["Test kurulum", "1", "1.000,00 USD", "", "Tek seferlik", "1.000,00 USD"],
        ["Test destek", "2", "100,00 USD", "", "Aylık × 12 ay", "2.400,00 USD"],
        ["Toplam (USD)", "", "", "", "", "3.400,00 USD"]], kalem)
    kontrol("Ürün açıklaması (teklife özel kalemin açıklaması)", "Kurulum açıklaması" in i["metin"])

    istek("PATCH", f"/rest/quotes/{Q}", {"fillValues": {"musteri_durumu": "Satışçının yazdığı metin"}, "documentRequest": "NATIVE"})
    q = bekle(lambda: tek("quotes", "quote", Q), lambda q: not q.get("documentRequest") and (q.get("documents") or [{}])[0].get("fileId") != w.get("fileId"), 240)
    dosyalar = q.get("documents") or []
    i = incele(indir(dosyalar[0]["url"])) if dosyalar else {"metin": ""}
    kontrol("Satışçının yazdığı alan varsayılanın yerine geçti; yalnız Word", "Satışçının yazdığı metin" in i["metin"]
            and [d["label"].rsplit(".", 1)[-1] for d in dosyalar] == ["docx"], ([d["label"] for d in dosyalar], i["metin"][:300]))

    for x in eski_varsayilan:
        istek("PATCH", f"/rest/quoteTemplates/{x}", {"isDefault": True})   # testten önceki varsayılan geri


def temizle():
    for f in [x for x in liste("opportunities") if x["name"].startswith(ETIKET)]:
        for q in liste("quotes", f"&filter=opportunityId[eq]:{f['id']}"):
            for l in liste("quoteLines", f"&filter=quoteId[eq]:{q['id']}"):
                istek("DELETE", f"/rest/quoteLines/{l['id']}")
            istek("DELETE", f"/rest/quotes/{q['id']}")
        for s in liste("stageChanges", f"&filter=opportunityId[eq]:{f['id']}"):
            istek("DELETE", f"/rest/stageChanges/{s['id']}")
        istek("DELETE", f"/rest/opportunities/{f['id']}")
    for r in liste("companies"):
        if ETIKET in (r.get("name") or ""):
            istek("DELETE", f"/rest/companies/{r['id']}")
    for s in liste("quoteTemplates"):
        if ETIKET in (s.get("name") or ""):
            for b in liste("templateSections", f"&filter=quoteTemplateId[eq]:{s['id']}"):
                istek("DELETE", f"/rest/templateSections/{b['id']}")
            istek("DELETE", f"/rest/quoteTemplates/{s['id']}")
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
