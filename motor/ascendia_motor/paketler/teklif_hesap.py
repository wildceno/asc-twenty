"""Teklif hesabı (saf işlevler, yan etkisiz; birim testli). Plan: kararlar/2026-11-13-teklif-modulu-plan.md.

Kalem: gelir fiyat para biriminde, maliyet maliyet para biriminde (ikisi farklı olabilir: ör. lisans maliyeti USD, satış TL).
Dönem: tek seferlik 1 kez; aylık her ay; yıllık her yıl (son kısmi yıl orantılı) — fırsattaki kuralla aynı (11 Kas).
Çok yıllık süre: yıl k (0'dan) için maliyet × Π(1 + enflasyon_i), fiyat × artış çarpanı (yok / sabit % / enflasyon kadar).
Enflasyon (14c): para birimi → sözleşme yılı başına yıllık % listesi; listede olmayan para birimi için 0 (uyarı verilir).
"""
SOZLESME_YILI = 5   # öngörü tablosunda para birimi başına tutulan yıl sayısı; sonrası son değerle devam eder


def para(c):
    """{'amountMicros', 'currencyCode'} → (tutar, kod) ya da (0, None)."""
    if not c or c.get("amountMicros") in (None, ""):
        return 0.0, (c or {}).get("currencyCode")
    return float(c["amountMicros"]) / 1e6, c.get("currencyCode")


def yil_dilimleri(odeme, ay):
    """Ödeme şekline göre yıl başına (yıl indeksi, tekrar sayısı) listesi. Tek seferlik: [(0, 1)]."""
    if odeme == "ONE_TIME" or not odeme:
        return [(0, 1.0)]
    ay = ay or 0
    out, k = [], 0
    while ay > 0:
        bu_yil = min(12, ay)
        out.append((k, float(bu_yil) if odeme == "MONTHLY" else bu_yil / 12.0))
        ay -= bu_yil
        k += 1
    return out


def carpan(oranlar, k):
    """Yıl k için birikimli çarpan: Π_{i<k}(1 + oran_i/100). oranlar: yıl indeksine göre % listesi (eksikse son değer)."""
    c = 1.0
    for i in range(k):
        o = oranlar[i] if i < len(oranlar) else (oranlar[-1] if oranlar else 0.0)
        c *= 1 + (o or 0.0) / 100
    return c


def kalem_hesap(kalem, teklif_ayi, fiyat_artisi="NONE", artis_orani=0.0, enflasyon=None):
    """Bir teklif kaleminin (gelir, gelir para birimi, maliyet, maliyet para birimi, yıllık kırılım)."""
    enflasyon = enflasyon or {}
    miktar = float(kalem.get("quantity") or 0)
    fiyat, fk = para(kalem.get("unitPrice"))
    maliyet, mk = para(kalem.get("unitCost"))
    indirim = float(kalem.get("discountPercent") or 0) / 100
    odeme = kalem.get("billing") or "ONE_TIME"
    ay = kalem.get("months") or teklif_ayi or 0
    gelir = gider = 0.0
    for k, tekrar in yil_dilimleri(odeme, ay):
        f_enf = enflasyon.get(fk, [])
        m_enf = enflasyon.get(mk, [])
        if fiyat_artisi == "FIXED":
            f_carpan = carpan([artis_orani or 0.0] * (k + 1), k)
        elif fiyat_artisi == "INFLATION":
            f_carpan = carpan(f_enf, k)
        else:
            f_carpan = 1.0
        gelir += miktar * fiyat * (1 - indirim) * tekrar * f_carpan
        gider += miktar * maliyet * tekrar * carpan(m_enf, k)
    return {"gelir": gelir, "gelir_pb": fk, "maliyet": gider, "maliyet_pb": mk, "odeme": odeme,
            "birim_gelir": miktar * fiyat * (1 - indirim), "birim_maliyet": miktar * maliyet}


def sayilan_kalemler(kalemler):
    """Seçenek gruplarında yalnız varsayılan (yoksa sıradaki ilk) sayılır; grupsuz kalemlerin hepsi sayılır."""
    gruplar, out = {}, []
    for k in sorted(kalemler, key=lambda x: (x.get("sortOrder") or 0, x.get("id") or "")):
        g = (k.get("optionGroup") or "").strip()
        if not g:
            out.append(k)
        else:
            gruplar.setdefault(g, []).append(k)
    for g, ks in gruplar.items():
        out.append(next((k for k in ks if k.get("isDefaultOption")), ks[0]))
    return out


