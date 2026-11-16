"""Paket FATURA (liste 21; kullanıcı kararları 15 Kas 2026): Paraşüt'te satış faturası ve tahsilat durumu.

- Fırsat Invoice aşamasına geçince geçerli (kabul edilmiş / gönderilmiş) tekliften fatura planı kurulur: tek seferlik
  kalemler ilk tarihte; aylık kalemler sözleşme süresince her ay, yıllık kalemler her yıl (son kısmi yıl orantılı), aynı
  gün. Her (tarih, para birimi) bir fatura; anahtar fırsat + tarih + para biriminden türetilen UUID (Paraşüt aynı anahtarla
  ikinci fatura açmaz). Tekrarlamayı motor yapar: Paraşüt API tekrarlama planını açmıyor (OpenAPI v4.1.0, 15 Kas).
- Fatura kaydı oluşturulur (item_type invoice); e-fatura / e-arşiv resmîleştirmesi Paraşüt'te elle.
- Cari: şirketin vergi numarası, yoksa adıyla aranır; yoksa oluşturulur; kimliği şirkete yazılır.
- KDV: teklif kaleminden, yoksa CRM Ayarı → Varsayılan KDV %; ikisi de yoksa fatura kesilmez, mesaj yazılır.
- İlk fatura kesilince fırsatın Faturalama durumu Tamamlandı. Tahsilat durumu 00/08/16'da (ve plan değişince) okunur.
Kimlik: OAuth2 (Paraşüt Keycloak); yenileme belirteci her kullanımda dönüşür ve oturum dosyasına yazılır.
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from ascendia_motor.cekirdek.ayar import TR
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.twenty import api, liste
from ascendia_motor.paketler.teklif_hesap import carpan, para, sayilan_kalemler, yil_dilimleri

AYAR_FILE = os.environ.get("PARASUT_AYAR_FILE", "/run/sirlar/parasut.json")
SECRET_FILE = os.environ.get("PARASUT_SECRET_FILE", "/run/sirlar/parasut_secret")
OTURUM_FILE = os.environ.get("PARASUT_OTURUM_FILE", "/run/parasut/oturum.json")
ANAHTAR_AD_ALANI = uuid.UUID("6f0e5a52-7c1d-4b4e-9a54-0b2f1c3d7e11")   # fatura anahtarları için sabit ad alanı
PB = {"TRY": "TRL"}   # Paraşüt Türk lirası kodu
TAHSILAT = {"paid": "PAID", "partially_paid": "PARTIAL", "unpaid": "UNPAID", "overdue": "OVERDUE"}
JSONAPI = "application/vnd.api+json"

_belirtec = {"deger": None, "bitis": 0}
_son_dilim = None


class AyarYok(Exception):
    pass


# ---------------- saf işlevler ----------------

def ay_ekle(gun, ay):
    """Tarihe ay ekler; ayın son günü taşarsa ayın son gününe çeker (31 Oca + 1 ay = 28/29 Şub)."""
    y, m = divmod(gun.month - 1 + ay, 12)
    yil, ay_ = gun.year + y, m + 1
    for g in (gun.day, 30, 29, 28):
        try:
            return dt.date(yil, ay_, g)
        except ValueError:
            continue
    raise ValueError(gun)


def fatura_anahtari(firsat_id, tarih, pb):
    return str(uuid.uuid5(ANAHTAR_AD_ALANI, f"{firsat_id}|{tarih}|{pb}"))


def fatura_plani(firsat_id, teklif, kalemler, baslangic, varsayilan_kdv):
    """Faturalar: [{'anahtar','tarih','pb','kalemler':[{ad, miktar, birim_fiyat, indirim, kdv}], 'tutar'}] (tarihe göre).
    Fiyat artışı (sabit % / enflasyon) yıl yıl birim fiyata uygulanır (teklif hesabıyla aynı kural)."""
    ay = teklif.get("contractMonths") or 0
    artis = teklif.get("priceEscalation") or "NONE"
    oran = float(teklif.get("priceEscalationRate") or 0)
    enf = ((teklif.get("inflationUsed") or {}).get("oranlar") or {})
    gruplar, eksik_kdv = {}, []
    for k in sayilan_kalemler(kalemler):
        fiyat, pb = para(k.get("unitPrice"))
        if not pb or not fiyat:
            continue
        kdv = k.get("vatRate") if k.get("vatRate") is not None else varsayilan_kdv
        if kdv is None:
            eksik_kdv.append(k.get("name") or "?")
            continue
        odeme = k.get("billing") or "ONE_TIME"
        k_ay = k.get("months") or ay
        if odeme == "ONE_TIME":
            donemler = [(baslangic, 1.0, 0)]
        elif odeme == "MONTHLY":
            donemler = [(ay_ekle(baslangic, i), 1.0, i // 12) for i in range(int(k_ay))]
        else:   # YEARLY: son kısmi yıl orantılı
            donemler = [(ay_ekle(baslangic, 12 * yil), tekrar, yil) for yil, tekrar in yil_dilimleri("YEARLY", k_ay)]
        for tarih, orani, yil in donemler:
            if artis == "FIXED":
                f_carpan = carpan([oran] * (yil + 1), yil)
            elif artis == "INFLATION":
                f_carpan = carpan(enf.get(pb, []), yil)
            else:
                f_carpan = 1.0
            satir = {"ad": k.get("name") or "", "miktar": round(float(k.get("quantity") or 0) * orani, 4),
                     "birim_fiyat": round(fiyat * f_carpan, 2), "indirim": float(k.get("discountPercent") or 0), "kdv": float(kdv)}
            g = gruplar.setdefault((tarih.isoformat(), pb), [])
            g.append(satir)
    plan = []
    for (tarih, pb), satirlar in sorted(gruplar.items()):
        tutar = round(sum(s["miktar"] * s["birim_fiyat"] * (1 - s["indirim"] / 100) for s in satirlar), 2)
        plan.append({"anahtar": fatura_anahtari(firsat_id, tarih, pb), "tarih": tarih, "pb": pb, "kalemler": satirlar,
                     "tutar": tutar, "durum": "PLANLANDI"})
    return plan, eksik_kdv


def adres_alanlari(sirket):
    """Şirketin Vergi No / Vergi Dairesi ve Fatura Adresi (Twenty ADDRESS alanı) → Paraşüt alanları (saf)."""
    a = sirket.get("billingAddress") or {}
    sokak = ", ".join(x for x in (a.get("addressStreet1"), a.get("addressStreet2")) if x)
    out = {"tax_number": sirket.get("taxNumber"), "tax_office": sirket.get("taxOffice"), "address": sokak or None,
           "city": a.get("addressCity"), "postal_code": a.get("addressPostcode"), "country": a.get("addressCountry")}
    return {k: v for k, v in out.items() if v}


def fatura_govdesi(fatura, cari_id, sirket, aciklama):
    ozn = {"item_type": "invoice", "issue_date": fatura["tarih"], "currency": PB.get(fatura["pb"], fatura["pb"]),
           "description": aciklama[:250]}
    for alan, deger in adres_alanlari(sirket).items():
        ozn["billing_address" if alan == "address" else "billing_postal_code" if alan == "postal_code" else alan] = deger
    return {"data": {"type": "sales_invoices", "attributes": ozn, "relationships": {
        "contact": {"data": {"id": str(cari_id), "type": "contacts"}},
        "details": {"data": [{"type": "sales_invoice_details", "attributes": {
            "quantity": s["miktar"], "unit_price": s["birim_fiyat"], "vat_rate": s["kdv"], "description": s["ad"][:250],
            **({"discount_type": "percentage", "discount_value": s["indirim"]} if s["indirim"] else {})}} for s in fatura["kalemler"]]},
        "external_reference_key": {"data": {"type": "external_reference_keys", "attributes": {"key": fatura["anahtar"]}}}}}}


def cari_govdesi(sirket):
    ozn = {"name": (sirket.get("name") or "")[:250], "account_type": "customer", "contact_type": "company"}
    ozn.update(adres_alanlari(sirket))
    return {"data": {"type": "contacts", "attributes": ozn}}


def tahsilat_ozeti(durumlar):
    """Kesilen faturaların ödeme durumlarından fırsatın Tahsilat Durumu (saf). Gecikmiş varsa Gecikmiş; hepsi ödendiyse
    Ödendi; hiç ödeme yoksa Ödenmedi; diğer Kısmen ödendi."""
    d = [x for x in durumlar if x]
    if not d:
        return None
    if "OVERDUE" in d:
        return "OVERDUE"
    if all(x == "PAID" for x in d):
        return "PAID"
    if all(x == "UNPAID" for x in d):
        return "UNPAID"
    return "PARTIAL"


# ---------------- Paraşüt bağlantısı ----------------

def ayar():
    try:
        a = json.load(open(AYAR_FILE))
    except (OSError, ValueError):
        a = {}
    if not all(a.get(k) for k in ("client_id", "company_id", "api", "token_url")):
        raise AyarYok("Paraşüt bağlantısı kurulmamış (ayar yok)")
    if not os.path.exists(OTURUM_FILE):
        raise AyarYok("Paraşüt oturumu yok (ops/parasut-baglan.py ile bir kez yetki verin)")
    return a


def belirtec(a):
    if _belirtec["deger"] and time.time() < _belirtec["bitis"] - 30:
        return _belirtec["deger"]
    o = json.load(open(OTURUM_FILE))
    veri = {"grant_type": "refresh_token", "client_id": a["client_id"], "refresh_token": o["refresh_token"]}
    if os.path.exists(SECRET_FILE) and os.path.getsize(SECRET_FILE):
        veri["client_secret"] = open(SECRET_FILE).read().strip()
    t = json.loads(urllib.request.urlopen(urllib.request.Request(a["token_url"], data=urllib.parse.urlencode(veri).encode()),
                                          timeout=30).read())
    if t.get("refresh_token"):   # dönen yenileme belirteci saklanır (dönüşümlü)
        gecici = OTURUM_FILE + ".yeni"
        with open(gecici, "w") as f:
            json.dump({"refresh_token": t["refresh_token"], "yenilendi": int(time.time())}, f)
        os.replace(gecici, OTURUM_FILE)
    _belirtec.update(deger=t["access_token"], bitis=time.time() + int(t.get("expires_in") or 300))
    return _belirtec["deger"]


def ps(a, yontem, yol, govde=None):
    url = f"{a['api'].rstrip('/')}/{a['company_id']}{yol}"
    r = urllib.request.Request(url, method=yontem, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Authorization": "Bearer " + belirtec(a), "Content-Type": JSONAPI, "Accept": JSONAPI})
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            return json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e:
        govde_ = e.read().decode(errors="replace")
        try:
            hata = json.loads(govde_)
        except ValueError:
            hata = {}
        raise ParasutHatasi(e.code, hata, govde_[:300])


class ParasutHatasi(Exception):
    def __init__(self, kod, govde, metin):
        super().__init__(f"Paraşüt {kod}: {metin}")
        self.kod, self.govde = kod, govde


def cari_bul_ya_da_olustur(a, sirket):
    if sirket.get("parasutContactId"):
        return sirket["parasutContactId"]
    bulunan = []
    if sirket.get("taxNumber"):
        bulunan = ps(a, "GET", "/contacts?" + urllib.parse.urlencode({"filter[tax_number]": sirket["taxNumber"]})).get("data") or []
    if not bulunan and sirket.get("name"):
        bulunan = [c for c in ps(a, "GET", "/contacts?" + urllib.parse.urlencode({"filter[name]": sirket["name"]})).get("data") or []
                   if (c.get("attributes") or {}).get("name", "").strip().lower() == sirket["name"].strip().lower()]
    cari = bulunan[0]["id"] if bulunan else ps(a, "POST", "/contacts", cari_govdesi(sirket))["data"]["id"]
    api("PATCH", f"/rest/companies/{sirket['id']}", {"parasutContactId": str(cari)})
    log(f"{sirket.get('name')}: Paraşüt carisi {'bulundu' if bulunan else 'oluşturuldu'}")
    return str(cari)


def fatura_kes(a, fatura, cari, sirket, aciklama):
    try:
        f = ps(a, "POST", "/sales_invoices", fatura_govdesi(fatura, cari, sirket, aciklama))["data"]
    except ParasutHatasi as e:
        mevcut = ((e.govde.get("errors") or [{}])[0].get("meta") or {}).get("sales_invoice_id") if e.kod == 422 else None
        if not mevcut:
            raise
        f = ps(a, "GET", f"/sales_invoices/{mevcut}")["data"]   # aynı anahtar: daha önce kesilmiş
    return f


# ---------------- işler ----------------

def _bugun():
    return dt.datetime.now(TR).date()


def firsat_isle(anahtar):
    """Invoice aşamasındaki fırsat: plan yoksa kur, vadesi gelen faturaları kes, tahsilatı güncelle."""
    fid = anahtar.split(":", 1)[1]
    f = (api("GET", f"/rest/opportunities/{fid}") or {}).get("opportunity") or {}
    if f.get("stage") not in ("INVOICE", "WON") and not f.get("invoiceSchedule"):
        return
    yama = {}
    try:
        a = ayar()
    except AyarYok as e:
        if f.get("parasutMessage") != str(e):
            api("PATCH", f"/rest/opportunities/{fid}", {"parasutMessage": str(e)})
        return
    plan = f.get("invoiceSchedule") or []
    if not plan:
        t = (api("GET", f"/rest/quotes/{f['currentQuoteId']}") or {}).get("quote") if f.get("currentQuoteId") else None
        if not t or t.get("status") not in ("ACCEPTED", "SENT"):
            api("PATCH", f"/rest/opportunities/{fid}", {"parasutMessage": "Fatura için kabul edilmiş (ya da gönderilmiş) geçerli teklif yok."})
            return
        kalemler = liste("quoteLines", filtre=f"quoteId[eq]:{t['id']}")
        plan, eksik = fatura_plani(fid, t, kalemler, _bugun(), Durum.varsayilan_kdv)
        if eksik:
            api("PATCH", f"/rest/opportunities/{fid}", {"parasutMessage": f"KDV oranı yok: {', '.join(eksik)} (kalemde ya da CRM Ayarı → Varsayılan KDV %)."})
            return
    sirket = (api("GET", f"/rest/companies/{f['companyId']}") or {}).get("company") if f.get("companyId") else None
    if not sirket:
        api("PATCH", f"/rest/opportunities/{fid}", {"parasutMessage": "Fırsatın şirketi yok: cari belirlenemedi."})
        return
    mesaj = None
    try:
        cari = cari_bul_ya_da_olustur(a, sirket)
        for p in plan:
            if p["durum"] == "PLANLANDI" and p["tarih"] <= _bugun().isoformat():
                fat = fatura_kes(a, p, cari, sirket, f"{f.get('name')} · {p['tarih']}")
                p.update(durum="KESILDI", fatura_id=fat["id"], fatura_no=(fat.get("attributes") or {}).get("invoice_no"))
                log(f"{f.get('name')}: Paraşüt faturası {p['tarih']} {p['pb']} {p['tutar']}")
            if p.get("fatura_id"):
                at = (ps(a, "GET", f"/sales_invoices/{p['fatura_id']}")["data"].get("attributes") or {})
                p["odeme"] = TAHSILAT.get(at.get("payment_status"))
                p["kalan"] = at.get("remaining")
    except ParasutHatasi as e:
        log(f"HATA Paraşüt ({f.get('name')}): {e}")
        mesaj = f"Paraşüt hatası: {str(e)[:250]}"
    yama.update({"invoiceSchedule": plan, "parasutCheckedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "parasutMessage": mesaj or f"{sum(1 for p in plan if p['durum'] == 'KESILDI')}/{len(plan)} fatura kesildi."})
    ozet = tahsilat_ozeti([p.get("odeme") for p in plan if p.get("fatura_id")])
    if ozet:
        yama["collectionStatus"] = ozet
    if any(p.get("fatura_id") for p in plan) and f.get("invoicingStatus") != "DONE":
        yama["invoicingStatus"] = "DONE"   # kullanıcı kararı: ilk fatura kesilince Faturalama tamamlandı
    api("PATCH", f"/rest/opportunities/{fid}", yama)


def zamanli(anahtar=None):
    """Yarım saatte bir; 00/08/16 dilimlerinde planı olan fırsatlar: vadesi gelen fatura, tahsilat güncellemesi."""
    global _son_dilim
    from ascendia_motor.paketler.imza import kontrol_dilimi
    dilim = kontrol_dilimi(dt.datetime.now(TR), _son_dilim)
    if not dilim:
        return
    _son_dilim = dilim
    for f in liste("opportunities", filtre="stage[in]:[INVOICE,WON]"):
        if f.get("invoiceSchedule") or f.get("stage") == "INVOICE":
            firsat_isle(f"fatura:{f['id']}")


# ---------------- paket tanımı ----------------
AD = "FATURA"
OLAYLAR = [(("opportunity.updated",), lambda ad, kayit: [f"fatura:{kayit['id']}"]
            if kayit.get("id") and kayit.get("stage") == "INVOICE" and "stage" in (kayit.get("_degisen") or []) else [])]
ISLER = {"fatura": firsat_isle, "fatura_zaman": zamanli}
PERIYODIK = ["fatura_zaman"]
