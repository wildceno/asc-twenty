"""Şablon bölüm türü ve yer tutucu sözlüğü birim testleri (liste 15a)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ascendia_motor.paketler.sablon import bolum_turu, yer_tutucu_listesi  # noqa: E402


class Sablon(unittest.TestCase):
    def test_tur_onerisi(self):
        self.assertEqual(bolum_turu([]), ("FIXED", None))
        self.assertEqual(bolum_turu(["musteri_adi", "teklif_tarihi"]), ("FIXED", None))      # CRM'den dolar
        self.assertEqual(bolum_turu(["musteri_durumu"]), ("FILL", None))                     # tanınmayan
        self.assertEqual(bolum_turu(["kalem_tablosu", "toplam"]), ("AUTO", "LINE_TABLE"))
        self.assertEqual(bolum_turu(["urun_aciklamalari"]), ("AUTO", "PRODUCT_DESCRIPTIONS"))

    def test_yer_tutucu_listesi(self):
        s = {"genel_yer_tutucular": ["teklif_no"],
             "bolumler": [{"ad": "Ana kapak", "yer_tutucular": ["musteri_adi"]},
                          {"ad": "Mevcut durum", "yer_tutucular": ["musteri_durumu", "musteri_adi"]}]}
        l = {x["ad"]: (x["tur"], x["bolumler"]) for x in yer_tutucu_listesi(s)}
        self.assertEqual(l["teklif_no"], ("crm", ["üst / alt bilgi"]))
        self.assertEqual(l["musteri_adi"], ("crm", ["Ana kapak", "Mevcut durum"]))
        self.assertEqual(l["musteri_durumu"], ("doldurulacak", ["Mevcut durum"]))
        self.assertEqual(l["gecerlilik"], ("crm", []))              # sözlükte var, dosyada kullanılmamış
        self.assertEqual(l["kalem_tablosu"], ("otomatik", []))
        self.assertEqual({x["ad"] for x in yer_tutucu_listesi()}, set(l) - {"musteri_durumu"})


if __name__ == "__main__":
    unittest.main()
