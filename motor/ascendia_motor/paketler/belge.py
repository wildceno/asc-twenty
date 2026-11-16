"""Teklif belgesi üretimi (liste 15b; TEKLIF paketinin parçası). Plan: kararlar/2026-11-13-teklif-modulu-plan.md.

Belge sekmesi teklife "Belge İsteği" yazar → motor şablonu indirir, değerleri toplar (CRM alanları, satışçının
doldurdukları, kalem tablosu, ürün açıklamaları), belge servisine gönderir, sonucu teklifin Belgeler alanına yükler,
isteği temizler ve durumu yazar. Dosya alanına yükleme Twenty'nin kendi akışıyla: createFileUpload → PUT → completeFileUpload.
"""
import base64
import datetime as dt
import json
import re
import urllib.error
import urllib.request

from ascendia_motor.cekirdek.ayar import API, TR
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.twenty import api, gql, liste
from ascendia_motor.paketler.sablon import (AKIS, BELGE_URL, CRM_ALANLARI, OTOMATIK, crm_bolumu_mu, dosya_indir,
                                            varsayilan_sablon)
from ascendia_motor.paketler.teklif_hesap import para, sayilan_kalemler

ODEME = {"ONE_TIME": "Tek seferlik", "MONTHLY": "Aylık", "YEARLY": "Yıllık"}
BASLIKLAR = ["Kalem", "Miktar", "Birim fiyat", "İndirim", "Ödeme", "Tutar"]
_alan_id = {}


def md_metin(md):
    """Twenty biçimli metninin markdown'u → belgeye yazılacak düz metin (saf): satır sonları korunur, kalın / italik
    işaretleri ve başlık #'ları kalkar, madde işaretleri • olur, üç ve daha fazla boş satır ikiye iner."""
    satirlar = []
    for satir in (md or "").replace("\r\n", "\n").split("\n"):
        t = re.sub(r"^\s{0,3}#{1,6}\s+", "", satir)
        t = re.sub(r"^(\s*)[-*+]\s+", lambda m: m.group(1) + "• ", t)
        t = re.sub(r"(\*\*|__)(.+?)\1", r"\2", t)
        t = re.sub(r"(?<![\w*])[*_](?!\s)(.+?)(?<!\s)[*_](?![\w*])", r"\1", t)
        t = t.replace("\\", "")
        satirlar.append(t.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(satirlar)).strip()


def tr_sayi(n, ondalik=2):
    """1234.5 → '1.234,50' (Türkçe biçim)."""
    s = f"{n:,.{ondalik}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def tr_tarih(iso):
    return dt.date.fromisoformat(iso[:10]).strftime("%d.%m.%Y") if iso else ""


def miktar_metni(n):
    return tr_sayi(n, 0) if float(n).is_integer() else tr_sayi(n, 2)


def kalem_tablosu(kalemler, teklif_ayi, kirilim):
    """Kalem tablosu (saf): tüm kalemler (seçenek grubundakiler işaretli), para birimine göre toplamlar (sayılanlar)."""
    sayilan = {k.get("id") for k in sayilan_kalemler(kalemler)}
    satirlar = []
    for k in sorted(kalemler, key=lambda x: ((x.get("section") or ""), x.get("sortOrder") or 0)):
        fiyat, fpb = para(k.get("unitPrice"))
        gelir, gpb = para(k.get("lineRevenue"))
        odeme = k.get("billing") or "ONE_TIME"
        ay = k.get("months") or teklif_ayi
        odeme_metni = ODEME[odeme] + (f" × {ay} ay" if odeme == "MONTHLY" and ay else "") + \
            (f" × {tr_sayi(ay / 12, 1).rstrip('0').rstrip(',')} yıl" if odeme == "YEARLY" and ay else "")
        ad = k.get("name") or ""
        if k.get("optionGroup"):
            ad += f" (seçenek: {k['optionGroup']}{'' if k.get('id') in sayilan else ', alternatif'})"
        satirlar.append([ad, miktar_metni(k.get("quantity") or 0), f"{tr_sayi(fiyat)} {fpb or ''}".strip(),
                         f"%{tr_sayi(k['discountPercent'], 0)}" if k.get("discountPercent") else "",
                         odeme_metni, f"{tr_sayi(gelir)} {gpb or ''}".strip()])
    # Yalnız gelir olan para birimleri (kırılımda yalnız maliyeti olan para birimi de bulunabilir: ör. TRY maliyetli kalem)
    toplamlar = [[f"Toplam ({pb})", "", "", "", "", f"{tr_sayi(v.get('gelir') or 0)} {pb}"]
                 for pb, v in (kirilim or {}).items() if v.get("gelir")]
    return {"basliklar": BASLIKLAR, "satirlar": satirlar, "toplamlar": toplamlar}


