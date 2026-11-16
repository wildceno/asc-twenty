"""Paraşüt fatura planı ve bağlantısı (liste 21). Paraşüt yanıtları taklit edilir (gerçek erişim başvuru onayından sonra)."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ascendia_motor.paketler import fatura  # noqa: E402
from ascendia_motor.paketler.fatura import (ay_ekle, cari_govdesi, fatura_anahtari, fatura_govdesi, fatura_plani,  # noqa: E402
                                            tahsilat_ozeti)


def p(t, k):
    return {"amountMicros": int(round(t * 1e6)), "currencyCode": k}


KALEMLER = [
    {"id": "1", "name": "Kurulum", "quantity": 1, "unitPrice": p(1000, "TRY"), "billing": "ONE_TIME", "vatRate": 20, "sortOrder": 1},
    {"id": "2", "name": "Destek", "quantity": 2, "unitPrice": p(100, "USD"), "billing": "MONTHLY", "discountPercent": 10, "sortOrder": 2},
    {"id": "3", "name": "Lisans", "quantity": 1, "unitPrice": p(1200, "USD"), "billing": "YEARLY", "vatRate": 0, "sortOrder": 3},
]


class Plan(unittest.TestCase):
    def test_ay_ekle_ay_sonu(self):
        self.assertEqual(ay_ekle(dt.date(2026, 1, 31), 1), dt.date(2026, 2, 28))
        self.assertEqual(ay_ekle(dt.date(2026, 1, 31), 13), dt.date(2027, 2, 28))
        self.assertEqual(ay_ekle(dt.date(2028, 1, 31), 1), dt.date(2028, 2, 29))
        self.assertEqual(ay_ekle(dt.date(2026, 11, 15), 2), dt.date(2027, 1, 15))

    def test_plan(self):
        # 3 ay, başlangıç 31 Oca: TRY kurulum 1.000 (01-31); USD: 01-31 destek 2×100×0,9=180 + lisans 1200×3/12=300 → 480;
        # 02-28 ve 03-31 destek 180. Destek KDV'si varsayılandan (20), lisans 0.
        plan, eksik = fatura_plani("F1", {"contractMonths": 3}, KALEMLER, dt.date(2026, 1, 31), 20)
        self.assertEqual(eksik, [])
        self.assertEqual([(x["tarih"], x["pb"], x["tutar"]) for x in plan],
                         [("2026-01-31", "TRY", 1000.0), ("2026-01-31", "USD", 480.0), ("2026-02-28", "USD", 180.0),
                          ("2026-03-31", "USD", 180.0)])
        usd = plan[1]["kalemler"]
        self.assertEqual([(k["ad"], k["miktar"], k["birim_fiyat"], k["indirim"], k["kdv"]) for k in usd],
                         [("Destek", 2.0, 100.0, 10.0, 20.0), ("Lisans", 0.25, 1200.0, 0.0, 0.0)])
        self.assertEqual(len({x["anahtar"] for x in plan}), 4)
        self.assertEqual(plan[0]["anahtar"], fatura_anahtari("F1", "2026-01-31", "TRY"))   # tekrar üretilebilir

    def test_sabit_artis_ikinci_yil(self):
        k = [{"id": "a", "name": "Aylık", "quantity": 1, "unitPrice": p(100, "USD"), "billing": "MONTHLY", "vatRate": 20}]
        plan, _ = fatura_plani("F", {"contractMonths": 14, "priceEscalation": "FIXED", "priceEscalationRate": 10}, k, dt.date(2026, 1, 1), None)
        self.assertEqual([x["tutar"] for x in plan], [100.0] * 12 + [110.0, 110.0])

    def test_kdv_yoksa_eksik(self):
        k = [{"id": "a", "name": "KDV'siz", "quantity": 1, "unitPrice": p(10, "TRY"), "billing": "ONE_TIME"}]
        self.assertEqual(fatura_plani("F", {"contractMonths": 1}, k, dt.date(2026, 1, 1), None), ([], ["KDV'siz"]))

    def test_tahsilat_ozeti(self):
        self.assertEqual(tahsilat_ozeti(["PAID", "PAID"]), "PAID")
        self.assertEqual(tahsilat_ozeti(["PAID", "UNPAID"]), "PARTIAL")
        self.assertEqual(tahsilat_ozeti(["UNPAID", "OVERDUE"]), "OVERDUE")
        self.assertEqual(tahsilat_ozeti(["UNPAID"]), "UNPAID")
        self.assertIsNone(tahsilat_ozeti([None]))


class Govde(unittest.TestCase):
    def test_fatura_govdesi(self):
        plan, _ = fatura_plani("F1", {"contractMonths": 1}, KALEMLER[:1], dt.date(2026, 1, 31), 20)
        g = fatura_govdesi(plan[0], "77", {"name": "Örnek A.Ş.", "taxNumber": "1234567890",
                                              "billingAddress": {"addressStreet1": "Örnek Cad. 1", "addressCity": "İstanbul"}}, "Fırsat · 2026-01-31")
        d = g["data"]
        self.assertEqual((d["type"], d["attributes"]["item_type"], d["attributes"]["currency"], d["attributes"]["issue_date"]),
                         ("sales_invoices", "invoice", "TRL", "2026-01-31"))
        self.assertEqual((d["attributes"]["tax_number"], d["attributes"]["city"], d["attributes"]["billing_address"]),
                         ("1234567890", "İstanbul", "Örnek Cad. 1"))
        self.assertEqual(d["relationships"]["contact"]["data"], {"id": "77", "type": "contacts"})
        det = d["relationships"]["details"]["data"][0]["attributes"]
        self.assertEqual((det["quantity"], det["unit_price"], det["vat_rate"]), (1.0, 1000.0, 20.0))
        self.assertNotIn("discount_type", det)
        self.assertEqual(d["relationships"]["external_reference_key"]["data"]["attributes"]["key"], plan[0]["anahtar"])

    def test_cari_govdesi(self):
        a = cari_govdesi({"name": "Örnek A.Ş.", "taxOffice": "Kadıköy"})["data"]["attributes"]
        self.assertEqual((a["name"], a["account_type"], a["contact_type"], a["tax_office"]), ("Örnek A.Ş.", "customer", "company", "Kadıköy"))


class Baglanti(unittest.TestCase):
    def test_ayni_anahtar_422_mevcut_fatura(self):
        cagri = []

        def sahte(a, yontem, yol, govde=None):
            cagri.append((yontem, yol))
            if yontem == "POST":
                raise fatura.ParasutHatasi(422, {"errors": [{"meta": {"sales_invoice_id": 555}}]}, "Bu key ile daha önce")
            return {"data": {"id": "555", "attributes": {"invoice_no": "A-1"}}}
        plan, _ = fatura_plani("F1", {"contractMonths": 1}, KALEMLER[:1], dt.date(2026, 1, 31), 20)
        with mock.patch.object(fatura, "ps", sahte):
            f = fatura.fatura_kes({}, plan[0], "77", {}, "x")
        self.assertEqual(f["id"], "555")
        self.assertEqual(cagri, [("POST", "/sales_invoices"), ("GET", "/sales_invoices/555")])

    def test_yenileme_belirteci_saklanir(self):
        with tempfile.TemporaryDirectory() as k:
            oturum = os.path.join(k, "oturum.json")
            json.dump({"refresh_token": "eski"}, open(oturum, "w"))
            istekler = []

            def sahte_urlopen(r, timeout=0):
                istekler.append(r.data.decode())
                return io.BytesIO(json.dumps({"access_token": "A", "expires_in": 300, "refresh_token": "yeni"}).encode())
            with mock.patch.object(fatura, "OTURUM_FILE", oturum), mock.patch.object(fatura, "SECRET_FILE", os.path.join(k, "yok")), \
                    mock.patch.object(fatura.urllib.request, "urlopen", sahte_urlopen):
                fatura._belirtec.update(deger=None, bitis=0)
                self.assertEqual(fatura.belirtec({"client_id": "c", "token_url": "https://x/token"}), "A")
            self.assertIn("refresh_token=eski", istekler[0])
            self.assertEqual(json.load(open(oturum))["refresh_token"], "yeni")


if __name__ == "__main__":
    unittest.main()
