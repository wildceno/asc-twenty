"""Paket kaydı (7c, kullanıcı kararı 13 Kas 2026: tek servis, ayrı paketler, müşteri bazında aç/kapat).

Her paket modülü şunları bildirir:
  AD           : CRM Ayarı → Açık Paketler'deki değer (ör. "TAKIP")
  OLAYLAR      : [(webhook olay öneki, olay → kuyruk işleri)]
  ISLER        : {iş adı: işlev(anahtar)}; anahtar "ad" ya da "ad:kayıt-id"
  SONRAKI      : {iş adı: [ardından kuyruğa eklenecek işler]}
  BIRLESTIRME  : {iş adı: saniye} → bu sürede tek çalıştırma (tam tarama işleri)
  PERIYODIK    : [yarım saatte bir kuyruğa eklenecek işler]
  tumunu_isle(): "hepsi" işinde (kur/ayar/dönem değişince, açılışta, günlük kurdan sonra) çağrılır
Çekirdek (kur, ayar, dönemler, kuyruk, webhook) her zaman açıktır.
"""
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.paketler import eposta, fatura, hedefler, imza, saglik, satis_sureci, takip, teklif

SIRA = [satis_sureci, teklif, imza, fatura, hedefler, eposta, takip, saglik]   # eposta takip'ten önce: temaslar takibi besler   # "hepsi" işinde çalışma sırası
CEKIRDEK_OLAYLARI = ("crmSetting.", "exchangeRate.", "reportingPeriod.")


def acik(ad):
    """CRM Ayarı'nda Açık Paketler boşsa hepsi açık (varsayılan)."""
    return Durum.acik_paketler is None or ad in Durum.acik_paketler


def acik_paketler():
    return [p for p in SIRA if acik(p.AD)]


def olay_isleri(ad, kayit):
    isler = ["hepsi"] if ad.startswith(CEKIRDEK_OLAYLARI) else []
    for p in acik_paketler():
        for onek, cevir in getattr(p, "OLAYLAR", []):
            if ad.startswith(onek):
                isler += cevir(ad, kayit)
    return isler


def is_islevi(anahtar):
    """(paket, işlev) ya da paket kapalıysa / iş bilinmiyorsa None."""
    ad = anahtar.split(":", 1)[0]
    for p in SIRA:
        if ad in getattr(p, "ISLER", {}):
            return (p, p.ISLER[ad]) if acik(p.AD) else None
    return None


def sonraki_isler(anahtar):
    ad = anahtar.split(":", 1)[0]
    return [i for p in SIRA for i in getattr(p, "SONRAKI", {}).get(ad, [])]


def birlestirme(anahtar):
    return next((p.BIRLESTIRME[anahtar] for p in SIRA if anahtar in getattr(p, "BIRLESTIRME", {})), 0)


def periyodik():
    return [i for p in acik_paketler() for i in getattr(p, "PERIYODIK", [])]
