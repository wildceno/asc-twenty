"""Günlük (log) ve motorun kendi sağlık işaretleri: hata sayacı, takılma bekçisi zamanları."""
import collections
import datetime as dt
import time

from ascendia_motor.cekirdek.ayar import TR


# Sistem sağlığı için motorun kendi durumu (liste 7): hata sayacı ve takılma bekçisinin işaretleri
SAGLIK = {"baslangic": time.time(), "hatalar": collections.deque(maxlen=1000), "son_hata": None,
          "mesgul_basi": None, "mesgul_is": None, "zamanlayici_son": time.time(), "portal": "kapalı", "twenty_yok": False}


def log(*a):
    print(dt.datetime.now(TR).strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)
    if a and str(a[0]).startswith("HATA"):
        SAGLIK["hatalar"].append(time.time())
        SAGLIK["son_hata"] = (time.time(), " ".join(str(x) for x in a)[:500])


def oku(yol):
    with open(yol) as fh:
        return fh.read().strip()
