"""Akış şablonu testleri (liste 15c): içerik slaytı çoğaltma, tablo bölme, resim kopyası, son kapak sonda, PDF."""
import io
import unittest

from belge_servisi.akis import sayfala
from belge_servisi.doldur import uret
from belge_servisi.oku import oku
from testler.ornek_uret import pptx_akis_ornek

PARAGRAF = "Bu bir test paragrafıdır; sayfalama tahminini sınamak için yeterince uzun tutulmuştur. " * 4
TABLO = {"basliklar": ["Kalem", "Miktar", "Tutar"],
         "satirlar": [[f"Test kalemi {i}", "1", "10,00 USD"] for i in range(1, 41)],
         "toplamlar": [["Toplam (USD)", "", "400,00 USD"]]}
BLOKLAR = [{"baslik": "Giriş", "tur": "metin", "metin": "\n".join([PARAGRAF] * 12)},
           {"baslik": "Teklif", "tur": "tablo", "tablo": TABLO},
           {"baslik": "Ürün açıklamaları", "tur": "aciklamalar", "ogeler": [{"ad": "Test kalemi 1", "aciklama": "Açıklama."}]}]


class Akis(unittest.TestCase):
    def test_okuma(self):
        o = oku(pptx_akis_ornek())
        self.assertEqual([b["ad"] for b in o["bolumler"]], ["Ana kapak", "İçerik", "Son kapak"])
        self.assertIn("icerik", o["bolumler"][1]["yer_tutucular"])

    def test_sayfalama_tablo_bolunur(self):
        s = sayfala(BLOKLAR, 480, 620, 11)
        self.assertGreater(len(s), 2)
        tablolar = [v for sayfa in s for t, v, _ in sayfa if t == "tablo"]
        self.assertGreater(len(tablolar), 1, "40 satır tek sayfaya sığmamalı")
        self.assertEqual(sum(len(t["satirlar"]) for t in tablolar), 41)
        for sayfa in s:
            self.assertLessEqual(sum(h for _, _, h in sayfa), 620 + 12)

    def test_uretim(self):
        from pptx import Presentation
        s = uret(pptx_akis_ornek(), {"degerler": {"musteri_adi": "Örnek Müşteri", "teklif_no": "2"}, "bolum_sayisi": 3,
                                     "akis": BLOKLAR, "pdf": True})
        p = Presentation(io.BytesIO(s["belge"]))
        n = len(p.slides)
        self.assertGreater(n, 4, "içerik birden fazla slayta yayılmalı")
        metin = lambda sl: " ".join(sh.text_frame.text for sh in sl.shapes if sh.has_text_frame)
        self.assertIn("Hazırlanan: Örnek Müşteri", metin(p.slides[0]))
        self.assertIn("Son kapak · Örnek Müşteri", metin(p.slides[n - 1]))
        for sl in list(p.slides)[1:n - 1]:
            self.assertIn("Alt bilgi · Teklif 2", metin(sl))
            self.assertEqual(sum(1 for sh in sl.shapes if sh.shape_type == 13), 1, "her içerik slaytında resim")
            for sh in sl.shapes:
                if sh.has_table:
                    self.assertEqual(sh.table.cell(0, 0).text, "Kalem", "tablo başlığı her sayfada")
        self.assertEqual(oku(s["belge"])["yer_tutucular"], [])
        self.assertTrue(s["pdf"].startswith(b"%PDF"))

    def test_icerik_yoksa_slayt_cikar(self):
        from pptx import Presentation
        s = uret(pptx_akis_ornek(), {"degerler": {"musteri_adi": "X", "teklif_no": "1"}, "bolum_sayisi": 3, "akis": []})
        self.assertEqual(len(Presentation(io.BytesIO(s["belge"])).slides), 2)

    def test_duzen_isaretleri(self):
        """{{bosluk}} bir satır boşluk, {{sayfa_sonu}} yeni sayfa; bölüm başlığı sayfa başında boşluksuz (16 Kas)."""
        b = [{"baslik": "Bir", "tur": "metin", "metin": "Satır A\n{{bosluk}}\nSatır B {{ sayfa_sonu }}Satır C"},
             {"baslik": "İki", "tur": "metin", "metin": "Satır D"}]
        sayfalar = sayfala(b, 600, 400, 12)
        self.assertEqual(len(sayfalar), 2)
        ilk = [v["satirlar"] for _, v, _ in sayfalar[0]]
        self.assertEqual(ilk, [["Bir"], ["Satır A"], [""], ["Satır B"]])
        ikinci = sayfalar[1]
        self.assertEqual([v["satirlar"] for _, v, _ in ikinci], [["Satır C"], ["İki"], ["Satır D"]])
        self.assertEqual(ikinci[1][1]["once"], 24)     # sayfa ortasındaki bölüm başlığı: bölüm arası boşluk
        self.assertEqual(sayfalar[0][0][1]["once"], 0)  # sayfanın ilk başlığı: boşluk yok


if __name__ == "__main__":
    unittest.main()
