"""Paket HEDEFLER: hedef kalemi gerçekleşmesi, forecast, dönüşüm oranları (manuel / geçmiş)."""
import datetime as dt

from ascendia_motor.cekirdek.ayar import DELIVERY_PHASE, TR
from ascendia_motor.cekirdek.donemler import donem_bul, tarih_tr
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.para import ayni, cevir, cur, para
from ascendia_motor.cekirdek.twenty import api, liste
from ascendia_motor.cekirdek.yukle import kurlari_yukle


METRIK_ALANI = {"GROSS_PROFIT": "grossProfitReporting", "REVENUE": "amountReporting", "ARR": "arrReporting",
                "MRR": "mrrReporting"}


KAZANILAN = DELIVERY_PHASE | {"WON"}


TOTAL_PIPELINE = {"PIPELINE", "UPSIDE", "COMMIT"}   # kullanıcı, 11 Kas


def oranlari_hesapla(tum_firsatlar):
    """Aşama dönüşüm oranları: geçmiş (o aşamaya girip kapanan fırsatların Audit+ oranı) eşiği aştıysa geçmiş,
    yoksa manuel. Döner: {aşama: kullanılan oran %}."""
    kayitlar = liste("forecastRates")
    if not kayitlar:
        return {}
    girdi = {}
    for k in liste("stageChanges"):
        if k.get("opportunityId") and k.get("toStage"):
            girdi.setdefault(k["opportunityId"], set()).add(k["toStage"])
    son = {o["id"]: o["stage"] for o in tum_firsatlar}
    sonuc = {}
    for r in kayitlar:
        asama = r.get("stage")
        kapanan = [i for i, a in girdi.items() if asama in a and son.get(i) in KAZANILAN | {"LOST", "DISQUALIFIED"}]
        kazanilan = [i for i in kapanan if son[i] in KAZANILAN]
        gecmis = round(len(kazanilan) / len(kapanan) * 100, 1) if kapanan else None
        gecmise = gecmis is not None and len(kapanan) >= Durum.esik
        kullanilan = gecmis if gecmise else r.get("manualRate")
        yama = {"historicalRate": gecmis, "closedCount": len(kapanan), "effectiveRate": kullanilan,
                "rateSource": "HISTORY" if gecmise else "MANUAL"}
        yama = {a: v for a, v in yama.items() if not ayni(r.get(a), v)}
        if yama:
            api("PATCH", f"/rest/forecastRates/{r['id']}", yama)
        if asama and kullanilan is not None:
            sonuc[asama] = float(kullanilan)
    return sonuc


