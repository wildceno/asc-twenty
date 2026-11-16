#!/usr/bin/env python3
"""Enflasyon öngörüsü (liste 14c; plan: kararlar/2026-11-13-teklif-modulu-plan.md).

Enflasyon Öngörüsü: para birimi × sözleşme yılı (1..5) başına yıllık %. TRY ve USD'yi hesap motoru kaynaklardan yazar
(TCMB Piyasa Katılımcıları Anketi, Fed ekonomik projeksiyonları); "Elle sabitlendi" işaretli kayda motor dokunmaz,
başka para birimi elle eklenebilir. Teklifte hesapta kullanılan öngörü "Kullanılan Enflasyon" alanında saklanır
(gönderilmiş teklifte sabit). Yönetim nesnesi: satış rolleri görmez (12_yetkiler). Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, load_objects  # noqa: E402

O = load_objects()
O = ensure_object(O, "inflationForecast", "inflationForecasts", "Enflasyon Öngörüsü", "Enflasyon Öngörüleri", "IconTrendingUp",
                  "Teklif hesabında maliyetlere (ve seçilirse fiyata) yıl yıl uygulanan enflasyon öngörüsü.")
for name, typ, label in [
    ("forecastCurrency", "TEXT", "Para Birimi"),
    ("contractYear", "NUMBER", "Sözleşme Yılı"),
    ("ratePercent", "NUMBER", "Yıllık Enflasyon %"),
    ("source", "TEXT", "Kaynak"),
    ("sourceDate", "DATE", "Yayın Tarihi"),
    ("manual", "BOOLEAN", "Elle Sabitlendi (motor değiştirmez)"),
]:
    ensure_field(O, "inflationForecast", name, typ, label)
ensure_field(O, "quote", "inflationUsed", "RAW_JSON", "Kullanılan Enflasyon", read_only=True)
