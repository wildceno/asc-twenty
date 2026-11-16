#!/usr/bin/env python3
"""Ascendia şablonu: raporlama dönemleri ve kapanan fırsat kilidi.

Kullanıcı kararları (11 Kas 2026):
- Çalışma alanının (müşterinin) raporlama ayarları: mali yıl başlangıcı, hedef dönemi (aylık/çeyreklik/yıllık).
- Dönemlerin başlangıç ve bitiş tarihleri otomatik oluşur, elle düzenlenebilir.
- Audit, Delivery, Invoice, Won, Lost, DSQ'daki fırsatın teklif ve maliyet bilgileri değişmez:
  motor kapanış anındaki değerleri Aşama Geçmişi'ne yazar, sonraki değişiklikleri geri alır.
Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, load_objects  # noqa: E402

O = load_objects()
RO = {"read_only": True}

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
         "Kasım", "Aralık"]
ensure_field(O, "crmSetting", "fiscalYearStartMonth", "SELECT", "Mali Yıl Başlangıcı",
             [(f"M{i + 1:02d}", ad, "blue") for i, ad in enumerate(AYLAR)])
PERIOD_TYPES = [("MONTH", "Aylık", "sky"), ("QUARTER", "Çeyreklik", "blue"), ("YEAR", "Yıllık", "purple")]
ensure_field(O, "crmSetting", "targetPeriodType", "SELECT", "Hedef Dönemi", PERIOD_TYPES)

# Raporlama dönemi: motor her mali yıl için yıl, 4 çeyrek ve 12 ay üretir; tarihler elle düzenlenebilir.
O = ensure_object(O, "reportingPeriod", "reportingPeriods", "Raporlama Dönemi", "Raporlama Dönemleri",
                  "IconCalendarStats", "Mali yıl, çeyrek ve ay dönemleri. Sistem üretir, tarihler düzenlenebilir.")
ensure_field(O, "reportingPeriod", "periodType", "SELECT", "Dönem Türü",
             [("YEAR", "Yıl", "purple"), ("QUARTER", "Çeyrek", "blue"), ("MONTH", "Ay", "sky")], **RO)
ensure_field(O, "reportingPeriod", "fiscalYear", "NUMBER", "Mali Yıl", **RO)
ensure_field(O, "reportingPeriod", "startDate", "DATE", "Başlangıç")
ensure_field(O, "reportingPeriod", "endDate", "DATE", "Bitiş")

# Kapanış anındaki teklif/maliyet değerleri (kilit için)
ensure_field(O, "stageChange", "closingSnapshot", "RAW_JSON", "Kapanış Değerleri", **RO)
