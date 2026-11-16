"""Şablon okuma birim testleri. Çalıştırma (konteynerde): python3 -m unittest discover -s testler -t ."""
import unittest

from belge_servisi.oku import OkumaHatasi, oku
from testler.ornek_uret import docx_ornek, pptx_ornek


class Word(unittest.TestCase):
    def setUp(self):
        self.s = oku(docx_ornek())

    def test_bolumler(self):
        self.assertEqual(self.s["bicim"], "DOCX")
        self.assertEqual([b["ad"] for b in self.s["bolumler"]],
                         ["Ana kapak", "Hakkımızda", "Mevcut durum", "Teklif", "Ürün açıklamaları", "Ticari koşullar"])

    def test_yer_tutucular(self):
        b = {x["ad"]: x["yer_tutucular"] for x in self.s["bolumler"]}
        self.assertEqual(b["Ana kapak"], ["musteri_adi", "teklif_tarihi"])
        self.assertEqual(b["Teklif"], ["kalem_tablosu", "toplam"])
        self.assertEqual(b["Ticari koşullar"], ["gecerlilik", "sure_ay"])   # tablodan
        self.assertEqual(self.s["genel_yer_tutucular"], ["teklif_no"])     # üst bilgiden
        self.assertIn("musteri_durumu", self.s["yer_tutucular"])
        self.assertEqual(self.s["uyarilar"], [])

    def test_baslik_yoksa_uyari(self):
        from docx import Document
        import io
        d = Document()
        d.add_paragraph("Yalnız düz metin {{musteri_adi}}")
        b = io.BytesIO()
        d.save(b)
        s = oku(b.getvalue())
        self.assertEqual([x["ad"] for x in s["bolumler"]], ["Ana kapak"])
        self.assertTrue(any("Başlık 1" in u for u in s["uyarilar"]))


class PowerPoint(unittest.TestCase):
    def test_slaytlar_ve_not_ile_birlesme(self):
        s = oku(pptx_ornek())
        self.assertEqual(s["bicim"], "PPTX")
        self.assertEqual([(b["ad"], b["kaynak"]) for b in s["bolumler"]],
                         [("Ana kapak", "slayt 1"), ("Hakkımızda", "slayt 2"), ("Çözüm", "slayt 3–4"),
                          ("Teklif", "slayt 5"), ("Slayt 6", "slayt 6")])
        self.assertEqual(s["bolumler"][2]["yer_tutucular"], ["cozum_ozeti"])
        self.assertEqual(s["bolumler"][3]["yer_tutucular"], ["kalem_tablosu"])
        self.assertTrue(any("Slayt 6" in u for u in s["uyarilar"]))


class Hatalar(unittest.TestCase):
    def test_zip_degil(self):
        with self.assertRaises(OkumaHatasi):
            oku(b"duz metin")


if __name__ == "__main__":
    unittest.main()