def doldurulacak_varsayilanlari(bolumler):
    """Teklifte doldurulan bölümün varsayılan metni, o bölümdeki tek tanınmayan yer tutucunun başlangıç değeridir."""
    out = {}
    for b in bolumler:
        if b.get("sectionType") != "FILL" or not b.get("defaultText"):
            continue
        bilinmeyen = [y for y in (b.get("placeholders") or []) if y not in CRM_ALANLARI and y not in OTOMATIK]
        if len(bilinmeyen) == 1:
            out.setdefault(bilinmeyen[0], b["defaultText"])
    return out


YER_TUTUCU = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def akis_bloklari(icerik_bolumleri, haric, doldurulan, degerler, tablo, aciklamalar):
    """Akış şablonunun içerik bölümleri (CRM'de tanımlı, sıralı) → belge servisinin blokları (saf).
    Sabit: bölüm metni; teklifte doldurulur: satışçının metni (yoksa varsayılan); otomatik: kalem tablosu / açıklamalar.
    Metindeki {{yer_tutucu}} CRM değeriyle değişir (bilinmeyen boş kalır)."""
    def coz(metin):
        return YER_TUTUCU.sub(lambda m: str(degerler.get(m.group(1).strip(), "")), metin or "")
    out = []
    for b in sorted(icerik_bolumleri, key=lambda x: x.get("sortOrder") or 0):
        if b.get("removable") and int(b.get("sortOrder") or 0) in haric:
            continue
        tur = b.get("sectionType") or "FIXED"
        if tur == "AUTO" and b.get("autoContent") == "LINE_TABLE":
            out.append({"baslik": b.get("name"), "tur": "tablo", "tablo": tablo})
        elif tur == "AUTO" and b.get("autoContent") == "PRODUCT_DESCRIPTIONS":
            if aciklamalar:
                out.append({"baslik": b.get("name"), "tur": "aciklamalar", "ogeler": aciklamalar})
        else:
            metin = doldurulan.get(f"bolum:{b['id']}") if tur == "FILL" else None
            metin = metin if metin not in (None, "") else b.get("defaultText")
            out.append({"baslik": b.get("name"), "tur": "metin", "metin": coz(metin)})
    return out


def _alan(nesne, ad):
    if (nesne, ad) not in _alan_id:
        for e in gql("{ objects(paging:{first:200}) { edges { node { nameSingular fields(paging:{first:500}) "
                     "{ edges { node { id name } } } } } } }")["objects"]["edges"]:
            for f in e["node"]["fields"]["edges"]:
                _alan_id[(e["node"]["nameSingular"], f["node"]["name"])] = f["node"]["id"]
    return _alan_id[(nesne, ad)]


def dosya_yukle(nesne, alan, ad, icerik):
    t = gql("mutation($n:String!,$s:Float!,$a:String!){ createFileUpload(filename:$n,size:$s,fileFolder:FilesField,"
            "fieldMetadataId:$a){ fileId uploadUrl contentType } }", {"n": ad, "s": len(icerik), "a": _alan(nesne, alan)})["createFileUpload"]
    url = API + "/" + t["uploadUrl"].split("/", 3)[3]   # dış adres → iç ağ (yol ve imza aynı)
    urllib.request.urlopen(urllib.request.Request(url, method="PUT", data=icerik, headers={"Content-Type": t["contentType"]}),
                           timeout=120)
    gql("mutation($f:String!){ completeFileUpload(fileId:$f){ id } }", {"f": t["fileId"]})
    return {"fileId": t["fileId"], "label": ad}


def _dosya_adi(ad):
    return re.sub(r'[\\/:*?"<>|]+', "-", ad or "Teklif").strip()[:120]


