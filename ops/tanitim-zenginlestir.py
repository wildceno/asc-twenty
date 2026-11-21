#!/usr/bin/env python3
"""Tanıtım verisini video için zenginleştirir (kullanıcı istekleri 16 Kas 2026). TÜM KAYITLAR HAYALİDİR.
- Tutarlar: Lead aşamalarında 1 USD (fırsat netleşmeden değer bilinmez); Pipeline'da teklif gönderilmemiş ama elle
  tahmini değer; Commit'teki taslak teklif gönderilir (değer tekliften gelir).
- Katalog kalemleri, temaslar (her fırsata), notlar, görevler (her fırsata açık / tamamlanmış), rakip hizmetleri,
  hedefler (Q4 2026 yönetici + Q1 2027 kişisel).
ops/tanitim-verisi.py sonunda çağrılır; tek başına da çalışır. Tekrar çalışınca çoğaltmaz (ad kontrolü).
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motor"))
from ascendia_motor.cekirdek.metin import zengin_metin  # noqa: E402

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


def liste(p, f=""):
    return istek("GET", f"/rest/{p}?limit=200{f}")["data"][p]


def yeni(cogul, tekil, govde):
    return istek("POST", f"/rest/{cogul}", govde)["data"]["create" + tekil[0].upper() + tekil[1:]]["id"]


def guncelle(p, i, govde):
    istek("PATCH", f"/rest/{p}/{i}", govde)


def para(t, k="USD"):
    return {"amountMicros": None if t is None else int(round(t * 1e6)), "currencyCode": k}


def an(n, saat=10):
    return (dt.datetime.combine(BUGUN + dt.timedelta(days=n), dt.time(saat, 0)) - dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")


def gun(n):
    return (BUGUN + dt.timedelta(days=n)).isoformat()


UYE = {f"{u['name']['firstName']} {u['name']['lastName']}": u["id"] for u in liste("workspaceMembers")}
SAHIP_AD = os.environ.get("TANITIM_SAHIP") or next(a for a in UYE if not a.startswith("Test"))
FIRSAT = {o["name"]: o for o in liste("opportunities")}
SIRKET = {c["name"]: c["id"] for c in liste("companies")}
KISI = {f"{p['name']['firstName']} {p['name']['lastName']}": p for p in liste("people")}
if "Zirve Eğitim - Satış koçluğu 12 ay" not in FIRSAT:
    sys.exit("tanıtım verisi yok: önce ops/tanitim-verisi.py")


def f(k):
    """Fırsat adının başıyla (benzersiz önek)."""
    return next(o for a, o in FIRSAT.items() if a.startswith(k))


# ---------------- 1) tutarlar ----------------
for o in FIRSAT.values():
    if o["stage"] in ("LEAD_GEN", "LEAD_IN_TOUCH"):
        guncelle("opportunities", o["id"], {"oneTimeFee": para(1), "monthlyRecurring": para(None), "annualRecurring": para(None)})
guncelle("opportunities", f("Toros")["id"], {"oneTimeFee": para(4000), "monthlyRecurring": para(4800), "contractMonths": 6,
                                              "oneTimeCost": para(1500), "monthlyCost": para(2000)})
guncelle("opportunities", f("Ege Gıda - Saha")["id"], {"oneTimeFee": para(9500), "oneTimeCost": para(7600)})
zirve = next(q for q in liste("quotes") if q.get("opportunityId") == f("Zirve")["id"])
if zirve["status"] == "DRAFT":
    guncelle("quotes", zirve["id"], {"status": "SENT"})
print("tutarlar tamam")

# ---------------- 2) katalog ----------------
KATALOG = [
    ("Satış eğitimi atölyesi (2 gün)", "ONE_TIME", "atölye", 6000, 2400, "USD", "PERSONNEL",
     "Uygulamalı iki günlük satış atölyesi, 20 katılımcıya kadar.",
     "Program: keşif soruları, değer önerisi, itiraz yönetimi, kapanış.\nRol oyunları ve vaka çalışmaları.\nKatılımcı başına çalışma kitabı."),
    ("Yönetici satış eğitimi (1 gün)", "ONE_TIME", "gün", 120000, 45000, "TRY", "PERSONNEL",
     "Satış yöneticileri için bir günlük program.",
     "Pipeline yönetimi ve forecast disiplini.\nKoçluk görüşmesi yapısı.\nEkip performans göstergeleri."),
    ("Satış süreci analizi", "ONE_TIME", "proje", 4000, 1500, "USD", "PERSONNEL",
     "Mevcut satış sürecinin haritalanması ve iyileştirme raporu.",
     "Görüşmeler ve CRM verisi incelemesi.\nAşama tanımları ve dönüşüm oranları.\nÖnceliklendirilmiş iyileştirme planı."),
    ("Satış playbook hazırlama", "ONE_TIME", "proje", 5000, 1800, "USD", "PERSONNEL",
     "Şirkete özel satış oyun kitabı.",
     "Hedef müşteri profili ve alıcı rolleri.\nAşama bazında yapılacaklar ve çıkış kriterleri.\nE-posta ve görüşme şablonları."),
    ("CRM kurulum ve uyarlama (Twenty)", "ONE_TIME", "proje", 6500, 2600, "USD", "SUBCONTRACT",
     "Twenty CRM kurulumu, alan ve süreç uyarlaması.",
     "Veri modeli ve satış aşamaları.\nTeklif modülü ve şablon.\nVeri taşıma ve kullanıcı eğitimi."),
    ("CRM barındırma ve bakım", "MONTHLY", "ay", 300, 90, "USD", "LICENSE",
     "Yönetilen sunucu, yedek, güncelleme ve izleme.",
     "AB bölgesinde sunucu.\nGünlük yedek ve geri yükleme testi.\nSürüm yükseltmeleri."),
    ("Bireysel satış koçluğu", "MONTHLY", "kişi/ay", 900, 350, "USD", "PERSONNEL",
     "Satış temsilcisine aylık birebir koçluk.",
     "Ayda iki birebir görüşme.\nGerçek fırsatlar üzerinden çalışma.\nAylık gelişim notu."),
    ("Yıllık destek paketi", "YEARLY", "yıl", 3000, 1000, "USD", "PERSONNEL",
     "Eğitim sonrası bir yıl boyunca danışmanlık desteği.",
     "Çeyreklik değerlendirme toplantısı.\nE-posta ile soru-cevap.\nPlaybook güncellemesi."),
    ("LinkedIn ile satış eğitimi (yarım gün)", "ONE_TIME", "oturum", 2000, 700, "USD", "PERSONNEL",
     "Sosyal satış ve LinkedIn ile müşteri bulma.",
     "Profil ve içerik.\nHedef listesi ve mesaj dizileri.\nÖlçüm."),
]
mevcut = {c["name"] for c in liste("catalogItems")}
for ad, odeme, birim, fiyat, maliyet, pb, tur, kisa, detay in KATALOG:
    if ad in mevcut:
        continue
    yeni("catalogItems", "catalogItem", {"name": ad, "billing": odeme, "unit": birim, "listPrice": para(fiyat, pb),
                                         "unitCost": para(maliyet, pb), "costType": tur, "kind": "SERVICE", "active": True,
                                         "shortDescription": kisa, "details": zengin_metin(detay)})
print("katalog tamam")

# ---------------- 3) temaslar ----------------
# (fırsat öneki, kişi, kanal, yön, sonuç, gün, özet)
TEMASLAR = [
    ("Lale", "Barış Çetin", "LINKEDIN", "OUTBOUND", "POSITIVE", -6, "Mağazacılık direktörüyle LinkedIn bağlantısı"),
    ("Lale", "Ceren Yalçın", "CALL", "OUTBOUND", "MEETING_BOOKED", -1, "Tanışma toplantısı ayarlandı"),
    ("Vadi İnşaat - Bayi", "Tolga Kurt", "EMAIL", "OUTBOUND", "NO_REPLY", -12, "Bayi satış koçluğu tanıtım e-postası"),
    ("Vadi İnşaat - Bayi", "Tolga Kurt", "CALL", "OUTBOUND", "POSITIVE", -2, "Geri arama: bayi ağı 40 nokta"),
    ("Nova", "Onur Yıldız", "EMAIL", "INBOUND", "POSITIVE", -10, "Etkinlik sunumunun dosyası istendi"),
    ("Nova", "Ece Aksoy", "LINKEDIN", "OUTBOUND", "POSITIVE", -7, "Satış operasyonu ile bağlantı"),
    ("Toros", "Serkan Polat", "CALL", "OUTBOUND", "POSITIVE", -30, "Referansla ilk görüşme"),
    ("Toros", "Melis Avcı", "MEETING", "OUTBOUND", "POSITIVE", -13, "Bölge müdürleriyle ihtiyaç atölyesi"),
    ("Toros", "Serkan Polat", "EMAIL", "INBOUND", "POSITIVE", -3, "Bütçe onayı süreci soruldu"),
    ("Ege Gıda - Saha", "Hakan Öztürk", "MEETING", "OUTBOUND", "POSITIVE", -21, "Saha ekibiyle tanışma"),
    ("Ege Gıda - Saha", "Derya Kılıç", "EMAIL", "OUTBOUND", "POSITIVE", -5, "Eğitim takvimi önerisi gönderildi"),
    ("Pera", "Can Erdem", "CALL", "OUTBOUND", "POSITIVE", -40, "Kanal ortağının yönlendirmesi"),
    ("Pera", "Seda Güneş", "MEETING", "OUTBOUND", "POSITIVE", -32, "CRM ihtiyaç analizi"),
    ("Zirve", "Selin Ateş", "EMAIL", "INBOUND", "POSITIVE", -24, "Koçluk programı talebi"),
    ("Zirve", "Okan Bulut", "MEETING", "OUTBOUND", "POSITIVE", -16, "Kurumsal ilişkilerle kapsam görüşmesi"),
    ("Zirve", "Selin Ateş", "EMAIL", "OUTBOUND", "POSITIVE", -1, "Teklif gönderildi"),
    ("Delta", "Gizem Şahin", "CALL", "OUTBOUND", "POSITIVE", -19, "Bölge ekiplerinin ihtiyacı"),
    ("Delta", "Emre Koç", "EMAIL", "INBOUND", "POSITIVE", -4, "İndirimli fiyat kabul edildi, onay bekleniyor"),
    ("Poyraz", "Kerem Aydın", "CALL", "OUTBOUND", "POSITIVE", -35, "İlk görüşme"),
    ("Poyraz", "Zeynep Arslan", "MEETING", "OUTBOUND", "POSITIVE", -26, "Eğitim ihtiyacı analizi"),
    ("Poyraz", "Kerem Aydın", "EMAIL", "INBOUND", "POSITIVE", -3, "Sözleşme taslağı hukuka iletildi"),
    ("Mavi", "Burak Yılmaz", "MEETING", "OUTBOUND", "POSITIVE", -45, "Genel müdürle tanışma"),
    ("Mavi", "Ayşe Çelik", "CALL", "OUTBOUND", "POSITIVE", -20, "Teklif detayları"),
    ("Mavi", "Burak Yılmaz", "EMAIL", "INBOUND", "POSITIVE", -2, "1. atölye geri bildirimi olumlu"),
    ("Kuzey Lojistik - Satış eğitimi 2", "Murat Kaya", "MEETING", "OUTBOUND", "POSITIVE", -25, "2. faz kapsamı"),
    ("Kuzey Lojistik - Satış eğitimi 2", "Murat Kaya", "CALL", "OUTBOUND", "POSITIVE", -9, "Fatura bilgileri teyit edildi"),
    ("Kuzey Lojistik - Satış eğitimi 1", "Murat Kaya", "MEETING", "OUTBOUND", "POSITIVE", -80, "1. faz başlangıç"),
    ("Kuzey Lojistik - Satış eğitimi 1", "Elif Demir", "EMAIL", "INBOUND", "POSITIVE", -60, "Katılımcı memnuniyet anketi sonuçları"),
    ("Ege Gıda - CRM", "Hakan Öztürk", "MEETING", "OUTBOUND", "POSITIVE", -30, "CRM ihtiyacı konuşuldu"),
    ("Vadi İnşaat - Kurumsal", "Pınar Özkan", "CALL", "INBOUND", "NEGATIVE", -14, "Bireysel eğitim talebi, kapsam dışı"),
]
var = {(t.get("opportunityId"), t.get("name")) for t in liste("touchpoints")}
for fk, k, kanal, yon, sonuc, g, ozet in TEMASLAR:
    o = f(fk)
    if (o["id"], ozet) in var:
        continue
    yeni("touchpoints", "touchpoint", {"name": ozet, "summary": ozet, "channel": kanal, "direction": yon, "result": sonuc,
                                       "occurredAt": an(g, 11 + (abs(g) % 6)), "personId": KISI[k]["id"], "companyId": o["companyId"],
                                       "opportunityId": o["id"], "performedById": o["ownerId"]})
print("temaslar tamam")

# ---------------- 4) notlar ----------------
NOTLAR = [
    ("Lale", "İlk izlenim", "Mağaza sayısı 120. Eğitim mağaza müdürleri üzerinden yayılmak isteniyor.\nKarar verici: mağazacılık direktörü."),
    ("Nova", "Etkinlik notu", "Kurumsal satış ekibi 35 kişi. Satış süreci bölgeden bölgeye farklı.\nCRM'de aşama tanımı yok."),
    ("Toros", "İhtiyaç analizi özeti", "Bölge müdürleri haftalık pipeline toplantısı yapmıyor.\nÖncelik: koçluk ritmi ve forecast disiplini.\nBütçe: ilk yarıyıl."),
    ("Ege Gıda - Saha", "Saha ekibi yapısı", "3 bölge, 45 saha satış temsilcisi.\nEğitim bölge bazında, taşeron eğitmenle verilecek."),
    ("Pera", "Kanal ortağı payı", "Yönlendiren iş ortağına gelir üzerinden %10 pay. Teklife yansıtıldı."),
    ("Zirve", "Karar süreci", "Genel müdür onaylıyor, kurumsal ilişkiler süreci yürütüyor.\nSözleşme süresi 12 ay, aylık koçluk."),
    ("Delta", "Fiyat görüşmesi", "Koçluk aylık fiyatında indirim istendi. Marj kuralı nedeniyle yönetici onayı gerekebilir."),
    ("Poyraz", "Sözleşme notu", "Teklif kabul edildi; sözleşme hukuk incelemesinde. Başlangıç tarihi imzaya bağlı."),
    ("Mavi", "Proje planı", "1. atölye tamamlandı. 2. atölye ve CRM uyarlaması önümüzdeki ay."),
    ("Kuzey Lojistik - Satış eğitimi 2", "Fatura", "Tek seferlik eğitim bedeli; fatura teslimden sonra kesilecek."),
    ("Kuzey Lojistik - Satış eğitimi 1", "Kapanış değerlendirmesi", "Katılımcı memnuniyeti yüksek. 2. faz için referans oldu."),
    ("Ege Gıda - CRM", "Kayıp nedeni", "Bütçe önceliği değişti. Yeni yılın ikinci çeyreğinde tekrar görüşülecek."),
    ("Vadi İnşaat - Kurumsal", "Uygunluk", "Ekip küçük, kurumsal akademi ihtiyacı yok. Bayi koçluğu ayrı fırsat olarak açıldı."),
]
var = {n["title"] for n in liste("notes")}
for fk, baslik, metin in NOTLAR:
    o = f(fk)
    tam = f"{o['name'].split(' - ')[0]}: {baslik}"
    if tam in var:
        continue
    nid = yeni("notes", "note", {"title": tam, "bodyV2": zengin_metin(metin)})
    yeni("noteTargets", "noteTarget", {"noteId": nid, "targetOpportunityId": o["id"]})
    yeni("noteTargets", "noteTarget", {"noteId": nid, "targetCompanyId": o["companyId"]})
print("notlar tamam")

# ---------------- 5) görevler (her fırsata) ----------------
# (fırsat öneki, başlık, durum, gün)
GOREVLER = [
    ("Lale", "Tanışma toplantısı için sunum hazırla", "TODO", 2), ("Lale", "Mağaza sayısı ve yapısını araştır", "DONE", -4),
    ("Vadi İnşaat - Bayi", "Bayi listesi iste", "TODO", 3), ("Vadi İnşaat - Bayi", "Tanıtım e-postası gönder", "DONE", -12),
    ("Nova", "İhtiyaç analizi toplantısı gündemi", "IN_PROGRESS", 1), ("Nova", "Etkinlik sunumunu gönder", "DONE", -9),
    ("Toros", "Teklif sunumunu hazırla", "IN_PROGRESS", 2), ("Toros", "Bölge müdürü listesini al", "DONE", -12),
    ("Ege Gıda - Saha", "Taşeron eğitmen takvimini netleştir", "TODO", 5), ("Ege Gıda - Saha", "Saha ziyareti planla", "DONE", -18),
    ("Pera", "Kanal ortağıyla pay anlaşmasını imzala", "DONE", -30),
    ("Zirve", "İmza sürecini başlat", "TODO", 3), ("Zirve", "Kapsam toplantısı notlarını paylaş", "DONE", -15),
    ("Delta", "Fiyat onayını takip et", "IN_PROGRESS", 1), ("Delta", "Referans müşteri bilgisi gönder", "DONE", -10),
    ("Poyraz", "Sözleşme hukuk yorumlarını yanıtla", "TODO", 4), ("Poyraz", "Kabul edilen teklifi arşivle", "DONE", -5),
    ("Mavi", "2. atölye katılımcı listesi", "TODO", 6), ("Mavi", "1. atölye raporunu gönder", "DONE", -1),
    ("Kuzey Lojistik - Satış eğitimi 2", "Faturayı kes", "TODO", 2), ("Kuzey Lojistik - Satış eğitimi 2", "Teslim tutanağını al", "DONE", -6),
    ("Kuzey Lojistik - Satış eğitimi 1", "Memnuniyet anketini paylaş", "DONE", -58), ("Kuzey Lojistik - Satış eğitimi 1", "Referans görüşmesi iste", "DONE", -40),
    ("Ege Gıda - CRM", "Gelecek yıl için hatırlatma kur", "DONE", -7),
    ("Vadi İnşaat - Kurumsal", "Bayi koçluğu fırsatını aç", "DONE", -14),
]
var = {g["title"] for g in liste("tasks")}
for fk, baslik, durum, g in GOREVLER:
    o = f(fk)
    tam = f"{o['name'].split(' - ')[0]}: {baslik}"
    if tam in var:
        continue
    gid = yeni("tasks", "task", {"title": tam, "status": durum, "assigneeId": o["ownerId"], "dueAt": an(g, 9)})
    yeni("taskTargets", "taskTarget", {"taskId": gid, "targetOpportunityId": o["id"]})
print("görevler tamam")

# ---------------- 6) rakip hizmetleri ----------------
RAKIP = [("Kuzey Lojistik A.Ş.", "Örnek CRM Yazılım A.Ş.", "CRM lisansı", 45),
         ("Toros Otomotiv Yan Sanayi", "Örnek Eğitim Danışmanlık Ltd.", "Bayi satış eğitimi", 120),
         ("Delta Medikal Cihazlar", "Örnek Akademi", "Saha satış eğitimi", 30),
         ("Pera Finans Teknolojileri", "Örnek CRM Yazılım A.Ş.", "CRM lisansı", 80),
         ("Ege Gıda Sanayi", "Örnek Danışmanlık", "Satış koçluğu", 150),
         ("Mavi Yazılım Teknolojileri", "Örnek Teklif Yazılımı", "Teklif yazılımı", 20),
         ("Zirve Eğitim Kurumları", "Örnek Akademi", "Yönetici eğitimi", 300),
         ("Poyraz Enerji Çözümleri", "Örnek CRM Yazılım A.Ş.", "CRM lisansı", 60)]
var = {c["name"] for c in liste("competitorServices")}
for sirket, rakip, hizmet, bitis in RAKIP:
    ad = f"{sirket} - {hizmet}"
    if ad not in var:
        yeni("competitorServices", "competitorService", {"name": ad, "companyId": SIRKET[sirket], "competitor": rakip,
                                                         "service": hizmet, "contractEnd": gun(bitis)})
print("rakip hizmetleri tamam")

# ---------------- 7) hedefler ----------------
DONEM = {p["name"]: p["id"] for p in liste("reportingPeriods")}
HEDEF = [(UYE["Test Yönetici"], "Test Yönetici Q4 2026 (ekip)", "Q4 2026", "MANAGER", 150000, 70000),
         (UYE[SAHIP_AD], f"{SAHIP_AD} Q1 2027", "Q1 2027", "PERSONAL", 100000, 50000),
         (UYE["Test Satış"], "Test Satış Q1 2027", "Q1 2027", "PERSONAL", 50000, 22000)]
var = {t["name"] for t in liste("targets")}
for uye, ad, donem, rol, gelir, brut in HEDEF:
    if ad in var:
        continue
    h = yeni("targets", "target", {"name": ad, "memberId": uye, "periodId": DONEM[donem], "targetRole": rol})
    yeni("targetLines", "targetLine", {"name": f"{ad} - Gelir", "targetId": h, "metric": "REVENUE", "targetAmount": para(gelir), "weightPercent": 70})
    yeni("targetLines", "targetLine", {"name": f"{ad} - Brüt kâr", "targetId": h, "metric": "GROSS_PROFIT", "targetAmount": para(brut), "weightPercent": 30})
print("ZENGINLESTIRME-TAMAM")
