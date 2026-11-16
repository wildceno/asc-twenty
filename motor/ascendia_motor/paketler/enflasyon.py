"""Enflasyon öngörüsü (liste 14c; plan: kararlar/2026-11-13-teklif-modulu-plan.md). TEKLIF paketinin parçası.

Kaynaklar (13 Kas 2026'da erişimleri denendi):
- TRY: TCMB Piyasa Katılımcıları Anketi, EVDS (evds3), uygun ortalama serileri; ücretsiz EVDS anahtarı gerekir.
    TP.PKAUO.S01.E.U 12 ay sonrasının yıllık TÜFE beklentisi · .F.U 24 ay sonrası · .G.U 5 yıl sonrası
- USD: Fed FOMC Summary of Economic Projections, PCE enflasyonu medyanı (FRED resmî API: PCECTPIMD takvim yılları,
    PCECTPIMDLR uzun dönem; ücretsiz FRED API anahtarı gerekir. Anahtarsız grafik CSV adresi otomatik istemcileri
    zaman aşımına düşürüyor — 13 Kas'ta denendi — bu yüzden kullanılmaz).
Sonuç Twenty'de "Enflasyon Öngörüsü" kayıtlarına (para birimi × sözleşme yılı 1..5) yazılır. "Elle sabitlendi"
işaretli kayıtlara motor dokunmaz; tabloda olmayan para birimi (EUR, GBP…) elle eklenebilir.
Günde bir kez denenir; başarısızsa yarım saatte bir yeniden denenir ve alarm açılır.
"""
import datetime as dt
import json
import os
import urllib.request

from ascendia_motor.cekirdek.ayar import TR
from ascendia_motor.cekirdek.gunluk import log, oku
from ascendia_motor.cekirdek.twenty import api, liste
from ascendia_motor.paketler.teklif_hesap import enflasyon_sozlugu, tl_yillari, usd_yillari

EVDS_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
EVDS_KEY_FILE = os.environ.get("EVDS_KEY_FILE", "/run/sirlar/evds_key")
EVDS_SERI = {"12ay": "TP.PKAUO.S01.E.U", "24ay": "TP.PKAUO.S01.F.U", "5yil": "TP.PKAUO.S01.G.U"}
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_KEY_FILE = os.environ.get("FRED_KEY_FILE", "/run/sirlar/fred_key")
KAYNAK_TRY = "TCMB Piyasa Katılımcıları Anketi (EVDS): 12 ay, 24 ay, 5 yıl TÜFE beklentisi; yıl 3-4 ara değer"
KAYNAK_USD = "Fed FOMC Ekonomik Projeksiyonları, PCE enflasyonu medyanı (FRED PCECTPIMD / PCECTPIMDLR)"

_son_basarili = None   # bu gün başarıyla güncellendiyse tekrar gidilmez
_tablo = None          # Enflasyon Öngörüsü kayıtlarının önbelleği (kayıt değişince boşaltılır)


def _getir(url, baslik=None):
    r = urllib.request.Request(url, headers={"User-Agent": "ascendia-hesap-motoru", **(baslik or {})})
    with urllib.request.urlopen(r, timeout=30) as f:
        return f.read().decode("utf-8")


def tcmb_beklentileri(bugun):
    """Son anketin (12 ay, 24 ay, 5 yıl) değerleri ve anket ayı (YYYY-AA-01)."""
    anahtar = oku(EVDS_KEY_FILE) if os.path.exists(EVDS_KEY_FILE) else ""
    if not anahtar:
        raise RuntimeError("EVDS anahtarı yok (~/twenty/.evds-anahtari)")
    bas = (bugun - dt.timedelta(days=150)).strftime("%d-%m-%Y")
    url = f"{EVDS_URL}/series={'-'.join(EVDS_SERI.values())}&startDate={bas}&endDate={bugun.strftime('%d-%m-%Y')}&type=json"
    veri = json.loads(_getir(url, {"key": anahtar}))
    for satir in reversed(veri.get("items") or []):
        d = {ad: satir.get(seri.replace(".", "_")) for ad, seri in EVDS_SERI.items()}
        if all(v not in (None, "") for v in d.values()):
            yil, ay = satir["Tarih"].split("-")
            return {ad: float(v) for ad, v in d.items()}, f"{int(yil):04d}-{int(ay):02d}-01"
    raise RuntimeError("EVDS: son 5 ayda tam anket verisi yok")


