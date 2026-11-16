#!/usr/bin/env python3
"""Teklif şablonu uçtan uca testi (liste 15a, deneme ortamı; test kayıtlarını siler).
Plan: kararlar/2026-11-13-teklif-modulu-plan.md (15a kararları). Kullanım (sunucuda): python3 ops/sablon-testi.py [temizle]

Örnek dosyalar belge servisinin nötr örnek üreticisinden (belge/testler/ornek_uret.py): yalnız yer tutucu, rakam yok.
1. Word: bölümler Başlık 1'e göre, türler yer tutuculardan önerilir, üst bilgi yer tutucusu genel listede.
2. Kullanıcının bölüm seçimi dosya yeniden yüklenince korunur.
3. PowerPoint: slayt = bölüm, notla birleşme, başlıksız slayt uyarısı.
4. Varsayılan tek; dosyasız şablon Aktif olamaz; okunamayan dosya uyarı verir.
5. Yeni teklife varsayılan aktif şablon gelir.
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
ETIKET = "TEST şablon - silinecek"
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


def ornek(ad):
    subprocess.run(["docker", "exec", "belge-servisi", "python3", "-m", "testler.ornek_uret", "/tmp"], check=True, capture_output=True)
    return subprocess.run(["docker", "exec", "belge-servisi", "cat", f"/tmp/{ad}"], check=True, capture_output=True).stdout


ALAN_ID = None


def yukle(sid, ad, icerik):
    global ALAN_ID
    if not ALAN_ID:
        ALAN_ID = next(f["node"]["id"] for e in gql("{ objects(paging:{first:200}) { edges { node { nameSingular "
                                                     "fields(paging:{first:500}) { edges { node { id name } } } } } } }")["objects"]["edges"]
                       if e["node"]["nameSingular"] == "quoteTemplate" for f in e["node"]["fields"]["edges"] if f["node"]["name"] == "templateFile")
    t = gql("mutation($n:String!,$s:Float!,$a:String!){ createFileUpload(filename:$n,size:$s,fileFolder:FilesField,"
            "fieldMetadataId:$a){ fileId uploadUrl contentType } }", {"n": ad, "s": len(icerik), "a": ALAN_ID})["createFileUpload"]
    url = B + "/" + t["uploadUrl"].split("/", 3)[3]
    urllib.request.urlopen(urllib.request.Request(url, method="PUT", data=icerik, headers={"Content-Type": t["contentType"]}), timeout=60)
    gql("mutation($f:String!){ completeFileUpload(fileId:$f){ id } }", {"f": t["fileId"]})
    istek("PATCH", f"/rest/quoteTemplates/{sid}", {"templateFile": [{"fileId": t["fileId"], "label": ad}]})
    return t["fileId"]


def sablon(ad):
    return istek("POST", "/rest/quoteTemplates", {"name": f"{ETIKET} {ad}"})["data"]["createQuoteTemplate"]["id"]


def okundu(sid, fid):
    return bekle(lambda: tek("quoteTemplates", "quoteTemplate", sid), lambda s: s.get("readFileId") == fid)


def bolumler(sid):
    return sorted(liste("templateSections", f"&filter=quoteTemplateId[eq]:{sid}"), key=lambda b: b.get("sortOrder") or 0)


def calistir():
    docx, pptx = ornek("ornek-sablon.docx"), ornek("ornek-sablon.pptx")

    W = sablon("Word")
    s = okundu(W, yukle(W, "ornek-sablon.docx", docx))
    b = bolumler(W)
    ozet = [(x["name"], x["sectionType"], x.get("autoContent"), x["removable"]) for x in b]
    kontrol("Word: bölümler ve önerilen türler", ozet == [
        ("Ana kapak", "FIXED", None, False), ("Hakkımızda", "FIXED", None, True), ("Mevcut durum", "FILL", None, True),
        ("Teklif", "AUTO", "LINE_TABLE", False), ("Ürün açıklamaları", "AUTO", "PRODUCT_DESCRIPTIONS", True),
        ("Ticari koşullar", "FIXED", None, True)] and s.get("format") == "DOCX", ozet)
    yt = {x["ad"]: (x["tur"], x["bolumler"]) for x in s.get("placeholders") or []}
    kontrol("Word: yer tutucular (üst bilgi, tablo, tanınmayan)", yt.get("teklif_no") == ("crm", ["üst / alt bilgi"])
            and yt.get("gecerlilik") == ("crm", ["Ticari koşullar"]) and yt.get("musteri_durumu") == ("doldurulacak", ["Mevcut durum"])
            and yt.get("kalem_tablosu", ("",))[0] == "otomatik" and not s.get("readWarnings"), (yt, s.get("readWarnings")))

    hak = next(x for x in b if x["name"] == "Hakkımızda")
    istek("PATCH", f"/rest/templateSections/{hak['id']}", {"sectionType": "FILL", "defaultText": "Kısa tanıtım"})
    okundu(W, yukle(W, "ornek-sablon-v2.docx", docx))
    hak2 = next((x for x in bolumler(W) if x["name"] == "Hakkımızda"), {})
    kontrol("Yeniden yüklemede kullanıcı seçimi korundu", hak2.get("id") == hak["id"] and hak2.get("sectionType") == "FILL"
            and hak2.get("defaultText") == "Kısa tanıtım", hak2)

    istek("PATCH", f"/rest/quoteTemplates/{W}", {"status": "ACTIVE", "isDefault": True})
    P = sablon("PowerPoint")
    s = okundu(P, yukle(P, "ornek-sablon.pptx", pptx))
    ozet = [(x["name"], x["sourceRef"], x["sectionType"]) for x in bolumler(P)]
    kontrol("PowerPoint: slayt bölümleri, notla birleşme", ozet == [
        ("Ana kapak", "slayt 1", "FIXED"), ("Hakkımızda", "slayt 2", "FIXED"), ("Çözüm", "slayt 3–4", "FILL"),
        ("Teklif", "slayt 5", "AUTO"), ("Slayt 6", "slayt 6", "FIXED")] and s.get("format") == "PPTX", ozet)
    kontrol("PowerPoint: başlıksız slayt uyarısı", "Slayt 6" in (s.get("readWarnings") or ""), s.get("readWarnings"))

    istek("PATCH", f"/rest/quoteTemplates/{P}", {"status": "ACTIVE", "isDefault": True})
    w = bekle(lambda: tek("quoteTemplates", "quoteTemplate", W), lambda w: w.get("isDefault") is False)
    kontrol("Varsayılan tek: yeni varsayılan seçilince eskisi kalktı", w.get("isDefault") is False
            and tek("quoteTemplates", "quoteTemplate", P).get("isDefault") is True)

    Bos = sablon("dosyasız")
    istek("PATCH", f"/rest/quoteTemplates/{Bos}", {"status": "ACTIVE"})
    x = bekle(lambda: tek("quoteTemplates", "quoteTemplate", Bos), lambda x: x.get("status") == "DRAFT" and x.get("readWarnings"))
    kontrol("Dosyasız şablon Aktif olamaz", x.get("status") == "DRAFT" and "Aktif" in (x.get("readWarnings") or ""), x.get("readWarnings"))

    Kotu = sablon("bozuk")
    fid = yukle(Kotu, "not.txt", b"duz metin")
    x = okundu(Kotu, fid)
    kontrol("Okunamayan dosyada uyarı", (x.get("readWarnings") or "").startswith("Okunamadı"), x.get("readWarnings"))

    sirket = istek("POST", "/rest/companies", {"name": ETIKET})["data"]["createCompany"]["id"]
    kapanis = (dt.date.today() + dt.timedelta(days=20)).isoformat() + "T12:00:00.000Z"
    F = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} F", "companyId": sirket, "stage": "PIPELINE",
                                              "closeDate": kapanis, "contractMonths": 12})["data"]["createOpportunity"]["id"]
    Q = istek("POST", "/rest/quotes", {"opportunityId": F})["data"]["createQuote"]["id"]
    q = bekle(lambda: tek("quotes", "quote", Q), lambda q: q.get("quoteTemplateId"))
    kontrol("Yeni teklife varsayılan aktif şablon geldi", q.get("quoteTemplateId") == P, q.get("quoteTemplateId"))


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