def hedefleri_hesapla():
    """Hedef kalemi gerçekleşeni: dönemde Audit/Delivery/Invoice/Won'a geçen (Lost/DSQ hariç) fırsatlar."""
    hedefler = liste("targets")
    if not hedefler:
        return
    if not Durum.kurlar:
        kurlari_yukle()
    donem = {r["id"]: (r["startDate"][:10], r["endDate"][:10]) for r in liste("reportingPeriods")
             if r.get("startDate") and r.get("endDate")}
    tum = liste("opportunities")
    firsatlar = [o for o in tum if o["stage"] in KAZANILAN and o.get("realCloseDate")]
    acik = [o for o in tum if o["stage"] in TOTAL_PIPELINE and o.get("closeDate")]
    oranlar = oranlari_hesapla(tum)
    kalemler = liste("targetLines")
    ekip = liste("teamMembers")
    yoneticisi = {e["memberId"]: e.get("managerId") for e in ekip if e.get("memberId")}
    gorev = {e["memberId"]: e.get("jobFunction") for e in ekip if e.get("memberId")}

    def ekibi(yonetici):
        """Yöneticinin kendisi + doğrudan ve dolaylı ekibi."""
        sonuc, sira = {yonetici}, [yonetici]
        while sira:
            y = sira.pop()
            for uye, yon in yoneticisi.items():
                if yon == y and uye not in sonuc:
                    sonuc.add(uye)
                    sira.append(uye)
        return sonuc

    for h in hedefler:
        aralik, rol = donem.get(h.get("periodId")), h.get("targetRole")
        uye = h.get("memberId")
        if gorev.get(uye) == "SUPPORT":
            log(f"hedef {h.get('name')}: support rolünün hedefi yok, hesaplanmadı")
            continue
        # Kullanıcı (11 Kas): herkes Fırsat Sahibi olduğu fırsatlarla; yönetici bağlı kişilerinkiyle (kendisi hariç)
        kisiler = (ekibi(uye) - {uye}) if rol == "MANAGER" else {uye}
        ilgili = [o for o in firsatlar if aralik and uye and o.get("ownerId") in kisiler
                  and aralik[0] <= o["realCloseDate"][:10] <= aralik[1]]
        beklenen = [o for o in acik if aralik and uye and o.get("ownerId") in kisiler
                    and aralik[0] <= tarih_tr(o["closeDate"]) <= aralik[1]]
        puan, agirlik_top, fpuan = 0.0, 0.0, 0.0
        for k in [x for x in kalemler if x.get("targetId") == h["id"]]:
            alan, hedef_para = METRIK_ALANI.get(k.get("metric")), para(k.get("targetAmount"))
            if not alan:
                continue
            kod = hedef_para[1] if hedef_para else (Durum.raporlama or "USD")
            toplam_ = 0.0
            for o in ilgili:
                p = para(o.get(alan))
                v = cevir(p[0], p[1], kod, Durum.kurlar) if p else None
                toplam_ += v or 0.0
            oran = round(toplam_ / hedef_para[0] * 100, 1) if hedef_para and hedef_para[0] else None
            fc = 0.0
            for o in beklenen:
                p = para(o.get(alan))
                v = cevir(p[0], p[1], kod, Durum.kurlar) if p else None
                fc += (v or 0.0) * oranlar.get(o["stage"], 0.0) / 100
            foran = round((toplam_ + fc) / hedef_para[0] * 100, 1) if hedef_para and hedef_para[0] else None
            guncel = donem_bul(dt.datetime.now(TR).date().isoformat())
            yama = {"actualAmount": cur(toplam_, kod), "attainmentPercent": oran,
                    "forecastAmount": cur(fc, kod), "forecastAttainmentPercent": foran,
                    "inCurrentPeriod": bool(guncel and h.get("periodId") == guncel[1])}
            yama = {a: v for a, v in yama.items() if not ayni(k.get(a), v)}
            if yama:
                api("PATCH", f"/rest/targetLines/{k['id']}", yama)
            if oran is not None:
                w = float(k.get("weightPercent") or 0) or 1.0
                puan, agirlik_top, fpuan = puan + w * oran, agirlik_top + w, fpuan + w * (foran or 0.0)
        genel = round(puan / agirlik_top, 1) if agirlik_top else None
        fgenel = round(fpuan / agirlik_top, 1) if agirlik_top else None
        hy = {a: v for a, v in {"attainmentPercent": genel, "forecastAttainmentPercent": fgenel}.items()
              if not ayni(h.get(a), v)}
        if hy:
            api("PATCH", f"/rest/targets/{h['id']}", hy)
            log(f"hedef {h.get('name')}: gerçekleşme %{genel}, forecast %{fgenel}")


# ---------------- paket tanımı ----------------
AD = "HEDEFLER"
OLAYLAR = [(("target.", "targetLine.", "teamMember.", "forecastRate."), lambda ad, kayit: ["hedefler"])]
ISLER = {"hedefler": lambda anahtar: hedefleri_hesapla()}
BIRLESTIRME = {"hedefler": 30}   # tam tarama: olay yağmurunda 30 sn'de bir


def tumunu_isle():
    hedefleri_hesapla()
