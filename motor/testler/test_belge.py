"""Teklif belgesi verisi birim testleri (liste 15b): Türkçe sayı biçimi, kalem tablosu, doldurulan alan varsayılanı."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ascendia_motor.paketler.belge import akis_bloklari, doldurulacak_varsayilanlari, kalem_tablosu, md_metin, tr_sayi  # noqa: E402


def p(t, k):
    return {"amountMicros": int(round(t * 1e6)), "currencyCode": k}


class Belge(unittest.TestCase):
    def test_tr_sayi(self):
        self.assertEqual(tr_sayi(1234567.5), "1.234.567,50")
        self.assertEqual(tr_sayi(0), "0,00")

    def test_kalem_tablosu(self):
        k = [{"id": "a", "name": "Kurulum", "quantity": 1, "unitPrice": p(1000, "USD"), "lineRevenue": p(1000, "USD"),
              "billing": "ONE_TIME", "sortOrder": 1},
             {"id": "b", "name": "Destek", "quantity": 2, "unitPrice": p(100, "USD"), "lineRevenue": p(4800, "USD"), "discountPercent": 0,
              "billing": "MONTHLY", "sortOrder": 2, "optionGroup": "D", "isDefaultOption": True},
             {"id": "c", "name": "Destek yıllık", "quantity": 2, "unitPrice": p(1000, "USD"), "lineRevenue": p(4000, "USD"),
              "discountPercent": 10, "billing": "YEARLY", "sortOrder": 3, "optionGroup": "D"}]
        t = kalem_tablosu(k, 24, {"USD": {"gelir": 5800.0, "maliyet": 0}, "TRY": {"gelir": 0.0, "maliyet": 500.0}})
        self.assertEqual(t["satirlar"][0], ["Kurulum", "1", "1.000,00 USD", "", "Tek seferlik", "1.000,00 USD"])
        self.assertEqual(t["satirlar"][1], ["Destek (seçenek: D)", "2", "100,00 USD", "", "Aylık × 24 ay", "4.800,00 USD"])
        self.assertEqual(t["satirlar"][2], ["Destek yıllık (seçenek: D, alternatif)", "2", "1.000,00 USD", "%10", "Yıllık × 2 yıl", "4.000,00 USD"])
        self.assertEqual(t["toplamlar"], [["Toplam (USD)", "", "", "", "", "5.800,00 USD"]])

    def test_varsayilan_metin(self):
        b = [{"sectionType": "FILL", "defaultText": "Metin", "placeholders": ["musteri_durumu", "musteri_adi"]},
             {"sectionType": "FILL", "defaultText": "İki alan", "placeholders": ["x", "y"]},
             {"sectionType": "FIXED", "defaultText": "Yok", "placeholders": ["z"]}]
        self.assertEqual(doldurulacak_varsayilanlari(b), {"musteri_durumu": "Metin"})


    def test_md_metin(self):
        md = "## Hizmet Tanımı\n**SAP Basis** hizmetleri.\n\n\n\n- Sistem izleme\n- *Yedekleme*\n1. Bir"
        self.assertEqual(md_metin(md), "Hizmet Tanımı\nSAP Basis hizmetleri.\n\n• Sistem izleme\n• Yedekleme\n1. Bir")
        self.assertEqual(md_metin(None), "")
        self.assertEqual(md_metin("dosya_adi_ornek ve 2*3"), "dosya_adi_ornek ve 2*3")

    def test_akis_bloklari(self):
        b = [{"id": "3", "name": "Teklif", "sortOrder": 103, "sectionType": "AUTO", "autoContent": "LINE_TABLE", "removable": False},
             {"id": "1", "name": "Hakkımızda", "sortOrder": 101, "sectionType": "FIXED", "removable": True,
              "defaultText": "{{musteri_adi}} için {{bilinmeyen}}hazırlandı."},
             {"id": "2", "name": "Durum", "sortOrder": 102, "sectionType": "FILL", "removable": True, "defaultText": "Varsayılan"},
             {"id": "4", "name": "Çıkan", "sortOrder": 104, "sectionType": "FIXED", "removable": True, "defaultText": "x"},
             {"id": "5", "name": "Kilitli", "sortOrder": 105, "sectionType": "FIXED", "removable": False, "defaultText": "y"}]
        out = akis_bloklari(b, {104, 105}, {"bolum:2": "Satışçı metni"}, {"musteri_adi": "Örnek"}, {"basliklar": ["K"]}, [])
        self.assertEqual([(x["baslik"], x["tur"]) for x in out],
                         [("Hakkımızda", "metin"), ("Durum", "metin"), ("Teklif", "tablo"), ("Kilitli", "metin")])
        self.assertEqual(out[0]["metin"], "Örnek için hazırlandı.")
        self.assertEqual(out[1]["metin"], "Satışçı metni")
        self.assertEqual(akis_bloklari(b[2:3], set(), {}, {}, None, [])[0]["metin"], "Varsayılan")
        # düzen işaretleri korunur, belge servisi işler (16 Kas)
        d = [{"id": "9", "name": "D", "sortOrder": 101, "sectionType": "FIXED", "defaultText": "A\n{{bosluk}}\n{{ sayfa_sonu }}\n{{x}}B"}]
        self.assertEqual(akis_bloklari(d, set(), {}, {}, None, [])[0]["metin"], "A\n{{bosluk}}\n{{ sayfa_sonu }}\nB")


if __name__ == "__main__":
    unittest.main()
