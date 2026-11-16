"""E-posta temas / cevap görevi saf işlevleri (liste 19)."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ascendia_motor.paketler.eposta import cevap_saatleri, sahip_ve_karsi, toplanti_taraflari  # noqa: E402


class Eposta(unittest.TestCase):
    def test_gelen(self):
        k = [{"role": "FROM", "handle": "ayse@musteri.com", "personId": "P1"},
             {"role": "TO", "handle": "satis@firma.com", "workspaceMemberId": "U1"}]
        self.assertEqual(sahip_ve_karsi("INCOMING", k, {}), ("U1", k[0]))

    def test_gelen_kutu_eslestirme(self):
        k = [{"role": "FROM", "handle": "ayse@musteri.com", "personId": "P1"},
             {"role": "TO", "handle": "Deneme@Gmail.com"}]
        self.assertEqual(sahip_ve_karsi("INCOMING", k, {"deneme@gmail.com": "U2"}), ("U2", k[0]))

    def test_giden_kisi_olmayan_atlanir(self):
        k = [{"role": "FROM", "handle": "satis@firma.com", "workspaceMemberId": "U1"},
             {"role": "TO", "handle": "bilinmeyen@x.com"}, {"role": "CC", "handle": "ali@musteri.com", "personId": "P2"}]
        self.assertEqual(sahip_ve_karsi("OUTGOING", k, {}), ("U1", k[2]))

    def test_ic_yazisma_ve_kisisiz_gonderen(self):
        ic = [{"role": "FROM", "handle": "a@firma.com", "workspaceMemberId": "U1"}, {"role": "TO", "handle": "b@firma.com", "workspaceMemberId": "U2"}]
        self.assertEqual(sahip_ve_karsi("INCOMING", ic, {})[1], None)
        kisisiz = [{"role": "FROM", "handle": "noreply@banka.com"}, {"role": "TO", "handle": "a@firma.com", "workspaceMemberId": "U1"}]
        self.assertEqual(sahip_ve_karsi("INCOMING", kisisiz, {}), ("U1", None))

    def test_cevap_saatleri(self):
        t0 = dt.datetime(2026, 11, 14, 9, 0, tzinfo=dt.timezone.utc)
        g = [("a", t0), ("b", t0 + dt.timedelta(hours=2)), ("c", t0 + dt.timedelta(hours=10))]
        self.assertEqual(cevap_saatleri(g, t0 + dt.timedelta(hours=5, minutes=30)), {"a": 5.5, "b": 3.5})


    def test_toplanti_taraflari(self):
        k = [{"handle": "kutu@gmail.com", "isOrganizer": True}, {"handle": "ayse@musteri.com", "personId": "P1"},
             {"handle": "ayse@musteri.com", "personId": "P1"}, {"handle": "uye@firma.com", "workspaceMemberId": "U9"},
             {"handle": "yabanci@x.com"}]
        sahip, biz, karsi = toplanti_taraflari(k, {"kutu@gmail.com": "U1"})
        self.assertEqual((sahip, biz, [x["personId"] for x in karsi]), ("U1", True, ["P1"]))
        disaridan = [{"handle": "ayse@musteri.com", "personId": "P1", "isOrganizer": True}, {"handle": "uye@firma.com", "workspaceMemberId": "U9"}]
        self.assertEqual(toplanti_taraflari(disaridan, {})[:2], ("U9", False))
        self.assertEqual(toplanti_taraflari([{"handle": "a@f.com", "workspaceMemberId": "U1"}], {})[2], [])


if __name__ == "__main__":
    unittest.main()
