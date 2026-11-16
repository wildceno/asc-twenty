"""Paket kaydı birim testi: webhook olaylarının işlere çevrilmesi eski motorla aynı mı, aç/kapat çalışıyor mu.
Çalıştırma: cd motor && python3 -m unittest discover -s testler"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ascendia_motor.cekirdek import paketler  # noqa: E402
from ascendia_motor.cekirdek.durum import Durum  # noqa: E402


class PaketKaydi(unittest.TestCase):
    def setUp(self):
        Durum.acik_paketler = None

    def test_eski_dagitimla_ayni(self):
        # Eski motor: opportunity → fırsat işi + takip; ayar/kur/dönem → hepsi; hedef nesneleri → hedefler;
        # temas/görev/kural → takip. Silinen fırsat için fırsat işi yok, takip var.
        beklenen = {
            "opportunity.updated": ["firsat:F1", "takip"], "opportunity.deleted": ["takip"],
            "crmSetting.updated": ["hepsi", "rakip"], "exchangeRate.created": ["hepsi"], "reportingPeriod.updated": ["hepsi"],
            "target.updated": ["hedefler"], "targetLine.deleted": ["hedefler"], "forecastRate.updated": ["hedefler"],
            "touchpoint.created": ["takip"], "task.updated": ["takip"], "taskTarget.deleted": ["takip"],
            "followUpRule.updated": ["takip"], "competitorService.created": ["rakip"], "company.updated": [], "company.created": ["hesap:F1"],
        }
        for ad, isler in beklenen.items():
            self.assertEqual(sorted(paketler.olay_isleri(ad, {"id": "F1"})), sorted(isler), ad)

    def test_teklif_olaylari(self):
        self.assertIn("teklif:Q1", paketler.olay_isleri("quoteLine.updated", {"id": "L1", "quoteId": "Q1"}))
        self.assertIn("teklif:Q1", paketler.olay_isleri("quote.created", {"id": "Q1"}))
        self.assertIn("teklif_kural", paketler.olay_isleri("marginRule.updated", {"id": "M1"}))
        self.assertIn("teklif_firsat:F1", paketler.olay_isleri("opportunity.updated", {"id": "F1", "currentQuoteId": "Q1", "_degisen": ["oneTimeFee"]}))
        self.assertNotIn("teklif_firsat:F1", paketler.olay_isleri("opportunity.updated", {"id": "F1", "_degisen": ["oneTimeFee"]}))

    def test_hesap_durumu(self):
        from ascendia_motor.paketler.satis_sureci import hesap_durumu
        b = "2026-11-13"
        self.assertEqual(hesap_durumu([], b), "PROSPECT")
        self.assertEqual(hesap_durumu([{"status": "SIGNING"}], b), "PROSPECT")
        self.assertEqual(hesap_durumu([{"status": "ACTIVE", "endDate": "2027-01-01"}], b), "CUSTOMER")
        self.assertEqual(hesap_durumu([{"status": "ACTIVE", "endDate": "2026-11-01"}], b), "FORMER")
        self.assertEqual(hesap_durumu([{"status": "ENDED"}, {"status": "ACTIVE"}], b), "CUSTOMER")
        self.assertEqual(hesap_durumu([{"status": "CANCELLED"}], b), "FORMER")
        self.assertEqual(paketler.olay_isleri("contract.updated", {"id": "C1", "companyId": "S1"}), ["hesap:S1"])

    def test_firsat_sirket_kilidi(self):
        self.assertIn("firsat_sirket:F1", paketler.olay_isleri("opportunity.updated", {"id": "F1", "_degisen": ["company"]}))
        self.assertNotIn("firsat_sirket:F1", paketler.olay_isleri("opportunity.updated", {"id": "F1", "_degisen": ["name"]}))

    def test_sirket_sorumlusu(self):
        self.assertEqual(paketler.olay_isleri("company.updated", {"id": "S1", "_degisen": ["accountManager"]}), ["sirket:S1"])
        self.assertEqual(paketler.olay_isleri("company.updated", {"id": "S1", "_degisen": ["name"]}), [])

    def test_kapali_paket(self):
        Durum.acik_paketler = {"SATIS_SURECI", "HEDEFLER", "SAGLIK"}
        self.assertEqual(paketler.olay_isleri("touchpoint.created", {"id": "x"}), [])
        self.assertIsNone(paketler.is_islevi("takip"))
        self.assertNotIn("takip", paketler.periyodik())
        self.assertIsNotNone(paketler.is_islevi("firsat:F1"))

    def test_islevler_ve_sonraki(self):
        self.assertEqual(paketler.sonraki_isler("firsat:F1"), ["hedefler"])
        self.assertEqual(paketler.birlestirme("takip"), 60)
        self.assertEqual(paketler.periyodik(), ["teklif_hatirlat", "enflasyon_guncelle", "imza_kontrol", "fatura_zaman", "eposta", "takvim", "takip", "rakip"])
        self.assertIn("rakip", paketler.olay_isleri("competitorService.updated", {"id": "R1"}))


if __name__ == "__main__":
    unittest.main()
