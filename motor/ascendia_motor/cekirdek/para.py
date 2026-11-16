"""Para birimi yardımcıları: micros, kur çevirisi, kalem toplamı (tek seferlik / aylık / yıllık)."""



def micros(c):
    if not c or c.get("amountMicros") in (None, ""):
        return None
    return int(float(c["amountMicros"]))


def para(c):
    m = micros(c)
    return None if m is None or not c.get("currencyCode") else (m / 1e6, c["currencyCode"])


def cevir(tutar, kaynak, hedef, kurlar):
    if kaynak == hedef:
        return tutar
    if kaynak != "TRY" and kaynak not in kurlar or hedef != "TRY" and hedef not in kurlar:
        return None
    try_tutar = tutar * (1 if kaynak == "TRY" else kurlar[kaynak][0])
    return try_tutar / (1 if hedef == "TRY" else kurlar[hedef][0])


def cur(tutar, kod):
    return {"amountMicros": int(round(tutar * 1e6)), "currencyCode": kod}


def toplam(kalemler, ay, kurlar, varsayilan):
    """(tek seferlik, aylık, yıllık) → kalemlerin para biriminde toplam; karışıksa `varsayilan`a çevrilir."""
    dolu = [(k, para(c)) for k, c in kalemler.items() if para(c)]
    if not dolu:
        return None
    kodlar = {p[1] for _, p in dolu}
    hedef = kodlar.pop() if len(kodlar) == 1 else varsayilan
    carpan = {"tek": 1, "aylik": ay or 0, "yillik": (ay or 0) / 12}
    t = 0.0
    for k, (tutar, kod) in dolu:
        v = cevir(tutar, kod, hedef, kurlar)
        if v is None:
            return None
        t += v * carpan[k]
    return t, hedef


def ayni(a, b):
    if isinstance(b, dict) or isinstance(a, dict):
        return micros(a) == micros(b) and (a or {}).get("currencyCode") == (b or {}).get("currencyCode")
    if isinstance(b, float) or isinstance(a, float):
        return a is not None and b is not None and abs(float(a) - float(b)) < 1e-9
    return (a or None) == (b or None)
