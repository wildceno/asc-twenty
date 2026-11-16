"""Kurları ve CRM Ayarı'nı yükler (raporlama para birimi, mali yıl, hedef dönemi, eşik, açık paketler)."""
from ascendia_motor.cekirdek.donemler import donemleri_yukle
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.twenty import liste


def kurlari_yukle():
    k = {}
    for r in liste("exchangeRates", sira="rateDate[DescNullsLast]"):
        kod = r.get("foreignCurrency")
        if kod and kod not in k and r.get("rateTry"):
            k[kod] = (float(r["rateTry"]), r.get("rateDate"))
    Durum.kurlar = k
    ayar = liste("crmSettings", limit=5)
    Durum.raporlama = ayar[0].get("reportingCurrency") if ayar else None
    ay = (ayar[0].get("fiscalYearStartMonth") if ayar else None) or "M01"
    Durum.mali_ay = int(ay[1:])
    Durum.esik = int((ayar[0].get("historyThreshold") if ayar else None) or 20)
    Durum.hedef_tipi = (ayar[0].get("targetPeriodType") if ayar else None) or "QUARTER"
    Durum.teklif_hatirlatma_gun = int((ayar[0].get("quoteReminderDays") if ayar else None) or 3)
    kdv = ayar[0].get("defaultVatRate") if ayar else None
    Durum.varsayilan_kdv = float(kdv) if kdv is not None else None
    Durum.rakip_gun = int((ayar[0].get("competitorRenewalDays") if ayar else None) or 90)
    Durum.acik_paketler = set((ayar[0].get("activeModules") if ayar else None) or []) or None
    donemleri_yukle()
