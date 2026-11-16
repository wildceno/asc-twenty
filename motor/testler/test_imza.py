"""DocuSign zarfı ve kontrol saatleri (liste 20)."""
import base64
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ascendia_motor.paketler.imza import CAPA, dosya_listesi, kontrol_dilimi, zarf  # noqa: E402


class Imza(unittest.TestCase):
    def test_zarf(self):
        z = zarf("Teklif X", b"%PDF-1.4", "x.pdf", "Ayşe Yılmaz", "ayse@musteri.com")
        self.assertEqual(z["status"], "sent")
        self.assertEqual(base64.b64decode(z["documents"][0]["documentBase64"]), b"%PDF-1.4")
        s = z["recipients"]["signers"][0]
        self.assertEqual((s["email"], s["name"]), ("ayse@musteri.com", "Ayşe Yılmaz"))
        t = s["tabs"]["signHereTabs"][0]
        self.assertEqual((t["anchorString"], t["anchorIgnoreIfNotPresent"]), (CAPA, "true"))

    def test_dosya_listesi(self):
        okunan = [{"fileId": "f1", "label": "a.pdf", "extension": ".pdf", "url": "https://x/file?token=t"}, {"label": "kimliksiz"}]
        self.assertEqual(dosya_listesi(okunan), [{"fileId": "f1", "label": "a.pdf"}])
        self.assertEqual(dosya_listesi(None), [])

    def test_kontrol_dilimi(self):
        tr = dt.timezone(dt.timedelta(hours=3))
        self.assertEqual(kontrol_dilimi(dt.datetime(2026, 11, 14, 8, 15, tzinfo=tr), None), "2026-11-14 08")
        self.assertIsNone(kontrol_dilimi(dt.datetime(2026, 11, 14, 8, 45, tzinfo=tr), "2026-11-14 08"))
        self.assertIsNone(kontrol_dilimi(dt.datetime(2026, 11, 14, 9, 0, tzinfo=tr), "2026-11-14 08"))
        self.assertEqual(kontrol_dilimi(dt.datetime(2026, 11, 15, 0, 5, tzinfo=tr), "2026-11-14 16"), "2026-11-15 00")


if __name__ == "__main__":
    unittest.main()