def belge_isle(anahtar):
    tid = anahtar.split(":", 1)[1]
    t = (api("GET", f"/rest/quotes/{tid}") or {}).get("quote")
    if not t or not t.get("documentRequest"):
        return
    istek = t["documentRequest"]

    def bitir(durum, ek=None):
        api("PATCH", f"/rest/quotes/{tid}", {"documentRequest": None, "documentStatus": durum, **(ek or {})})
        log(f"{t.get('name')}: belge — {durum}")

    if not t.get("quoteTemplateId"):   # şablon aktif olmadan açılmış teklif: varsayılan aktif şablon kullanılır
        v = varsayilan_sablon()
        if not v:
            return bitir("Üretilemedi: teklifte şablon seçili değil ve varsayılan aktif şablon yok.")
        api("PATCH", f"/rest/quotes/{tid}", {"quoteTemplateId": v})
        t["quoteTemplateId"] = v
    s = (api("GET", f"/rest/quoteTemplates/{t['quoteTemplateId']}") or {}).get("quoteTemplate") or {}
    dosya = (s.get("templateFile") or [None])[0]
    if not dosya or dosya.get("fileId") != s.get("readFileId"):
        return bitir("Üretilemedi: şablon dosyası okunmamış (şablonu yeniden yükleyin).")
    tum = sorted(liste("templateSections", filtre=f"quoteTemplateId[eq]:{s['id']}"), key=lambda b: b.get("sortOrder") or 0)
    bolumler = [b for b in tum if not crm_bolumu_mu(b)]          # dosyadan okunanlar (sıra okumadakiyle aynı)
    icerik_bolumleri = [b for b in tum if crm_bolumu_mu(b)]      # akış şablonunda CRM'de tanımlananlar
    secim = {int(x.get("sira") or 0): x for x in (t.get("documentSections") or []) if isinstance(x, dict)}
    haric = [b["sortOrder"] for b in tum if b.get("removable") and secim.get(int(b["sortOrder"]), {}).get("dahil") is False]

    firsat = (api("GET", f"/rest/opportunities/{t['opportunityId']}") or {}).get("opportunity") or {} if t.get("opportunityId") else {}
    sirket = (api("GET", f"/rest/companies/{firsat['companyId']}") or {}).get("company") or {} if firsat.get("companyId") else {}
    sahip = (api("GET", f"/rest/workspaceMembers/{firsat['ownerId']}") or {}).get("workspaceMember") or {} if firsat.get("ownerId") else {}
    kirilim = t.get("currencyBreakdown") or {}
    degerler = {
        "musteri_adi": sirket.get("name") or "", "firsat_adi": firsat.get("name") or "", "teklif_adi": t.get("name") or "",
        "teklif_no": str(t.get("version") or ""), "teklif_tarihi": dt.datetime.now(TR).strftime("%d.%m.%Y"),
        "gecerlilik": tr_tarih(t.get("validUntil")), "sure_ay": str(t.get("contractMonths") or ""),
        "hazirlayan": " ".join(x for x in ((sahip.get("name") or {}).get("firstName"), (sahip.get("name") or {}).get("lastName")) if x),
        "imza": "/imza/",   # DocuSign çapası (liste 20); belge servisi beyaz yazar, imza alanı buraya konur
        "toplam": " + ".join(f"{tr_sayi(v.get('gelir') or 0)} {pb}" for pb, v in kirilim.items() if v.get("gelir")),
    }
    doldur = {**doldurulacak_varsayilanlari(bolumler), **{k: v for k, v in (t.get("fillValues") or {}).items() if v not in (None, "")}}
    degerler.update(doldur)

    kalemler = liste("quoteLines", filtre=f"quoteId[eq]:{tid}")
    aciklamalar = []
    for k in sorted(sayilan_kalemler(kalemler), key=lambda x: ((x.get("section") or ""), x.get("sortOrder") or 0)):
        metin = k.get("description")
        if k.get("catalogItemId"):
            kat = (api("GET", f"/rest/catalogItems/{k['catalogItemId']}") or {}).get("catalogItem") or {}
            metin = md_metin((kat.get("details") or {}).get("markdown")) or kat.get("shortDescription") or metin
        if metin:
            aciklamalar.append({"ad": k.get("name") or "", "aciklama": metin})

    tablo = kalem_tablosu(kalemler, t.get("contractMonths"), kirilim)
    akis = []
    if any(p.get("ad") == AKIS and p.get("bolumler") for p in (s.get("placeholders") or [])):
        akis = akis_bloklari(icerik_bolumleri, set(haric), t.get("fillValues") or {}, degerler, tablo, aciklamalar)
    girdi = {"sablon": base64.b64encode(dosya_indir(dosya["url"])).decode(), "degerler": degerler,
             "haric": [h for h in haric if h <= len(bolumler)], "bolum_sayisi": len(bolumler), "kalem_tablosu": tablo,
             "urun_aciklamalari": aciklamalar, "akis": akis, "pdf": istek in ("PDF", "BOTH")}
    try:
        r = urllib.request.Request(BELGE_URL + "/uret", data=json.dumps(girdi).encode(), method="POST",
                                   headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=300) as f:
            sonuc = json.loads(f.read())
    except urllib.error.HTTPError as e:
        hata = json.loads(e.read() or b"{}").get("hata") if e.code == 422 else f"belge servisi {e.code}"
        return bitir(f"Üretilemedi: {hata}")
    except Exception as e:   # noqa: BLE001 — servis kapalıysa teklif kilitlenmesin
        log(f"HATA belge servisi: {e}")
        return bitir("Üretilemedi: belge servisine ulaşılamadı (sistem yöneticisine bildirildi).")

    ad = _dosya_adi(t.get("name"))
    dosyalar = []
    if istek in ("NATIVE", "BOTH"):
        dosyalar.append(dosya_yukle("quote", "documents", ad + sonuc["uzanti"], base64.b64decode(sonuc["belge"])))
    if sonuc.get("pdf"):
        dosyalar.append(dosya_yukle("quote", "documents", ad + ".pdf", base64.b64decode(sonuc["pdf"])))
    zaman = dt.datetime.now(TR)
    durum = f"Üretildi {zaman.strftime('%d.%m.%Y %H:%M')} ({', '.join(d['label'].rsplit('.', 1)[-1] for d in dosyalar)})"
    if sonuc.get("uyarilar"):
        durum += " · " + " ".join(sonuc["uyarilar"])
    bitir(durum, {"documents": dosyalar, "documentAt": zaman.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")})
