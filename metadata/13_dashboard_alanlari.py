#!/usr/bin/env python3
"""Dashboard için alanlar.

Kullanıcı kararları (11 Kas 2026):
- Dashboard, şirketin raporladığı metrikle (Revenue / Gross Profit / ARR / MRR) ve raporlama para biriminde değer gösterir.
  Ascendia: Revenue, USD.
- Varsayılan olarak içinde bulunulan raporlama dönemi gösterilir; dönem, aşama, kişi filtrelenebilir.
Motor "Bu Dönemde" alanlarını güncel tutar: açık fırsatta beklenen kapanış, kapanmışta gerçek kapanış tarihi
içinde bulunulan dönemdeyse (dönem türü: CRM Ayarı → Hedef Dönemi).
Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, load_objects  # noqa: E402

O = load_objects()
RO = {"read_only": True}

ensure_field(O, "crmSetting", "reportingMetric", "SELECT", "Raporlama Metriği",
             [("REVENUE", "Revenue (TCV)", "blue"), ("GROSS_PROFIT", "Gross Profit", "green"),
              ("ARR", "ARR", "purple"), ("MRR", "MRR", "sky")])
ensure_field(O, "reportingPeriod", "isCurrent", "BOOLEAN", "İçinde Bulunulan Dönem", **RO)
ensure_field(O, "opportunity", "inCurrentPeriod", "BOOLEAN", "Bu Dönemde", **RO)
ensure_field(O, "opportunity", "reportingPeriodName", "TEXT", "Raporlama Dönemi", **RO)
ensure_field(O, "targetLine", "inCurrentPeriod", "BOOLEAN", "Bu Dönemde", **RO)
