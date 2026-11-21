"""Teklif şablonu (liste 15a; TEKLIF paketinin parçası). Plan: kararlar/2026-11-13-teklif-modulu-plan.md, 15a kararları.

Şablon kaydına dosya yüklenince (ya da dosya değişince) dosya indirilir, belge servisine gönderilir; dönen bölümler
Şablon Bölümü kayıtlarına, yer tutucular şablona yazılır. Kullanıcının bölüm seçimleri (tür, otomatik içerik,
kaldırılabilir, varsayılan metin) aynı adlı bölümde korunur. Varsayılan şablon tektir; Aktif yalnız okunmuş şablon olur.
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from ascendia_motor.cekirdek.ayar import API
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.twenty import api, liste

BELGE_URL = os.environ.get("BELGE_URL", "http://belge-servisi:8090").rstrip("/")

# Yer tutucu sözlüğü: belge üretiminde (15b) CRM'den dolanlar. Ad → açıklama.
CRM_ALANLARI = {
    "musteri_adi": "Müşteri (şirket) adı",
    "firsat_adi": "Fırsat adı",
    "teklif_adi": "Teklif adı",
    "teklif_no": "Teklif sürüm numarası",
    "teklif_tarihi": "Belgenin üretildiği gün",
    "gecerlilik": "Teklifin geçerlilik tarihi",
    "sure_ay": "Sözleşme süresi (ay)",
    "hazirlayan": "Fırsat sahibi (ad soyad)",
    "toplam": "Para birimine göre teklif toplamı",
    "imza": "DocuSign imza yeri: imzalayanın imzası buraya konur (belgede görünmez)",
}
OTOMATIK = {"kalem_tablosu": ("LINE_TABLE", "Otomatik bölüm: kalem tablosu (kalem, miktar, birim fiyat, indirim, tutar)"),
            "urun_aciklamalari": ("PRODUCT_DESCRIPTIONS", "Otomatik bölüm: kalemlerin katalogdaki detay açıklamaları")}
DUZEN = {"bosluk": "Bir satır boşluk bırakır (içerik bölümü metninde ya da Word şablonunda ayrı satıra yazılır)",
         "sayfa_sonu": "Devamı yeni sayfadan / slayttan başlar (ayrı satıra yazılır)"}
KULLANICI_SECIMI = ("sectionType", "autoContent", "removable", "defaultText")
# Akış şablonu (liste 15c): {{icerik}} içerik slaytını işaretler; içerik bölümleri dosyadan değil CRM'den tanımlanır
AKIS = "icerik"
CRM_BOLUMU = "CRM (içerik bölümü)"   # sourceRef: dosya yeniden okunduğunda bu bölümlere dokunulmaz
CRM_SIRA = 100                      # içerik bölümlerinin sırası 101'den başlar (dosya bölümlerinden ayrı)


def crm_bolumu_mu(b):
    return (b.get("sourceRef") or "") == CRM_BOLUMU


def _simdi():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def dosya_indir(url):
    """Twenty'nin verdiği imzalı dosya adresi dış adresle gelir; motor Twenty'ye iç ağdan gider (yol ve imza aynı)."""
    p = urllib.parse.urlsplit(url)
    ic = API + p.path + (("?" + p.query) if p.query else "")
    with urllib.request.urlopen(urllib.request.Request(ic), timeout=60) as f:
        return f.read()


def belge_oku(veri):
    r = urllib.request.Request(BELGE_URL + "/oku", data=veri, method="POST",
                               headers={"Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(r, timeout=120) as f:
            return json.loads(f.read())
    except urllib.error.HTTPError as e:
        if e.code == 422:
            raise ValueError(json.loads(e.read()).get("hata") or "Dosya okunamadı")
        raise


def bolum_turu(yer_tutucular):
    """Yer tutuculardan önerilen tür: otomatik işaret → AUTO; CRM sözlüğünde olmayan → FILL; yoksa FIXED."""
    if AKIS in yer_tutucular:
        return "FIXED", None   # içerik slaytı: içerik CRM bölümlerinden gelir
    for y in yer_tutucular:
        if y in OTOMATIK:
            return "AUTO", OTOMATIK[y][0]
    if any(y not in CRM_ALANLARI and y not in OTOMATIK and y not in DUZEN for y in yer_tutucular):
        return "FILL", None
    return "FIXED", None


def yer_tutucu_listesi(sonuc=None):
    """Dosyadaki yer tutucular (nerede kullanıldığıyla) + sözlükte olup dosyada kullanılmayanlar (bolumler boş): şirket
    dosyasını hazırlarken kullanabileceği adları ekranda görür."""
    sonuc = sonuc or {}
    nerede = {}
    for y in sonuc.get("genel_yer_tutucular") or []:
        nerede.setdefault(y, []).append("üst / alt bilgi")
    for b in sonuc.get("bolumler") or []:
        for y in b["yer_tutucular"]:
            nerede.setdefault(y, []).append(b["ad"])
    out = []
    for y, yerler in nerede.items():
        if y in CRM_ALANLARI:
            tur, aciklama = "crm", CRM_ALANLARI[y]
        elif y in OTOMATIK:
            tur, aciklama = "otomatik", OTOMATIK[y][1]
        elif y in DUZEN:
            tur, aciklama = "duzen", DUZEN[y]
        elif y == AKIS:
            tur, aciklama = "akis", "İçerik alanı: CRM'de tanımlanan içerik bölümleri buraya yazılır, slayt gerektikçe çoğaltılır"
        else:
            tur, aciklama = "doldurulacak", "Tanınmayan yer tutucu: teklifte satışçı doldurur"
        out.append({"ad": y, "tur": tur, "aciklama": aciklama, "bolumler": yerler})
    for y, aciklama in CRM_ALANLARI.items():
        if y not in nerede:
            out.append({"ad": y, "tur": "crm", "aciklama": aciklama, "bolumler": []})
    for y, aciklama in DUZEN.items():
        if y not in nerede:
            out.append({"ad": y, "tur": "duzen", "aciklama": aciklama, "bolumler": []})
    for y, (_, aciklama) in OTOMATIK.items():
        if y not in nerede:
            out.append({"ad": y, "tur": "otomatik", "aciklama": aciklama, "bolumler": []})
    if AKIS not in nerede:
        out.append({"ad": AKIS, "tur": "akis", "bolumler": [],
                    "aciklama": "PowerPoint içerik slaytı işareti: bu kutunun alanına CRM'deki içerik bölümleri yazılır, slayt çoğaltılır"})
    return out


def sablon_isle(anahtar):
    sid = anahtar.split(":", 1)[1]
    s = (api("GET", f"/rest/quoteTemplates/{sid}") or {}).get("quoteTemplate")
    if not s:
        return
    yama = {}
    dosyalar = s.get("templateFile") or []
    dosya = dosyalar[0] if dosyalar else None
    if dosya and dosya.get("fileId") != s.get("readFileId"):
        try:
            sonuc = belge_oku(dosya_indir(dosya["url"]))
        except ValueError as e:
            api("PATCH", f"/rest/quoteTemplates/{sid}", {"readFileId": dosya["fileId"], "readAt": _simdi(),
                                                          "readWarnings": f"Okunamadı: {e}", "status": "DRAFT"})
            log(f"şablon okunamadı: {s.get('name')}: {e}")
            return
        bolumleri_esitle(sid, sonuc)
        uyarilar = list(sonuc.get("uyarilar") or [])
        if len(dosyalar) > 1:
            uyarilar.append(f"Şablon Dosyası alanında {len(dosyalar)} dosya var; yalnız ilki ({dosya.get('label')}) kullanılır.")
        yama.update({"readFileId": dosya["fileId"], "readAt": _simdi(), "format": sonuc["bicim"],
                     "placeholders": yer_tutucu_listesi(sonuc), "readWarnings": " ".join(uyarilar) or None})
        log(f"şablon okundu: {s.get('name')} ({sonuc['bicim']}, {len(sonuc['bolumler'])} bölüm)")
    elif not dosya and s.get("readFileId"):
        for b in liste("templateSections", filtre=f"quoteTemplateId[eq]:{sid}"):
            if not crm_bolumu_mu(b):
                api("DELETE", f"/rest/templateSections/{b['id']}")
        yama.update({"readFileId": None, "readAt": None, "format": None, "placeholders": yer_tutucu_listesi(),
                     "readWarnings": "Dosya kaldırıldı."})
    elif not dosya and not s.get("placeholders"):
        yama["placeholders"] = yer_tutucu_listesi()   # yeni şablon: kullanılabilir yer tutucular baştan görünsün
    okunmus = bool(dosya) and (yama.get("readFileId") or s.get("readFileId")) == dosya.get("fileId") \
        and not (yama.get("readWarnings") or s.get("readWarnings") or "").startswith("Okunamadı")
    if not s.get("status"):
        yama["status"] = "DRAFT"
    if s.get("status") == "ACTIVE" and not okunmus:
        yama["status"] = "DRAFT"
        yama["readWarnings"] = " ".join(x for x in ("Aktif olması için önce şablon dosyası yüklenip okunmalı.",
                                                     yama.get("readWarnings")) if x)
    if s.get("isDefault"):
        for d in liste("quoteTemplates", filtre="isDefault[eq]:true"):
            if d["id"] != sid and (d.get("updatedAt") or "") <= (s.get("updatedAt") or ""):
                api("PATCH", f"/rest/quoteTemplates/{d['id']}", {"isDefault": False})   # varsayılan tek
    yama = {a: v for a, v in yama.items() if s.get(a) != v}
    if yama:
        api("PATCH", f"/rest/quoteTemplates/{sid}", yama)


def bolumleri_esitle(sid, sonuc):
    """Aynı adlı (aynı addan kaçıncı) bölümde kullanıcı seçimi korunur; yeni bölüme önerilen tür; dosyada olmayan silinir."""
    mevcut = {}
    for b in sorted(liste("templateSections", filtre=f"quoteTemplateId[eq]:{sid}"), key=lambda x: x.get("sortOrder") or 0):
        if not crm_bolumu_mu(b):   # CRM'de tanımlı içerik bölümleri dosyadan bağımsızdır
            mevcut.setdefault(b.get("name"), []).append(b)
    for b in sonuc["bolumler"]:
        veri = {"name": b["ad"], "sortOrder": b["sira"], "sourceRef": b["kaynak"], "textPreview": b["onizleme"] or None,
                "placeholders": b["yer_tutucular"]}
        eski = mevcut[b["ad"]].pop(0) if mevcut.get(b["ad"]) else None
        if eski:
            fark = {a: v for a, v in veri.items() if eski.get(a) != v}
            if fark:
                api("PATCH", f"/rest/templateSections/{eski['id']}", fark)
        else:
            tur, oto = bolum_turu(b["yer_tutucular"])
            api("POST", "/rest/templateSections", {**veri, "quoteTemplateId": sid, "sectionType": tur, "autoContent": oto,
                                                   "removable": not (b["sira"] == 1 or oto == "LINE_TABLE"
                                                                     or AKIS in b["yer_tutucular"])})
    for kalanlar in mevcut.values():   # dosyada artık olmayan bölümler
        for b in kalanlar:
            api("DELETE", f"/rest/templateSections/{b['id']}")


def varsayilan_sablon():
    aktif = [s for s in liste("quoteTemplates", filtre="status[eq]:ACTIVE")]
    return next((s["id"] for s in aktif if s.get("isDefault")), aktif[0]["id"] if len(aktif) == 1 else None)