def teklif_ozet(teklif, kalemler, cevir, raporlama, enflasyon=None):
    """Teklif toplamları. cevir(tutar, kaynak_pb, hedef_pb) → tutar ya da None (kur yok).
    Döner: para birimi kırılımı, raporlama para biriminde gelir / maliyet / kanal payı / brüt kâr / marj,
    fırsata yazılacak kalemler (raporlama para biriminde tek seferlik, aylık, yıllık gelir ve maliyet)."""
    ay = teklif.get("contractMonths") or 0
    artis = teklif.get("priceEscalation") or "NONE"
    oran = float(teklif.get("priceEscalationRate") or 0)
    kirilim, eksik_kur = {}, set()
    toplam = {"gelir": 0.0, "maliyet": 0.0}
    kapsam_tabani = 0.0
    kapsam = set(teklif.get("channelShareScope") or [])
    firsat = {"ONE_TIME": [0.0, 0.0], "MONTHLY": [0.0, 0.0], "YEARLY": [0.0, 0.0]}   # [gelir, maliyet] birim dönem

    def rp(tutar, pb):
        if not tutar:
            return 0.0
        v = cevir(tutar, pb, raporlama) if pb and pb != raporlama else tutar
        if v is None:
            eksik_kur.add(pb)
            return 0.0
        return v

    sayilan = sayilan_kalemler(kalemler)
    for k in sayilan:
        h = kalem_hesap(k, ay, artis, oran, enflasyon)
        for pb, alan, v in ((h["gelir_pb"], "gelir", h["gelir"]), (h["maliyet_pb"], "maliyet", h["maliyet"])):
            if pb and v:
                d = kirilim.setdefault(pb, {"gelir": 0.0, "maliyet": 0.0})
                d[alan] = round(d[alan] + v, 2)
        g, m = rp(h["gelir"], h["gelir_pb"]), rp(h["maliyet"], h["maliyet_pb"])
        toplam["gelir"] += g
        toplam["maliyet"] += m
        if not kapsam or (k.get("costType") in kapsam):
            kapsam_tabani += g if teklif.get("channelShareBase") != "GROSS_PROFIT" else g - m
        firsat[h["odeme"]][0] += rp(h["birim_gelir"], h["gelir_pb"])
        firsat[h["odeme"]][1] += rp(h["birim_maliyet"], h["maliyet_pb"])
    kanal = max(0.0, kapsam_tabani) * float(teklif.get("channelShareRate") or 0) / 100
    brut = toplam["gelir"] - toplam["maliyet"] - kanal
    return {
        "kirilim": kirilim, "eksik_kur": sorted(eksik_kur),
        "gelir": round(toplam["gelir"], 2), "maliyet": round(toplam["maliyet"], 2), "kanal": round(kanal, 2),
        "brut": round(brut, 2), "marj": round(brut / toplam["gelir"] * 100, 1) if toplam["gelir"] else None,
        "firsat": {o: (round(v[0], 2), round(v[1], 2)) for o, v in firsat.items()}, "sayilan": [k.get("id") for k in sayilan],
    }


def gereken_onaylayici(marj, kurallar):
    """Marj, eşiği aşılan kuralların en düşük eşiklisinin onaylayıcısını gerektirir (en yetkili). Kural yoksa None."""
    if marj is None:
        return None
    uygun = [r for r in kurallar if r.get("thresholdPercent") is not None and marj < float(r["thresholdPercent"])]
    if not uygun:
        return None
    return min(uygun, key=lambda r: float(r["thresholdPercent"])).get("approverId")


def tl_yillari(oniki_ay, yirmidort_ay, bes_yil):
    """TCMB Piyasa Katılımcıları Anketi → sözleşme yılı 1..5 TÜFE öngörüsü.
    Yıl 1: 12 ay sonrasının yıllık TÜFE beklentisi; yıl 2: 24 ay sonrasının; yıl 5: 5 yıl sonrasının.
    Yıl 3 ve 4: 24 ay ile 5 yıl değeri arasında doğrusal geçiş (VARSAYIM: anket bu yılları ayrıca sormuyor)."""
    adim = (bes_yil - yirmidort_ay) / 3
    return [oniki_ay, yirmidort_ay, yirmidort_ay + adim, yirmidort_ay + 2 * adim, bes_yil]


def usd_yillari(projeksiyon, uzun_donem, bugun):
    """Fed (FOMC SEP) PCE enflasyonu medyanı → sözleşme yılı 1..5. projeksiyon: {takvim yılı: %} (Q4/Q4).
    Sözleşme yılı i, ortası (bugün + 6 + 12·(i−1) ay) hangi takvim yılına düşüyorsa o yılın projeksiyonunu alır;
    projeksiyonu olmayan yıllar için uzun dönem değeri. VARSAYIM: sözleşme hesap gününe yakın başlar."""
    out = []
    for i in range(SOZLESME_YILI):
        ay = bugun.month - 1 + 6 + 12 * i
        out.append(projeksiyon.get(bugun.year + ay // 12, uzun_donem))
    return out


def enflasyon_sozlugu(kayitlar):
    """Enflasyon Öngörüsü kayıtları → {para birimi: [yıl1, yıl2, ...]} (eksik yıl son değerle doldurulur)."""
    pb_yil = {}
    for r in kayitlar:
        pb, yil, oran = (r.get("forecastCurrency") or "").strip().upper(), r.get("contractYear"), r.get("ratePercent")
        if pb and yil and oran is not None:
            pb_yil.setdefault(pb, {})[int(yil)] = float(oran)
    out = {}
    for pb, yillar in pb_yil.items():
        liste_, son = [], 0.0
        for i in range(1, max(yillar) + 1):
            son = yillar.get(i, son)
            liste_.append(son)
        out[pb] = liste_
    return out


def enflasyonsuz_pb(kalemler, teklif_ayi, enflasyon, fiyat_artisi="NONE"):
    """12 aydan uzun yinelenen kalemlerde enflasyonu bilinmeyen para birimleri (maliyet; fiyat artışı 'enflasyon kadar'
    ise fiyat da). Bu kalemler o para biriminde enflasyonsuz hesaplanır; teklifte uyarı gösterilir."""
    eksik = set()
    for k in kalemler:
        if (k.get("billing") or "ONE_TIME") == "ONE_TIME" or (k.get("months") or teklif_ayi or 0) <= 12:
            continue
        for alan in ("unitCost",) + (("unitPrice",) if fiyat_artisi == "INFLATION" else ()):
            t, pb = para(k.get(alan))
            if t and pb and pb not in enflasyon:
                eksik.add(pb)
    return sorted(eksik)
