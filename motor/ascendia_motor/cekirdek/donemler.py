"""Raporlama dönemleri: üretim ("2026 Yılı", "Q4 2026", "Kasım 2026"), eşleme, içinde bulunulan dönem."""
import datetime as dt

from ascendia_motor.cekirdek.ayar import TR
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.twenty import api, liste


def donemleri_yukle():
    tum = [(r.get("periodType"), r["startDate"][:10], r["endDate"][:10], r["name"], r["id"], r.get("isCurrent"))
           for r in liste("reportingPeriods") if r.get("startDate") and r.get("endDate")]
    Durum.donemler = sorted(tum, key=lambda d: (d[1], d[0]))
    Durum.ceyrekler = sorted((b, e, ad) for t, b, e, ad, _, _ in tum if t == "QUARTER")


def donem_bul(gun_iso, tur=None):
    """Tarihin düştüğü (hedef dönemi türündeki) dönem: (ad, id) ya da None."""
    tur = tur or Durum.hedef_tipi
    for t, b, e, ad, did, _ in Durum.donemler:
        if t == tur and b <= gun_iso <= e:
            return ad, did
    return None


def guncel_donem_isaretle():
    """İçinde bulunulan dönem (her tür için) isCurrent = True."""
    bugun = dt.datetime.now(TR).date().isoformat()
    for t, b, e, ad, did, simdi in Durum.donemler:
        olmali = b <= bugun <= e
        if bool(simdi) != olmali:
            api("PATCH", f"/rest/reportingPeriods/{did}", {"isCurrent": olmali})
    donemleri_yukle()


def mali_yil(tarih):
    return tarih.year if tarih.month >= Durum.mali_ay else tarih.year - 1


def ay_ekle(t, n):
    y, m = divmod(t.month - 1 + n, 12)
    return dt.date(t.year + y, m + 1, 1)


AY_TAM = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
          "Aralık"]


def yil_etiketi(fy):
    """Takvim yılıyla aynıysa "2026", değilse "2026/27"."""
    return f"{fy}" if Durum.mali_ay == 1 else f"{fy}/{(fy + 1) % 100:02d}"


def donem_uret(fy):
    """Mali yıl için yıl + 4 çeyrek + 12 ay. Adlar (kullanıcı, 13 Kas): "2026 Yılı" (mali yıl takvimden farklıysa
    "2026/27 Mali Yılı"), "Q4 2026", "Kasım 2026".
    Var olan dönem ada göre değil tür + mali yıl + sıraya göre tanınır; tarihlerine dokunulmaz (elle düzeltilebilir).
    Eski otomatik adlar ("FY..." ile başlayan) yeni biçime çevrilir; elle verilmiş ad korunur."""
    bas = dt.date(fy, Durum.mali_ay, 1)
    gun = dt.timedelta(days=1)
    ye = yil_etiketi(fy)
    istenen = [("YEAR", f"{ye} Yılı" if Durum.mali_ay == 1 else f"{ye} Mali Yılı", bas, ay_ekle(bas, 12) - gun)]
    istenen += [("QUARTER", f"Q{n + 1} {ye}", ay_ekle(bas, 3 * n), ay_ekle(bas, 3 * n + 3) - gun) for n in range(4)]
    istenen += [("MONTH", f"{AY_TAM[ay_ekle(bas, n).month - 1]} {ay_ekle(bas, n).year}",
                 ay_ekle(bas, n), ay_ekle(bas, n + 1) - gun) for n in range(12)]
    var = {}
    for r in sorted(liste("reportingPeriods", filtre=f"fiscalYear[eq]:{fy}"), key=lambda r: r.get("startDate") or ""):
        var.setdefault(r["periodType"], []).append(r)
    sira = {}
    yeni = adlandirilan = 0
    for tur, ad, b, e in istenen:
        i = sira[tur] = sira.get(tur, -1) + 1
        mevcut = var.get(tur, [])
        if i < len(mevcut):
            r = mevcut[i]
            if r["name"] != ad and r["name"].startswith("FY"):
                api("PATCH", f"/rest/reportingPeriods/{r['id']}", {"name": ad})
                adlandirilan += 1
            continue
        api("POST", "/rest/reportingPeriods", {"name": ad, "periodType": tur, "fiscalYear": fy,
                                               "startDate": b.isoformat(), "endDate": e.isoformat()})
        yeni += 1
    if yeni or adlandirilan:
        log(f"Mali yıl {ye}: {yeni} dönem oluşturuldu, {adlandirilan} dönem yeniden adlandırıldı")
        donemleri_yukle()


def ceyrek(tarih_iso):
    """Beklenen kapanış tarihinin düştüğü mali çeyrek (Raporlama Dönemleri'nden)."""
    if not tarih_iso:
        return None
    gun = dt.datetime.fromisoformat(tarih_iso.replace("Z", "+00:00")).astimezone(TR).date()
    for _ in range(2):
        for b, e, ad in Durum.ceyrekler:
            if b <= gun.isoformat() <= e:
                return ad
        donem_uret(mali_yil(gun))
    return None


def tarih_tr(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TR).date().isoformat()
