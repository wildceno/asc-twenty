"""Zamanlayıcı: TCMB'ye günde en fazla bir kez gidilir (o günün kuru kayıtlıysa hiç gidilmez); kur saatinden (16:05)
önce, hiç kur yoksa bir kez son yayımlanan kur alınır. Yarım saatte bir paketlerin periyodik işleri kuyruğa eklenir."""
import datetime as dt
import time
import traceback

from ascendia_motor.cekirdek import paketler
from ascendia_motor.cekirdek.ayar import KUR_SAATI, TR
from ascendia_motor.cekirdek.gunluk import SAGLIK, log
from ascendia_motor.cekirdek.kur import bugunun_kuru_var, tcmb_esitle
from ascendia_motor.cekirdek.kuyruk import ekle
from ascendia_motor.cekirdek.twenty import liste


def zamanlayici():
    ilk, son_cekim = True, None   # hafta sonu/tatilde TCMB yeni kur yayımlamaz: yine günde bir deneme
    while True:
        simdi = dt.datetime.now(TR)
        SAGLIK["zamanlayici_son"] = time.time()
        try:
            hic_yok = not liste("exchangeRates", limit=1)
            if hic_yok or (simdi.strftime("%H:%M") >= KUR_SAATI and son_cekim != simdi.date()
                           and not bugunun_kuru_var()):
                tcmb_esitle()
                son_cekim = simdi.date()
                ekle("hepsi")
            elif ilk:
                ekle("hepsi")   # açılışta kaçan değişiklikler için bir kez
            ilk = False         # yalnız başarıda: açılışta API/DNS hazır değilse telafi kaybolmasın
            for anahtar in paketler.periyodik():
                ekle(anahtar)   # ör. takip: temassız gün zamanla artar
        except Exception:
            log("HATA TCMB", traceback.format_exc(limit=2))
            time.sleep(60 if ilk else 1800)   # açılış hatasında kısa aralıkla yeniden dene
            continue
        time.sleep(1800)