def fed_projeksiyonu():
    """Takvim yılı → PCE medyanı, uzun dönem değeri ve projeksiyonun yayın tarihi."""
    anahtar = oku(FRED_KEY_FILE) if os.path.exists(FRED_KEY_FILE) else ""
    if not anahtar:
        raise RuntimeError("FRED API anahtarı yok (~/twenty/.fred-anahtari)")

    def seri_oku(seri):
        # Gerçek zaman varsayılanı bugün: projeksiyonun en güncel yayını gelir; gözlemler tarih sırasıyla döner
        v = json.loads(_getir(f"{FRED_URL}?series_id={seri}&api_key={anahtar}&file_type=json"))
        return [(o["date"], float(o["value"])) for o in v.get("observations") or [] if o.get("value") not in (None, "", ".")]
    yillar = {int(t[:4]): v for t, v in seri_oku("PCECTPIMD")}
    uzun = seri_oku("PCECTPIMDLR")
    if not yillar or not uzun:
        raise RuntimeError("FRED: projeksiyon verisi boş")
    return yillar, uzun[-1][1], uzun[-1][0]


def tablo():
    """{para birimi: [yıl1..]} ve kaynak özeti (teklife yazılır)."""
    global _tablo
    if _tablo is None:
        kayitlar = liste("inflationForecasts")
        kaynak = {}
        for r in kayitlar:
            pb = (r.get("forecastCurrency") or "").upper()
            if pb and pb not in kaynak:
                kaynak[pb] = ("elle: " if r.get("manual") else "") + f"{r.get('source') or '—'} · {(r.get('sourceDate') or '')[:10]}"
        _tablo = (enflasyon_sozlugu(kayitlar), kaynak)
    return _tablo


def tablo_degisti(anahtar=None):
    global _tablo
    _tablo = None


def _farkli(alan, eski, yeni):
    if alan == "ratePercent":
        return eski is None or abs(float(eski) - yeni) > 1e-9
    if alan == "sourceDate":
        return (eski or "")[:10] != yeni
    return eski != yeni


def guncelle(anahtar=None):
    """Kaynaklardan çek, Enflasyon Öngörüsü kayıtlarını eşitle (günde bir başarılı tur)."""
    global _son_basarili
    from ascendia_motor.paketler.saglik import alarm_ac, alarm_kapat   # döngüsel içe aktarma olmasın
    bugun = dt.datetime.now(TR).date()
    if _son_basarili == bugun:
        return
    mevcut = {}
    for r in liste("inflationForecasts"):
        if r.get("forecastCurrency") and r.get("contractYear"):
            mevcut[(r["forecastCurrency"].upper(), int(r["contractYear"]))] = r
    hatalar = []
    for pb in ("TRY", "USD"):
        try:
            if pb == "TRY":
                b, tarih = tcmb_beklentileri(bugun)
                oranlar, kaynak = tl_yillari(b["12ay"], b["24ay"], b["5yil"]), KAYNAK_TRY
            else:
                yillar, uzun, tarih = fed_projeksiyonu()
                oranlar, kaynak = usd_yillari(yillar, uzun, bugun), KAYNAK_USD
        except Exception as e:   # noqa: BLE001 — kaynak hatası alarm olur, motor durmaz
            hatalar.append(f"{pb}: {str(e)[:200]}")
            continue
        for i, oran in enumerate(oranlar, 1):
            veri = {"name": f"{pb} · {i}. yıl", "forecastCurrency": pb, "contractYear": i, "ratePercent": round(oran, 2),
                    "source": kaynak, "sourceDate": tarih}
            r = mevcut.get((pb, i))
            if r is None:
                api("POST", "/rest/inflationForecasts", {**veri, "manual": False})
            elif not r.get("manual"):
                fark = {a: v for a, v in veri.items() if _farkli(a, r.get(a), v)}
                if fark:
                    api("PATCH", f"/rest/inflationForecasts/{r['id']}", fark)
                    log(f"enflasyon öngörüsü güncellendi: {pb} {i}. yıl %{veri['ratePercent']} ({tarih})")
    tablo_degisti()
    if hatalar:
        log("HATA enflasyon öngörüsü alınamadı:", "; ".join(hatalar))
        alarm_ac("ENFLASYON_ALINAMADI", "ENFLASYON", "UYARI", "Enflasyon öngörüsü alınamadı", "; ".join(hatalar))
    else:
        _son_basarili = bugun
        alarm_kapat("ENFLASYON_ALINAMADI", "ENFLASYON")
