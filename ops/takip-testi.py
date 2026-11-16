#!/usr/bin/env python3
"""Takip kuralları uçtan uca testi (deneme ortamı). Karar: kararlar/2026-11-13-takip-kurallari.md

Kullanım (sunucuda):
  python3 ops/takip-testi.py kur        # test kayıtlarını açar, motorun işaretlemesini doğrular
  (Takip iş akışının saatlik çalışmasını bekle: her saat 10. dakika, UTC)
  python3 ops/takip-testi.py dogrula    # görevleri, bağlantıyı, durumun temizlenmesini ve tekrar açılmamasını doğrular; siler
  python3 ops/takip-testi.py temizle    # yalnız test kayıtlarını siler

Senaryolar:
  A: Lead-inTouch, BDM = Test Yönetici, Sahip = Test Satış, son temas 10 gün önce (eşik 7) → Temassızlık, sorumlu BDM
  B: Pipeline, Sahip = Test Satış, 3 gün sonra planlı görüşme → Planlı görüşme, o tarihe görev, sorumlu Sahip
  C: Pipeline, son temas 20 gün önce ama ileri tarihli açık görev var → görev açılmaz (bastırma)
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
ETIKET = "TEST takip - silinecek"


def istek(m, yol, govde=None):
    r = urllib.request.Request(B + yol, method=m, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Authorization": "Bearer " + K, "Content-Type": "application/json"})
    for _ in range(8):
        try:
            return json.loads(urllib.request.urlopen(r).read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429:   # API sınırı (motorla aynı anahtar): bekle, yeniden dene
                time.sleep(15)
                continue
            raise SystemExit(f"{m} {yol}: {e.code} {e.read().decode()[:300]}")


def liste(plural, filtre=""):
    return istek("GET", f"/rest/{plural}?limit=200{filtre}")["data"][plural]


def iso(a):
    return a.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def uye(ad):
    return next(m["id"] for m in liste("workspaceMembers") if f"{m['name']['firstName']} {m['name']['lastName']}" == ad)


def test_firsatlari():
    return {o["name"]: o for o in liste("opportunities") if o["name"].startswith(ETIKET)}


def bekle_motor(kosul, sure=90):
    for _ in range(sure // 5):
        time.sleep(5)
        f = test_firsatlari()
        if kosul(f):
            return f
    return test_firsatlari()


def kur():
    if test_firsatlari():
        raise SystemExit("Önceki test kayıtları duruyor: önce 'temizle'.")
    simdi = dt.datetime.now(dt.timezone.utc)
    satis, yonetici = uye("Test Satış"), uye("Test Yönetici")
    sirket = istek("POST", "/rest/companies", {"name": ETIKET})["data"]["createCompany"]["id"]
    A = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} A", "companyId": sirket, "stage": "LEAD_IN_TOUCH",
                                              "ownerId": satis, "bdmId": yonetici})["data"]["createOpportunity"]["id"]
    Bf = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} B", "companyId": sirket, "stage": "PIPELINE",
                                               "ownerId": satis})["data"]["createOpportunity"]["id"]
    C = istek("POST", "/rest/opportunities", {"name": f"{ETIKET} C", "companyId": sirket, "stage": "PIPELINE",
                                              "ownerId": satis})["data"]["createOpportunity"]["id"]
    for oid, gun in ((A, -10), (Bf, 3), (C, -20)):
        istek("POST", "/rest/touchpoints", {"opportunityId": oid, "companyId": sirket, "direction": "OUTBOUND",
                                            "occurredAt": iso(simdi + dt.timedelta(days=gun))})
    g = istek("POST", "/rest/tasks", {"title": f"{ETIKET} C ileri görev", "status": "TODO", "assigneeId": satis,
                                      "dueAt": iso(simdi + dt.timedelta(days=5))})["data"]["createTask"]["id"]
    istek("POST", "/rest/taskTargets", {"taskId": g, "targetOpportunityId": C})
    f = bekle_motor(lambda f: f.get(f"{ETIKET} A", {}).get("followUpStatus") and f.get(f"{ETIKET} B", {}).get("followUpStatus"))
    a, b, c = f[f"{ETIKET} A"], f[f"{ETIKET} B"], f[f"{ETIKET} C"]
    sonuc = [
        ("A Temassızlık", a.get("followUpStatus") == "INACTIVITY"),
        ("A sorumlu BDM (Test Yönetici)", a.get("followUpAssigneeId") == yonetici),
        ("A temassız gün 10", a.get("daysWithoutTouch") == 10),
        ("B Planlı görüşme", b.get("followUpStatus") == "MEETING"),
        ("B sorumlu Sahip (Test Satış)", b.get("followUpAssigneeId") == satis),
        ("B görev tarihi = görüşme", (b.get("followUpDueAt") or "")[:16] == iso(simdi + dt.timedelta(days=3))[:16]),
        ("C bastırıldı (ileri tarihli görev)", not c.get("followUpStatus") and c.get("daysWithoutTouch") == 20),
    ]
    # Liste 11: rakip sözleşme bitişine 60 gün → şirketin AM'ine görev (bir kez); 200 gün → görev yok
    istek("PATCH", f"/rest/companies/{sirket}", {"accountManagerId": yonetici})
    R1 = istek("POST", "/rest/competitorServices", {"name": f"{ETIKET} R1", "companyId": sirket, "competitor": "Rakip A",
                                                    "service": "Eğitim", "contractEnd": (simdi + dt.timedelta(days=60)).date().isoformat()})["data"]["createCompetitorService"]["id"]
    R2 = istek("POST", "/rest/competitorServices", {"name": f"{ETIKET} R2", "companyId": sirket, "competitor": "Rakip B",
                                                    "contractEnd": (simdi + dt.timedelta(days=200)).date().isoformat()})["data"]["createCompetitorService"]["id"]
    rg = []
    for _ in range(30):
        time.sleep(3)
        rg = [t for t in liste("tasks") if (t.get("title") or "").startswith("Rakip sözleşmesi bitiyor") and ETIKET in t["title"]]
        if rg:
            break
    time.sleep(40)   # bir tur daha: ikinci görev açılmamalı
    rg = [t for t in liste("tasks") if (t.get("title") or "").startswith("Rakip sözleşmesi bitiyor") and ETIKET in t["title"]]
    r1 = istek("GET", f"/rest/competitorServices/{R1}")["data"]["competitorService"]
    sonuc += [
        ("Rakip 60 gün kala: tek görev, şirketin AM'ine", len(rg) == 1 and rg[0].get("assigneeId") == yonetici and "Rakip A" in rg[0]["title"]),
        ("Rakip: Hatırlatılan Bitiş yazıldı", (r1.get("renewalRemindedFor") or "")[:10] == r1["contractEnd"][:10]),
        ("Rakip 200 gün: görev yok", not any("Rakip B" in t["title"] for t in rg)),
    ]
    for ad, ok in sonuc:
        print(("GEÇTİ " if ok else "KALDI ") + ad)
    print("A:", a.get("followUpTitle"), "| B:", b.get("followUpTitle"))
    if not all(ok for _, ok in sonuc):
        sys.exit(1)


def gorevleri(oid):
    ids = {h["taskId"] for h in liste("taskTargets", f"&filter=targetOpportunityId[eq]:{oid}")}
    return [t for t in liste("tasks") if t["id"] in ids]


def dogrula():
    f = test_firsatlari()
    if not f:
        raise SystemExit("Test kaydı yok: önce 'kur'.")
    a, b = f[f"{ETIKET} A"], f[f"{ETIKET} B"]
    ga, gb = gorevleri(a["id"]), gorevleri(b["id"])
    sonuc = [
        ("A için görev açıldı (Takip:)", any(t["title"].startswith("Takip:") for t in ga)),
        ("A görevi BDM'e atandı", any(t.get("assigneeId") == a.get("followUpAssigneeId") or t.get("assigneeId") == uye("Test Yönetici") for t in ga)),
        ("B için görev açıldı (Görüşme:)", any(t["title"].startswith("Görüşme:") for t in gb)),
        ("A ve B Takip Durumu temizlendi", not a.get("followUpStatus") and not b.get("followUpStatus")),
    ]
    time.sleep(40)   # motorun bir tur daha hesaplaması: açık görev varken yeniden işaretlememeli
    f = test_firsatlari()
    sonuc.append(("Motor yeniden işaretlemedi", not f[f"{ETIKET} A"].get("followUpStatus") and not f[f"{ETIKET} B"].get("followUpStatus")))
    for ad, ok in sonuc:
        print(("GEÇTİ " if ok else "KALDI ") + ad)
    for t in ga + gb:
        print("  görev:", t["title"], "|", (t.get("dueAt") or "")[:16])
    temizle()
    if not all(ok for _, ok in sonuc):
        sys.exit(1)


def temizle():
    f = test_firsatlari()
    for o in f.values():
        for t in gorevleri(o["id"]):
            for h in liste("taskTargets", f"&filter=taskId[eq]:{t['id']}"):
                istek("DELETE", f"/rest/taskTargets/{h['id']}")
            istek("DELETE", f"/rest/tasks/{t['id']}")
        for t in liste("touchpoints", f"&filter=opportunityId[eq]:{o['id']}"):
            istek("DELETE", f"/rest/touchpoints/{t['id']}")
        for s in liste("stageChanges", f"&filter=opportunityId[eq]:{o['id']}"):
            istek("DELETE", f"/rest/stageChanges/{s['id']}")
        istek("DELETE", f"/rest/opportunities/{o['id']}")
    for r in liste("competitorServices"):
        if (r.get("name") or "").startswith(ETIKET):
            for h in liste("taskTargets", f"&filter=targetCompetitorServiceId[eq]:{r['id']}"):
                istek("DELETE", f"/rest/taskTargets/{h['id']}")
            istek("DELETE", f"/rest/competitorServices/{r['id']}")
    for c in liste("companies"):
        if c["name"] == ETIKET:
            for h in liste("taskTargets", f"&filter=targetCompanyId[eq]:{c['id']}"):
                istek("DELETE", f"/rest/taskTargets/{h['id']}")
            istek("DELETE", f"/rest/companies/{c['id']}")
    for t in liste("tasks"):   # motorun açtığı yetki onayı, rakip hatırlatması vb. test görevleri
        if ETIKET in (t.get("title") or ""):
            istek("DELETE", f"/rest/tasks/{t['id']}")
    print("temizlik: kalan test fırsatı", len(test_firsatlari()))


{"kur": kur, "dogrula": dogrula, "temizle": temizle}[sys.argv[1] if len(sys.argv) > 1 else "kur"]()
