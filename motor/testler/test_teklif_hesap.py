"""Teklif hesabı birim testleri: elle hesaplanmış örnekler (kuruşu kuruşuna). Plan: kararlar/2026-11-13-teklif-modulu-plan.md.
Çalıştırma: cd motor && python3 -m unittest discover -s testler"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import datetime as dt  # noqa: E402

from ascendia_motor.paketler.teklif_hesap import (enflasyon_sozlugu, enflasyonsuz_pb, gereken_onaylayici, kalem_hesap,  # noqa: E402
                                                  sayilan_kalemler, teklif_ozet, tl_yillari, usd_yillari)


def p(t, k):
    return {"amountMicros": int(round(t * 1e6)), "currencyCode": k}


# Kur: 1 USD = 40 TRY, 1 EUR = 44 TRY → TRY'den USD'ye ÷40, EUR'dan USD'ye ×1.1
KUR = {"USD": 40.0, "EUR": 44.0, "TRY": 1.0}


def cevir(t, a, b):
    if a not in KUR or b not in KUR:
        return None
    return t * KUR[a] / KUR[b]


class Ornekler(unittest.TestCase):
    def test_1_yalniz_tek_seferlik(self):
        # 2 × 5.000 USD, %10 indirim → gelir 9.000; maliyet 2 × 3.000 = 6.000; brüt 3.000; marj %33,3
        t = {"contractMonths": 12}
        k = [{"id": "a", "quantity": 2, "unitPrice": p(5000, "USD"), "unitCost": p(3000, "USD"), "discountPercent": 10,
              "billing": "ONE_TIME"}]
        o = teklif_ozet(t, k, cevir, "USD")
        self.assertEqual((o["gelir"], o["maliyet"], o["brut"], o["marj"]), (9000.0, 6000.0, 3000.0, 33.3))
        self.assertEqual(o["firsat"]["ONE_TIME"], (9000.0, 6000.0))

    def test_2_aylik_12_ay(self):
        # 10 kullanıcı × 25 USD/ay × 12 ay = 3.000; maliyet 10 × 10 × 12 = 1.200; fırsata aylık 250 / 100
        t = {"contractMonths": 12}
        k = [{"id": "a", "quantity": 10, "unitPrice": p(25, "USD"), "unitCost": p(10, "USD"), "billing": "MONTHLY"}]
        o = teklif_ozet(t, k, cevir, "USD")
        self.assertEqual((o["gelir"], o["maliyet"], o["brut"]), (3000.0, 1200.0, 1800.0))
        self.assertEqual(o["firsat"]["MONTHLY"], (250.0, 100.0))

    def test_3_karisik_para_kanal_secenek(self):
        # Süre 24 ay. Kurulum tek seferlik 80.000 TRY (maliyet 40.000 TRY) → USD 2.000 / 1.000
        # Lisans yıllık 1.000 USD × 5, maliyet 600 USD → 24 ay = 2 yıl: gelir 10.000, maliyet 6.000
        # Destek: seçenek grubu "Destek": aylık 100 EUR (varsayılan) / yıllık 1.000 EUR → aylık sayılır:
        #   24 × 100 EUR = 2.400 EUR → 2.640 USD; maliyet 24 × 50 EUR = 1.200 EUR → 1.320 USD
        # Toplam gelir 14.640, maliyet 8.320; kanal %10 ciro, kapsam yalnız Lisans → 1.000; brüt 5.320; marj %36,3
        t = {"contractMonths": 24, "channelShareRate": 10, "channelShareBase": "REVENUE", "channelShareScope": ["LICENSE"]}
        k = [
            {"id": "1", "sortOrder": 1, "quantity": 1, "unitPrice": p(80000, "TRY"), "unitCost": p(40000, "TRY"), "billing": "ONE_TIME", "costType": "PERSONNEL"},
            {"id": "2", "sortOrder": 2, "quantity": 5, "unitPrice": p(1000, "USD"), "unitCost": p(600, "USD"), "billing": "YEARLY", "costType": "LICENSE"},
            {"id": "3", "sortOrder": 3, "quantity": 1, "unitPrice": p(100, "EUR"), "unitCost": p(50, "EUR"), "billing": "MONTHLY", "costType": "PERSONNEL", "optionGroup": "Destek", "isDefaultOption": True},
            {"id": "4", "sortOrder": 4, "quantity": 1, "unitPrice": p(1000, "EUR"), "unitCost": p(500, "EUR"), "billing": "YEARLY", "costType": "PERSONNEL", "optionGroup": "Destek"},
        ]
        o = teklif_ozet(t, k, cevir, "USD")
        self.assertEqual(o["gelir"], 14640.0)
        self.assertEqual(o["maliyet"], 8320.0)
        self.assertEqual(o["kanal"], 1000.0)
        self.assertEqual(o["brut"], 5320.0)
        self.assertEqual(o["marj"], 36.3)
        self.assertEqual(o["kirilim"]["TRY"], {"gelir": 80000.0, "maliyet": 40000.0})
        self.assertEqual(o["kirilim"]["EUR"], {"gelir": 2400.0, "maliyet": 1200.0})
        self.assertEqual(sorted(o["sayilan"]), ["1", "2", "3"])

    def test_4_kanal_brut_kar_tabani(self):
        # Gelir 1.000, maliyet 600 → brüt 400; kanal %25 brüt kârdan = 100; kalan brüt 300; marj %30
        t = {"contractMonths": 12, "channelShareRate": 25, "channelShareBase": "GROSS_PROFIT"}
        k = [{"id": "a", "quantity": 1, "unitPrice": p(1000, "USD"), "unitCost": p(600, "USD"), "billing": "ONE_TIME"}]
        o = teklif_ozet(t, k, cevir, "USD")
        self.assertEqual((o["kanal"], o["brut"], o["marj"]), (100.0, 300.0, 30.0))

    def test_5_fiyat_artisi_ve_enflasyon(self):
        # Aylık 100 USD, maliyet 50 USD, 24 ay. Fiyat sabit %10 artış: 12×100 + 12×110 = 2.520
        # Maliyet USD enflasyonu yıl 1 için %3: 12×50 + 12×51,5 = 1.218
        h = kalem_hesap({"quantity": 1, "unitPrice": p(100, "USD"), "unitCost": p(50, "USD"), "billing": "MONTHLY"},
                        24, "FIXED", 10, {"USD": [3.0]})
        self.assertAlmostEqual(h["gelir"], 2520.0, places=6)
        self.assertAlmostEqual(h["maliyet"], 1218.0, places=6)

    def test_6_yillik_kismi_yil(self):
        # Yıllık 1.200, 18 ay → 1.200 + 600 = 1.800 (fırsattaki yıllık × S/12 kuralıyla aynı)
        h = kalem_hesap({"quantity": 1, "unitPrice": p(1200, "USD"), "unitCost": p(0, "USD"), "billing": "YEARLY"}, 18)
        self.assertAlmostEqual(h["gelir"], 1800.0, places=6)

    def test_7_eksik_kur(self):
        o = teklif_ozet({"contractMonths": 1}, [{"id": "a", "quantity": 1, "unitPrice": p(10, "JPY"), "billing": "ONE_TIME"}], cevir, "USD")
        self.assertEqual(o["eksik_kur"], ["JPY"])

    def test_8_onaylayici(self):
        kurallar = [{"thresholdPercent": 20, "approverId": "yonetici"}, {"thresholdPercent": 10, "approverId": "super"}]
        self.assertIsNone(gereken_onaylayici(25, kurallar))
        self.assertEqual(gereken_onaylayici(15, kurallar), "yonetici")
        self.assertEqual(gereken_onaylayici(8, kurallar), "super")
        self.assertIsNone(gereken_onaylayici(None, kurallar))

    def test_9_secenek_varsayilan_yoksa_ilk(self):
        k = [{"id": "x", "sortOrder": 2, "optionGroup": "G"}, {"id": "y", "sortOrder": 1, "optionGroup": "G"}]
        self.assertEqual([s["id"] for s in sayilan_kalemler(k)], ["y"])


    def test_10_tl_yillari_tcmb_kasim_2026(self):
        # TCMB PKA Kasım 2026 (EVDS, uygun ortalama): 12 ay 24,04; 24 ay 18,02; 5 yıl 12,15
        # Yıl 3 ve 4 doğrusal: adım (12,15 − 18,02) / 3 = −1,9567 → 16,0633; 14,1067
        y = tl_yillari(24.04, 18.02, 12.15)
        self.assertEqual([round(v, 2) for v in y], [24.04, 18.02, 16.06, 14.11, 12.15])

    def test_11_usd_yillari_fed_eylul_2026(self):
        # Fed SEP 16 Eyl 2026 PCE medyanı: 2026 3,7; 2027 2,3; 2028 2,1; 2029 2,0; uzun dönem 2,0
        # Hesap günü 13 Kas 2026: yıl 1 ortası Mayıs 2027 → 2,3; yıl 2 → 2028; yıl 3 → 2029; yıl 4-5 → uzun dönem
        p_ = {2026: 3.7, 2027: 2.3, 2028: 2.1, 2029: 2.0}
        self.assertEqual(usd_yillari(p_, 2.0, dt.date(2026, 11, 13)), [2.3, 2.1, 2.0, 2.0, 2.0])
        # Hesap günü 10 Ocak 2026: yıl 1 ortası Temmuz 2026 → 3,7
        self.assertEqual(usd_yillari(p_, 2.0, dt.date(2026, 1, 10))[0], 3.7)

    def test_12_sozluk_ve_cok_yillik_maliyet(self):
        kayit = [{"forecastCurrency": "TRY", "contractYear": 2, "ratePercent": 18.02}, {"forecastCurrency": "TRY", "contractYear": 1, "ratePercent": 24.04},
                 {"forecastCurrency": "usd", "contractYear": 1, "ratePercent": 2.3}]
        e = enflasyon_sozlugu(kayit)
        self.assertEqual(e, {"TRY": [24.04, 18.02], "USD": [2.3]})
        # Aylık maliyet 1.000 TRY, 36 ay: 12×1.000 + 12×1.240,40 + 12×1.240,40×1,1802 = 12.000 + 14.884,80 + 17.567,04
        h = kalem_hesap({"quantity": 1, "unitPrice": p(0, "TRY"), "unitCost": p(1000, "TRY"), "billing": "MONTHLY"}, 36, enflasyon=e)
        self.assertAlmostEqual(h["maliyet"], 12000 + 14884.8 + 12 * 1240.4 * 1.1802, places=4)
        self.assertAlmostEqual(h["maliyet"], 44451.84, places=2)

    def test_13_enflasyonu_bilinmeyen_pb(self):
        k = [{"billing": "MONTHLY", "unitCost": p(10, "EUR"), "unitPrice": p(20, "GBP")},
             {"billing": "ONE_TIME", "unitCost": p(10, "JPY")},
             {"billing": "MONTHLY", "months": 12, "unitCost": p(10, "CHF")}]
        self.assertEqual(enflasyonsuz_pb(k, 24, {"TRY": [1.0]}), ["EUR"])
        self.assertEqual(enflasyonsuz_pb(k, 24, {"TRY": [1.0]}, "INFLATION"), ["EUR", "GBP"])
        self.assertEqual(enflasyonsuz_pb(k, 12, {}), [])


if __name__ == "__main__":
    unittest.main()
