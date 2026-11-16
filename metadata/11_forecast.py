#!/usr/bin/env python3
"""Ascendia şablonu: forecast.

Kullanıcı kararları (11 Kas 2026):
- Forecast, total pipeline'daki (Pipeline, Upside, Commit) fırsatlar üzerinden: değer × aşama dönüşüm oranı.
- Dönüşüm oranı başlangıçta elle girilir (müşteri kurulumunda); yeterli geçmiş birikince geçmiş veriye geçilir.
- Dönüşüm hızı kullanılmaz; fırsat beklenen kapanış tarihinin dönemine yazılır.
- Forecast gerçekleşme beklentisi = (gerçekleşen + forecast) ÷ hedef.
Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, load_objects  # noqa: E402

O = load_objects()
RO = {"read_only": True}
YUZDE = {"type": "number", "decimals": 1}

ensure_field(O, "crmSetting", "historyThreshold", "NUMBER", "Geçmiş Veri Eşiği (kapanmış fırsat)")

O = ensure_object(O, "forecastRate", "forecastRates", "Dönüşüm Oranı", "Dönüşüm Oranları", "IconPercentage",
                  "Total pipeline aşamalarının Audit ve sonrasına dönüşme oranı (forecast için).")
ensure_field(O, "forecastRate", "stage", "SELECT", "Aşama",
             [("PIPELINE", "Pipeline", "sky"), ("UPSIDE", "Upside", "purple"), ("COMMIT", "Commit", "orange")])
ensure_field(O, "forecastRate", "manualRate", "NUMBER", "Manuel Oran %", settings=YUZDE)
ensure_field(O, "forecastRate", "historicalRate", "NUMBER", "Geçmiş Oran %", settings=YUZDE, **RO)
ensure_field(O, "forecastRate", "closedCount", "NUMBER", "Kapanmış Fırsat Sayısı", **RO)
ensure_field(O, "forecastRate", "effectiveRate", "NUMBER", "Kullanılan Oran %", settings=YUZDE, **RO)
ensure_field(O, "forecastRate", "rateSource", "SELECT", "Oran Kaynağı",
             [("MANUAL", "Manuel", "gray"), ("HISTORY", "Geçmiş veri", "green")], **RO)

ensure_field(O, "targetLine", "forecastAmount", "CURRENCY", "Forecast", **RO)
ensure_field(O, "targetLine", "forecastAttainmentPercent", "NUMBER", "Forecast Gerçekleşme %", settings=YUZDE, **RO)
ensure_field(O, "target", "forecastAttainmentPercent", "NUMBER", "Forecast Gerçekleşme %", settings=YUZDE, **RO)
