"""Şablon doldurma birim testleri (konteynerde; PDF için LibreOffice gerekir).
Test verisi yapay ve nötrdür ("Örnek Müşteri", yuvarlak test tutarları); gerçek kayıt değildir."""
import io
import unittest

from belge_servisi.doldur import parcalarda_degistir, uret
from belge_servisi.oku import oku
from testler.ornek_uret import docx_ornek, pptx_ornek

TABLO = {"basliklar": ["Kalem", "Miktar", "Birim fiyat", "Tutar"],
         "satirlar": [["Test kalemi A", "2", "100,00 USD", "200,00 USD"], ["Test kalemi B", "1", "50,00 USD", "50,00 USD"]],
         "toplamlar": [["Toplam (USD)", "", "", "250,00 USD"]]}
DEGER = {"musteri_adi": "Örnek Müşteri", "teklif_tarihi": "14.11.2026", "teklif_no": "3", "toplam": "250,00 USD",
         "gecerlilik": "30.11.2026", "sure_ay": "12", "musteri_durumu": "Birinci satır\nİkinci satır", "cozum_ozeti": "Özet metni"}
ACIKLAMA = [{"ad": "Test kalemi A", "aciklama": "A'nın açıklaması"}, {"ad": "Test kalemi B", "aciklama": ""}]


class Parca:
    def __init__(self, t):
        self.text = t


class Degistirme(unittest.TestCase):
    def test_bolunmus_isaret(self):
        p = [Parca("Sayın {{mus"), Parca("teri_adi}}"), Parca(", {{teklif_no}} no'lu")]
        parcalarda_degistir(p, lambda a: {"musteri_adi": "X A.Ş.", "teklif_no": "7"}[a])
        self.assertEqual([x.text for x in p], ["Sayın X A.Ş.", "", ", 7 no'lu"])

    def test_otomatik_isaret_atlanir(self):
        p = [Parca("{{kalem_tablosu}} ve {{toplam}}")]
        parcalarda_degistir(p, lambda a: "T")
        self.assertEqual(p[0].text, "{{kalem_tablosu}} ve T")


class Word(unittest.TestCase):
    def test_uret(self):
        from docx import Document
        girdi = {"degerler": DEGER, "haric": [2], "bolum_sayisi": 6, "kalem_tablosu": TABLO, "urun_aciklamalari": ACIKLAMA}
        s = uret(docx_ornek(), girdi)
        self.assertEqual(s["uzanti"], ".docx")
        o = oku(s["belge"])
        self.assertEqual([b["ad"] for b in o["bolumler"]], ["Ana kapak", "Mevcut durum", "Teklif", "Ürün açıklamaları", "Ticari koşullar"])
        self.assertEqual(o["yer_tutucular"], [], "doldurulmamış işaret kalmamalı")
        d = Document(io.BytesIO(s["belge"]))
        govde = "\n".join(p.text for p in d.paragraphs)
        self.assertIn("Örnek Müşteri için hazırlanmıştır · 14.11.2026", govde)
        self.assertIn("Toplam: 250,00 USD", govde)
        self.assertIn("Teklif 3", d.sections[0].header.paragraphs[0].text)
        tablolar = [[[c.text for c in r.cells] for r in t.rows] for t in d.tables]
        self.assertIn(TABLO["basliklar"], [t[0] for t in tablolar])
        kalem = next(t for t in tablolar if t[0] == TABLO["basliklar"])
        self.assertEqual(kalem[-1], TABLO["toplamlar"][0])
        self.assertIn(["Geçerlilik", "30.11.2026"], next(t for t in tablolar if t[0][0] == "Geçerlilik"))
        kalin = [r.text for p in d.paragraphs for r in p.runs if r.bold]
        self.assertIn("Test kalemi A", kalin)
        self.assertIn("A'nın açıklaması", govde)
        self.assertEqual(s["uyarilar"], [])

    def test_imza_capasi_beyaz(self):
        from docx import Document
        d = Document()
        d.add_paragraph("İmza:")
        d.add_paragraph("{{imza}}")
        b = io.BytesIO()
        d.save(b)
        s = uret(b.getvalue(), {"degerler": {"imza": "/imza/"}, "bolum_sayisi": 1})
        r = [r for p in Document(io.BytesIO(s["belge"])).paragraphs for r in p.runs if r.text == "/imza/"][0]
        self.assertEqual(str(r.font.color.rgb), "FFFFFF")

    def test_eksik_deger_uyari(self):
        s = uret(docx_ornek(), {"degerler": {}, "bolum_sayisi": 6})
        self.assertTrue(any("musteri_adi" in u for u in s["uyarilar"]))

    def test_dosya_degismisse_durur(self):
        with self.assertRaises(Exception):
            uret(docx_ornek(), {"degerler": {}, "bolum_sayisi": 9})

    def test_pdf(self):
        s = uret(docx_ornek(), {"degerler": DEGER, "bolum_sayisi": 6, "kalem_tablosu": TABLO, "pdf": True})
        self.assertTrue(s["pdf"].startswith(b"%PDF"))


class PowerPoint(unittest.TestCase):
    def test_uret(self):
        from pptx import Presentation
        girdi = {"degerler": DEGER, "haric": [2], "bolum_sayisi": 5, "kalem_tablosu": TABLO, "pdf": True}
        s = uret(pptx_ornek(), girdi)
        self.assertEqual(s["uzanti"], ".pptx")
        p = Presentation(io.BytesIO(s["belge"]))
        self.assertEqual(len(p.slides), 5)   # 6 slayttan Hakkımızda çıktı
        o = oku(s["belge"])
        self.assertEqual(o["yer_tutucular"], [])
        tablolar = [sh for sl in p.slides for sh in sl.shapes if sh.has_table]
        self.assertEqual(len(tablolar), 1)
        self.assertEqual(tablolar[0].table.cell(0, 0).text, "Kalem")
        metin = " ".join(sh.text_frame.text for sl in p.slides for sh in sl.shapes if sh.has_text_frame)
        self.assertIn("Örnek Müşteri için teklif", metin)
        self.assertTrue(s["pdf"].startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
