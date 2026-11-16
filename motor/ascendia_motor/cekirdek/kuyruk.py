"""İş kuyruğu: tek işçi, aynı iş kuyrukta bir kez (sıralı yazma: aynı fırsata iki iş aynı anda yazmaz).
Tam tarama işleri (ör. takip) BIRLESTIRME süresinde tek çalıştırmaya indirilir (7c: olay yağmurunda API sınırı dolmasın)."""
import datetime as dt
import queue
import threading
import time
import traceback

from ascendia_motor.cekirdek import paketler
from ascendia_motor.cekirdek.ayar import TR
from ascendia_motor.cekirdek.donemler import donem_uret, guncel_donem_isaretle, mali_yil
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.gunluk import SAGLIK, log
from ascendia_motor.cekirdek.yukle import kurlari_yukle

IS = queue.Queue()
BEKLEYEN = set()
_ZAMANLI = set()
_SON = {}


def ekle(anahtar):
    aralik = paketler.birlestirme(anahtar)
    if aralik:
        gecen = time.time() - _SON.get(anahtar, 0)
        if gecen < aralik:
            with Durum.kilit:
                if anahtar in _ZAMANLI or anahtar in BEKLEYEN:
                    return
                _ZAMANLI.add(anahtar)

            def sonra():
                with Durum.kilit:
                    _ZAMANLI.discard(anahtar)
                _kuyruga(anahtar)
            t = threading.Timer(aralik - gecen + 0.5, sonra)
            t.daemon = True
            t.start()
            return
    _kuyruga(anahtar)


def _kuyruga(anahtar):
    with Durum.kilit:
        if anahtar in BEKLEYEN:
            return
        BEKLEYEN.add(anahtar)
    IS.put(anahtar)


def tumunu_isle():
    """Kur, ayar ve dönemler; ardından açık paketlerin toplu işi (eski hepsini_isle)."""
    kurlari_yukle()
    bu_yil = mali_yil(dt.datetime.now(TR).date())
    for fy in (bu_yil - 1, bu_yil, bu_yil + 1):
        donem_uret(fy)
    guncel_donem_isaretle()
    for p in paketler.acik_paketler():
        if hasattr(p, "tumunu_isle"):
            p.tumunu_isle()


def isci():
    while True:
        anahtar = IS.get()
        with Durum.kilit:
            BEKLEYEN.discard(anahtar)
        _SON[anahtar] = time.time()
        SAGLIK["mesgul_basi"], SAGLIK["mesgul_is"] = time.time(), anahtar
        try:
            if anahtar == "hepsi":
                tumunu_isle()
            else:
                hedef = paketler.is_islevi(anahtar)
                if hedef:
                    if not Durum.kurlar:
                        kurlari_yukle()
                    hedef[1](anahtar)
                    for sonraki in paketler.sonraki_isler(anahtar):
                        ekle(sonraki)
        except Exception:
            log("HATA", anahtar, traceback.format_exc(limit=3))
        finally:
            SAGLIK["mesgul_basi"] = SAGLIK["mesgul_is"] = None
