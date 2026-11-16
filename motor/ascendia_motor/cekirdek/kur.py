"""TCMB döviz alış kurları (USD, EUR, GBP)."""
import datetime as dt
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ascendia_motor.cekirdek.ayar import TCMB_URL, TR
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.twenty import api, liste


def tcmb_esitle():
    opsiyon = {"USD", "EUR", "GBP"}
    kok = ET.fromstring(urllib.request.urlopen(TCMB_URL, timeout=30).read())
    tarih = dt.datetime.strptime(kok.attrib["Tarih"], "%d.%m.%Y").date().isoformat()
    for c in kok.findall("Currency"):
        kod = c.attrib.get("Kod")
        if kod not in opsiyon:
            continue
        birim, alis = float(c.findtext("Unit") or 1), c.findtext("ForexBuying")
        if not alis:
            continue
        if liste("exchangeRates", filtre=f"and(rateDate[eq]:{tarih},foreignCurrency[eq]:{kod})", limit=1):
            continue
        api("POST", "/rest/exchangeRates", {"name": f"{tarih} {kod}", "rateDate": tarih, "foreignCurrency": kod,
                                            "rateTry": round(float(alis) / birim, 4)})
        log(f"TCMB {tarih} {kod} döviz alış {float(alis) / birim:.4f}")
    return tarih


def bugunun_kuru_var():
    bugun = dt.datetime.now(TR).date().isoformat()
    return bool(liste("exchangeRates", filtre=f"rateDate[eq]:{bugun}", limit=1))
