#!/usr/bin/env python3
"""Tanıtım (video) verisi (liste 28; kullanıcı kararı 15 Kas 2026: gerçek veri silindi, video için tüm adım ve süreçler
için veri). TÜM KAYITLAR HAYALİDİR: şirket, kişi, tutar ve fiyatlar tanıtım içindir; alan adları ayrılmış ".example"
uzantısıdır (gerçek kurum değildir). Canlı DocuSign / e-posta gösterimi için "Selin Ateş" kişisinin e-postası
TANITIM_IMZACI_EPOSTA ortam değişkeniyle gerçek bir deneme kutusuna yönlendirilebilir.
Ortam: TANITIM_SAHIP (fırsat sahibi üyenin adı; boşsa adı "Test" ile başlamayan ilk üye), TANITIM_IMZACI_EPOSTA.

Lead aşamalarında tutar 1 USD (değer henüz bilinmez). Zenginleştirme (katalog, temas, not, görev, rakip, hedef):
ops/tanitim-zenginlestir.py sonunda çağrılır.
Süreçler: her aşamada fırsat (Lead-Gen → DSQ), aşama geçmişi, teklif (katalog + teklife özel kalem, şablon, PDF),
marj onayı (Ege Gıda saha teklifi), kanal ortağı payı, kabul → sipariş belgesi → Audit (sözleşme) → Delivery → Invoice → Won, temaslar (arama,
e-posta, toplantı, LinkedIn), ileri tarihli toplantı (planlı görüşme), temassız fırsat, rakip sözleşmesi yenilemesi,
görevler, Q4 2026 hedefleri. Kurallar hesap motorundan geçer (motor açık olmalı).
Kullanım (sunucuda): python3 ops/tanitim-verisi.py   (önce ops/is-verisi-temizle.py; tekrar çalıştırmaz: şirket varsa durur)
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
BUGUN = dt.date.today()


def istek(m, yol, govde=None):
    r = urllib.request.Request(B + yol, method=m, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + K})
    for _ in range(10):
        try:
            time.sleep(0.5)   # motorla aynı anahtar: dakikada 100 istek sınırı
            return json.loads(urllib.request.urlopen(r, timeout=120).read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20)
                continue
            raise SystemExit(f"{m} {yol}: {e.code} {e.read().decode()[:300]}")


def gql(q, v=None):
    d = istek("POST", "/metadata", {"query": q, "variables": v or {}})
    if d.get("errors"):
        raise SystemExit(str(d["errors"])[:300])
    return d["data"]


def liste(p, f=""):
    return istek("GET", f"/rest/{p}?limit=200{f}")["data"][p]


def yeni(cogul, tekil, govde):
    return istek("POST", f"/rest/{cogul}", govde)["data"]["create" + tekil[0].upper() + tekil[1:]]["id"]


def tek(p, tekil, i):
    return istek("GET", f"/rest/{p}/{i}")["data"][tekil]


def guncelle(p, i, govde):
    istek("PATCH", f"/rest/{p}/{i}", govde)


def bekle(f, kosul, sure=180, aralik=6):
    for _ in range(sure // aralik):
        x = f()
        if kosul(x):
            return x
        time.sleep(aralik)
    return f()


def para(t, k):
    return {"amountMicros": int(round(t * 1e6)), "currencyCode": k}


def gun(n):
    return (BUGUN + dt.timedelta(days=n)).isoformat()


def an(n, saat=10):
    return (dt.datetime.combine(BUGUN + dt.timedelta(days=n), dt.time(saat, 0)) - dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")


if liste("companies"):
    sys.exit("çalışma alanında şirket var: önce ops/is-verisi-temizle.py (tanıtım verisi boş alana kurulur)")

UYE = {f"{u['name']['firstName']} {u['name']['lastName']}": u["id"] for u in liste("workspaceMembers")}
SAHIP_AD = os.environ.get("TANITIM_SAHIP") or next(a for a in UYE if not a.startswith("Test"))
SAHIP, SATIS, YONETICI = UYE[SAHIP_AD], UYE["Test Satış"], UYE["Test Yönetici"]
IMZACI_EPOSTA = os.environ.get("TANITIM_IMZACI_EPOSTA", "selin.ates@zirveegitim.example")
KATALOG = {c["name"]: c["id"] for c in liste("catalogItems")}
Q4 = next(p["id"] for p in liste("reportingPeriods") if p["name"] == "Q4 2026")

# ---------------- şirketler ve kişiler (hayali) ----------------
SIRKETLER = [
    ("Kuzey Lojistik A.Ş.", "kuzeylojistik", "Lojistik", 420, "İstanbul", [("Murat", "Kaya", "Satış Direktörü"), ("Elif", "Demir", "İK Müdürü")]),
    ("Mavi Yazılım Teknolojileri", "maviyazilim", "Yazılım", 160, "Ankara", [("Burak", "Yılmaz", "Genel Müdür"), ("Ayşe", "Çelik", "Satış Müdürü")]),
    ("Poyraz Enerji Çözümleri", "poyrazenerji", "Enerji", 310, "İzmir", [("Kerem", "Aydın", "Ticari Direktör"), ("Zeynep", "Arslan", "Eğitim Uzmanı")]),
    ("Delta Medikal Cihazlar", "deltamedikal", "Sağlık", 220, "İstanbul", [("Emre", "Koç", "Satış ve Pazarlama Direktörü"), ("Gizem", "Şahin", "Bölge Satış Müdürü")]),
    ("Ege Gıda Sanayi", "egegida", "Gıda", 650, "Manisa", [("Hakan", "Öztürk", "Satış Genel Müdür Yardımcısı"), ("Derya", "Kılıç", "İK Direktörü")]),
    ("Pera Finans Teknolojileri", "perafinans", "Finans teknolojisi", 95, "İstanbul", [("Can", "Erdem", "Kurucu Ortak"), ("Seda", "Güneş", "Büyüme Müdürü")]),
    ("Toros Otomotiv Yan Sanayi", "torosotomotiv", "Otomotiv", 880, "Bursa", [("Serkan", "Polat", "Satış Direktörü"), ("Melis", "Avcı", "Kurumsal Gelişim Müdürü")]),
    ("Nova Telekom Hizmetleri", "novatelekom", "Telekom", 540, "İstanbul", [("Onur", "Yıldız", "Kurumsal Satış Direktörü"), ("Ece", "Aksoy", "Satış Operasyon Müdürü")]),
    ("Vadi İnşaat Malzemeleri", "vadiinsaat", "İnşaat malzemeleri", 260, "Kocaeli", [("Tolga", "Kurt", "Satış Müdürü"), ("Pınar", "Özkan", "İK Uzmanı")]),
    ("Lale Perakende", "laleperakende", "Perakende", 1200, "İstanbul", [("Barış", "Çetin", "Mağazacılık Direktörü"), ("Ceren", "Yalçın", "Eğitim Müdürü")]),
    ("Zirve Eğitim Kurumları", "zirveegitim", "Eğitim", 140, "Ankara", [("Selin", "Ateş", "Genel Müdür"), ("Okan", "Bulut", "Kurumsal İlişkiler Müdürü")]),
]
SIRKET, KISI = {}, {}
for ad, alan, sektor, calisan, il, kisiler in SIRKETLER:
    sid = yeni("companies", "company", {"name": ad, "domainName": {"primaryLinkUrl": f"https://{alan}.example"}, "sector": sektor,
                                        "employeeCount": calisan, "address": {"addressCity": il, "addressCountry": "Türkiye"},
                                        "accountManagerId": SATIS if len(SIRKET) % 2 else SAHIP})
    SIRKET[ad] = sid
    for i, (a, s, unvan) in enumerate(kisiler):
        eposta = IMZACI_EPOSTA if (a, s) == ("Selin", "Ateş") else f"{a.lower()}.{s.lower()}@{alan}.example"
        eposta = eposta.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
        KISI[f"{a} {s}"] = yeni("people", "person", {"name": {"firstName": a, "lastName": s}, "jobTitle": unvan, "companyId": sid,
                                                    "emails": {"primaryEmail": eposta}, "dataSource": "MANUAL"})
print(f"şirket {len(SIRKET)}, kişi {len(KISI)}")

ORTAK = yeni("partners", "partner", {"name": "Anadolu İş Ortakları Danışmanlık", "partnerType": ["CHANNEL"],
                                     "domainName": {"primaryLinkUrl": "https://anadoluisortaklari.example"},
                                     "note": "Tanıtım: kanal ortağı (satış payı %10)"})

# ---------------- fırsatlar ----------------
# (ad, şirket, sahip, hedef aşama, kaynak, ICP, kapanış (gün), muhatap, teklif tanımı ya da elle tutar)
FIRSATLAR = [
    ("Lale Perakende - Mağaza satış eğitimi", "Lale Perakende", SATIS, "LEAD_GEN", "INBOUND", "HIGH", 75, "Ceren Yalçın", {"tek": 1}),
    ("Vadi İnşaat - Bayi satış koçluğu", "Vadi İnşaat Malzemeleri", SATIS, "LEAD_GEN", "OUTBOUND", "MEDIUM", 90, "Tolga Kurt", {"tek": 1}),
    ("Nova Telekom - Kurumsal satış süreci", "Nova Telekom Hizmetleri", SAHIP, "LEAD_IN_TOUCH", "EVENT", "HIGH", 70, "Onur Yıldız", {"tek": 1}),
    ("Toros Otomotiv - Satış koçluğu 6 ay", "Toros Otomotiv Yan Sanayi", SAHIP, "PIPELINE", "REFERRAL", "HIGH", 45, "Serkan Polat", "toros"),
    ("Ege Gıda - Saha satış eğitimi", "Ege Gıda Sanayi", SATIS, "PIPELINE", "OUTBOUND", "MEDIUM", 60, "Hakan Öztürk", "ege"),
    ("Pera Finans - Satış ve CRM danışmanlığı", "Pera Finans Teknolojileri", SAHIP, "UPSIDE", "CHANNEL", "HIGH", 30, "Can Erdem", "pera"),
    ("Zirve Eğitim - Satış koçluğu 12 ay", "Zirve Eğitim Kurumları", SAHIP, "COMMIT", "INBOUND", "HIGH", 20, "Selin Ateş", "zirve"),
    ("Delta Medikal - Eğitim ve koçluk", "Delta Medikal Cihazlar", SATIS, "COMMIT", "REFERRAL", "MEDIUM", 25, "Emre Koç", "delta"),
    ("Poyraz Enerji - Satış koçluğu", "Poyraz Enerji Çözümleri", SAHIP, "AUDIT", "OUTBOUND", "HIGH", 10, "Kerem Aydın", "poyraz"),
    ("Mavi Yazılım - Satış süreci danışmanlığı", "Mavi Yazılım Teknolojileri", SATIS, "DELIVERY", "INBOUND", "HIGH", 5, "Burak Yılmaz", "mavi"),
    ("Kuzey Lojistik - Satış eğitimi 2. faz", "Kuzey Lojistik A.Ş.", SAHIP, "INVOICE", "EXISTING_CUSTOMER", "HIGH", 3, "Murat Kaya", "kuzey2"),
    ("Kuzey Lojistik - Satış eğitimi 1. faz", "Kuzey Lojistik A.Ş.", SAHIP, "WON", "REFERRAL", "HIGH", 1, "Murat Kaya", "kuzey1"),
    ("Ege Gıda - CRM uyarlama", "Ege Gıda Sanayi", SATIS, "LOST", "OUTBOUND", "LOW", 15, "Derya Kılıç", {"tek": 9000}),
    ("Vadi İnşaat - Kurumsal akademi", "Vadi İnşaat Malzemeleri", SATIS, "DISQUALIFIED", "INBOUND", "LOW", 40, "Pınar Özkan", {"tek": 7000}),
]
# Teklif tanımları: katalog (Sales Coaching, aylık 2.500 USD liste / 1.000 maliyet) + teklife özel kalemler (tanıtım fiyatları)
OZEL = {
    "atolye": ("Satış eğitimi atölyesi (2 gün)", 1, 6000, 2400, "USD", "ONE_TIME", "PERSONNEL", "Uygulamalı atölye, 20 katılımcıya kadar."),
    "analiz": ("Satış süreci analizi", 1, 4000, 1500, "USD", "ONE_TIME", "PERSONNEL", "Mevcut satış sürecinin haritalanması ve iyileştirme raporu."),
    "crm": ("CRM kurulum ve uyarlama", 1, 6500, 2600, "USD", "ONE_TIME", "SUBCONTRACT", "Twenty CRM kurulumu, alan ve süreç uyarlaması."),
    "saha": ("Saha satış eğitimi (3 bölge)", 1, 9000, 8500, "USD", "ONE_TIME", "SUBCONTRACT", "Üç bölgede saha eğitimi, taşeron eğitmenle."),
    "egitim_tl": ("Yönetici satış eğitimi (1 gün)", 1, 120000, 45000, "TRY", "ONE_TIME", "PERSONNEL", "Satış yöneticileri için bir günlük program."),
}
TEKLIFLER = {
    "toros": {"ay": 6, "katalog": [("Sales Coaching", 2, 2400)], "ozel": ["analiz"], "durum": "DRAFT"},
    "pera": {"ay": 6, "katalog": [("Sales Coaching", 1, 2500)], "ozel": ["crm", "analiz"], "durum": "SENT", "kanal": 10},
    "zirve": {"ay": 12, "katalog": [("Sales Coaching", 2, 2300)], "ozel": ["atolye"], "durum": "DRAFT", "imzaci": "Selin Ateş"},
    "ege": {"ay": 1, "katalog": [], "ozel": ["saha"], "durum": "SENT"},   # marj %10 altı → onay bekler
    "delta": {"ay": 6, "katalog": [("Sales Coaching", 1, 1150)], "ozel": ["atolye"], "durum": "SENT"},   # pazarlıklı fiyat
    "poyraz": {"ay": 12, "katalog": [("Sales Coaching", 1, 2500)], "ozel": ["egitim_tl"], "durum": "ACCEPTED"},
    "mavi": {"ay": 6, "katalog": [("Sales Coaching", 1, 2500)], "ozel": ["analiz", "crm"], "durum": "ACCEPTED"},
    "kuzey2": {"ay": 3, "katalog": [], "ozel": ["atolye", "egitim_tl"], "durum": "ACCEPTED"},
    "kuzey1": {"ay": 3, "katalog": [("Sales Coaching", 1, 2500)], "ozel": ["atolye"], "durum": "ACCEPTED"},
}
SIRA = ["LEAD_GEN", "LEAD_IN_TOUCH", "PIPELINE", "UPSIDE", "COMMIT"]
ALANLAR = {f["node"]["name"]: f["node"]["id"] for e in gql("{ objects(paging:{first:200}) { edges { node { nameSingular "
          "fields(paging:{first:500}) { edges { node { id name } } } } } } }")["objects"]["edges"]
          if e["node"]["nameSingular"] == "opportunity" for f in e["node"]["fields"]["edges"]}


def dosya_yukle(alan, ad, icerik):
    t = gql("mutation($n:String!,$s:Float!,$a:String!){ createFileUpload(filename:$n,size:$s,fileFolder:FilesField,"
            "fieldMetadataId:$a){ fileId uploadUrl contentType } }", {"n": ad, "s": len(icerik), "a": ALANLAR[alan]})["createFileUpload"]
    urllib.request.urlopen(urllib.request.Request(B + "/" + t["uploadUrl"].split("/", 3)[3], method="PUT", data=icerik,
                                                  headers={"Content-Type": t["contentType"]}), timeout=60)
    gql("mutation($f:String!){ completeFileUpload(fileId:$f){ id } }", {"f": t["fileId"]})
    return {"fileId": t["fileId"], "label": ad}


def teklif_kur(fid, ad, tanim):
    q = yeni("quotes", "quote", {"opportunityId": fid, "contractMonths": tanim["ay"], "validUntil": gun(21),
                                 **({"channelShareRate": tanim["kanal"], "channelShareBase": "REVENUE"} if tanim.get("kanal") else {}),
                                 **({"signerId": KISI[tanim["imzaci"]]} if tanim.get("imzaci") else {})})
    sira = 1
    for kat, miktar, fiyat in tanim["katalog"]:
        yeni("quoteLines", "quoteLine", {"quoteId": q, "catalogItemId": KATALOG[kat], "quantity": miktar, "sortOrder": sira,
                                         "unitPrice": para(fiyat, "USD")})
        sira += 1
    for k in tanim["ozel"]:
        n, miktar, fiyat, maliyet, pb, odeme, tur, aciklama = OZEL[k]
        yeni("quoteLines", "quoteLine", {"quoteId": q, "name": n, "quantity": miktar, "sortOrder": sira, "billing": odeme,
                                         "unitPrice": para(fiyat, pb), "unitCost": para(maliyet, pb), "costType": tur,
                                         "description": aciklama})
        sira += 1
    bekle(lambda: tek("quotes", "quote", q), lambda t: t.get("revenueReporting") and t.get("quoteTemplateId"))
    guncelle("quotes", q, {"documentRequest": "BOTH"})
    t = bekle(lambda: tek("quotes", "quote", q), lambda t: not t.get("documentRequest") and t.get("documentStatus"), 300)
    print(f"  teklif: {t.get('name')} · {t.get('documentStatus')}")
    if tanim["durum"] in ("SENT", "ACCEPTED"):
        guncelle("quotes", q, {"status": "SENT"})
        t = bekle(lambda: tek("quotes", "quote", q), lambda t: t.get("sentAt") or t.get("status") == "PENDING_APPROVAL")
    if tanim["durum"] == "ACCEPTED" and t.get("status") == "SENT":
        guncelle("quotes", q, {"status": "ACCEPTED"})
        t = bekle(lambda: tek("quotes", "quote", q), lambda t: t.get("status") == "ACCEPTED")
    return t


def asama(fid, hedef, ek=None):
    guncelle("opportunities", fid, {"stage": hedef, **(ek or {})})
    return bekle(lambda: tek("opportunities", "opportunity", fid), lambda f: f.get("stage") == hedef and not f.get("systemWarning"), 120)


FIRSAT = {}
for ad, sirket, sahip, hedef, kaynak, icp, kapanis, muhatap, tutar in FIRSATLAR:
    govde = {"name": ad, "companyId": SIRKET[sirket], "ownerId": sahip, "stage": "LEAD_GEN", "leadSource": kaynak, "icpFit": icp,
             "closeDate": an(kapanis, 15), "pointOfContactId": KISI[muhatap]}
    if isinstance(tutar, dict):
        govde.update({"oneTimeFee": para(tutar["tek"], "USD")} if "tek" in tutar else
                     {"monthlyRecurring": para(tutar["aylik"], "USD"), "contractMonths": tutar["ay"]})
    if kaynak == "CHANNEL":
        govde["channelPartnerId"] = ORTAK
    fid = yeni("opportunities", "opportunity", govde)
    FIRSAT[ad] = fid
    time.sleep(4)
    # açık aşamalara sırayla ilerle (aşama geçmişi oluşsun)
    son = hedef if hedef in SIRA else "COMMIT"
    for a in SIRA[1:SIRA.index(son) + 1]:
        asama(fid, a)
    if isinstance(tutar, str):
        t = teklif_kur(fid, ad, TEKLIFLER[tutar])
        if hedef in ("AUDIT", "DELIVERY", "INVOICE", "WON"):
            pdf = next(d for d in t["documents"] if d["label"].endswith(".pdf"))
            icerik = urllib.request.urlopen(B + "/" + pdf["url"].split("/", 3)[3], timeout=60).read()
            guncelle("opportunities", fid, {"orderDocument": [dosya_yukle("orderDocument", f"Sipariş onayı - {ad}.pdf", icerik)]})
            time.sleep(4)
            asama(fid, "AUDIT")
            if hedef in ("DELIVERY", "INVOICE", "WON"):
                asama(fid, "DELIVERY", {"contractStatus": "SIGNED", "deliveryStatus": "IN_PROGRESS"})
            if hedef in ("INVOICE", "WON"):
                asama(fid, "INVOICE", {"deliveryStatus": "DONE", "invoicingStatus": "IN_PROGRESS"})
            if hedef == "WON":
                asama(fid, "WON", {"invoicingStatus": "DONE"})
    if hedef in ("LOST", "DISQUALIFIED"):
        asama(fid, hedef, {"closeReason": "Bütçe önceliği değişti, proje gelecek yıla ertelendi." if hedef == "LOST"
                          else "Hedef profile uymuyor: satış ekibi 3 kişi, ihtiyaç bireysel eğitim."})
    print(f"fırsat: {ad} → {tek('opportunities', 'opportunity', fid).get('stage')}")

# ---------------- temaslar ----------------
# (fırsat, kişi, tür, yön, sonuç, gün (eksi = geçmiş), yapan, özet)
TEMASLAR = [
    ("Lale Perakende - Mağaza satış eğitimi", "Ceren Yalçın", "EMAIL", "INBOUND", "POSITIVE", -3, SATIS, "Web sitesinden eğitim talebi geldi"),
    ("Vadi İnşaat - Bayi satış koçluğu", "Tolga Kurt", "LINKEDIN", "OUTBOUND", "NO_REPLY", -5, SATIS, "LinkedIn bağlantı mesajı"),
    ("Nova Telekom - Kurumsal satış süreci", "Onur Yıldız", "MEETING", "OUTBOUND", "POSITIVE", -12, SAHIP, "Etkinlik sonrası tanışma görüşmesi"),
    ("Nova Telekom - Kurumsal satış süreci", "Ece Aksoy", "CALL", "OUTBOUND", "MEETING_BOOKED", -4, SAHIP, "İhtiyaç analizi toplantısı planlandı"),
    ("Toros Otomotiv - Satış koçluğu 6 ay", "Serkan Polat", "MEETING", "OUTBOUND", "POSITIVE", -20, SAHIP, "İhtiyaç analizi: bölge müdürleri için koçluk"),
    ("Toros Otomotiv - Satış koçluğu 6 ay", "Melis Avcı", "EMAIL", "OUTBOUND", "POSITIVE", -6, SAHIP, "Kapsam taslağı gönderildi"),
    ("Toros Otomotiv - Satış koçluğu 6 ay", "Serkan Polat", "MEETING", "OUTBOUND", None, 3, SAHIP, "Teklif sunumu (planlı)"),
    ("Ege Gıda - Saha satış eğitimi", "Hakan Öztürk", "CALL", "OUTBOUND", "POSITIVE", -9, SATIS, "Saha ekibi eğitim ihtiyacı konuşuldu"),
    ("Pera Finans - Satış ve CRM danışmanlığı", "Can Erdem", "MEETING", "INBOUND", "POSITIVE", -25, SAHIP, "Kanal ortağı yönlendirmesiyle tanışma"),
    ("Pera Finans - Satış ve CRM danışmanlığı", "Seda Güneş", "EMAIL", "OUTBOUND", "NO_REPLY", -15, SAHIP, "Teklif gönderildi"),
    ("Zirve Eğitim - Satış koçluğu 12 ay", "Selin Ateş", "MEETING", "OUTBOUND", "POSITIVE", -10, SAHIP, "Koçluk programı sunumu"),
    ("Zirve Eğitim - Satış koçluğu 12 ay", "Okan Bulut", "CALL", "INBOUND", "POSITIVE", -2, SAHIP, "Sözleşme süresi 12 ay olarak netleşti"),
    ("Delta Medikal - Eğitim ve koçluk", "Emre Koç", "MEETING", "OUTBOUND", "POSITIVE", -8, SATIS, "Bütçe görüşmesi: indirim talebi"),
    ("Poyraz Enerji - Satış koçluğu", "Kerem Aydın", "MEETING", "OUTBOUND", "POSITIVE", -18, SAHIP, "Teklif kabul edildi"),
    ("Mavi Yazılım - Satış süreci danışmanlığı", "Ayşe Çelik", "MEETING", "OUTBOUND", "POSITIVE", -6, SATIS, "Proje başlangıç toplantısı"),
    ("Kuzey Lojistik - Satış eğitimi 2. faz", "Elif Demir", "EMAIL", "INBOUND", "POSITIVE", -4, SAHIP, "2. faz katılımcı listesi geldi"),
    ("Ege Gıda - CRM uyarlama", "Derya Kılıç", "CALL", "OUTBOUND", "NEGATIVE", -7, SATIS, "Proje gelecek yıla ertelendi"),
]
for f, k, kanal, yon, sonuc, g, yapan, ozet in TEMASLAR:
    fid = FIRSAT[f]
    yeni("touchpoints", "touchpoint", {"name": f"{ozet}", "channel": kanal, "direction": yon, "occurredAt": an(g, 11),
                                       "personId": KISI[k], "companyId": tek("opportunities", "opportunity", fid)["companyId"],
                                       "opportunityId": fid, "performedById": yapan, "summary": ozet,
                                       **({"result": sonuc} if sonuc else {})})
print(f"temas {len(TEMASLAR)}")

# ---------------- görevler, rakip hizmetleri, hedefler ----------------
for baslik, kime, g, f in [("Delta Medikal: indirim talebi için yöneticiyle görüş", SATIS, 1, "Delta Medikal - Eğitim ve koçluk"),
                           ("Poyraz Enerji: sözleşme imzasını takip et", SAHIP, 2, "Poyraz Enerji - Satış koçluğu"),
                           ("Mavi Yazılım: 2. atölye tarihini netleştir", SATIS, 4, "Mavi Yazılım - Satış süreci danışmanlığı")]:
    gid = yeni("tasks", "task", {"title": baslik, "status": "TODO", "assigneeId": kime, "dueAt": an(g, 9)})
    yeni("taskTargets", "taskTarget", {"taskId": gid, "targetOpportunityId": FIRSAT[f]})
for sirket, rakip, hizmet, bitis in [("Lale Perakende", "Örnek Eğitim Danışmanlık Ltd.", "Mağaza satış eğitimi", 60),
                                     ("Nova Telekom Hizmetleri", "Örnek CRM Yazılım A.Ş.", "CRM lisansı", 75),
                                     ("Vadi İnşaat Malzemeleri", "Örnek Akademi", "Bayi eğitimi", 200)]:
    yeni("competitorServices", "competitorService", {"name": f"{sirket} - {hizmet}", "companyId": SIRKET[sirket], "competitor": rakip,
                                                     "service": hizmet, "contractEnd": gun(bitis)})
for uye, ad, gelir, brut in [(SAHIP, f"{SAHIP_AD} Q4 2026", 90000, 45000), (SATIS, "Test Satış Q4 2026", 45000, 20000)]:
    h = yeni("targets", "target", {"name": ad, "memberId": uye, "periodId": Q4, "targetRole": "PERSONAL"})
    yeni("targetLines", "targetLine", {"name": f"{ad} - Gelir", "targetId": h, "metric": "REVENUE", "targetAmount": para(gelir, "USD"), "weightPercent": 70})
    yeni("targetLines", "targetLine", {"name": f"{ad} - Brüt kâr", "targetId": h, "metric": "GROSS_PROFIT", "targetAmount": para(brut, "USD"), "weightPercent": 30})
import subprocess  # noqa: E402
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tanitim-zenginlestir.py")], check=True)
print("TANITIM-TAMAM")
