#!/usr/bin/env python3
"""Ascendia şablonu: hedefler.

Kullanıcı kararları (11 Kas 2026):
- Hedef: kişi + rol + raporlama dönemi; altında hedef kalemleri (metrik, hedef tutar, ağırlık %).
  Performans = Σ ağırlık × gerçekleşme oranı.
- Metrikler: Gross Profit, Revenue (= TCV), ARR, MRR. MRR = aylık + yıllık ÷ 12, ARR = MRR × 12.
- Gerçekleşen: dönemde kapanan (gerçek kapanış tarihi dönem içinde; Lost/DSQ hariç) ve kişinin hedefteki
  rolde yer aldığı fırsatlar; raporlama para biriminde. Motor hesaplar.
- Pazarlama çalışanlarının ölçümü sonra ele alınacak.
Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, ensure_relation, load_objects  # noqa: E402

O = load_objects()
RO = {"read_only": True}

# --- Fırsat: MRR / ARR (asıl para biriminde ve raporlama biriminde; motor hesaplar) ---
ensure_field(O, "opportunity", "mrr", "CURRENCY", "MRR", **RO)
ensure_field(O, "opportunity", "arr", "CURRENCY", "ARR", **RO)
ensure_field(O, "opportunity", "mrrReporting", "CURRENCY", "MRR (Raporlama)", **RO)
ensure_field(O, "opportunity", "arrReporting", "CURRENCY", "ARR (Raporlama)", **RO)

# --- Hedef ---
O = ensure_object(O, "target", "targets", "Hedef", "Hedefler", "IconTarget",
                  "Çalışan hedefi: kişi, rol, dönem; kalemleri ağırlıklı metriklerden oluşur.")
ensure_relation(O, "target", "member", "Çalışan", "workspaceMember", "Hedefleri",
                "IconUserCircle", "IconTarget", "targets")
ensure_relation(O, "target", "period", "Dönem", "reportingPeriod", "Hedefler",
                "IconCalendarStats", "IconTarget", "targets")
TARGET_ROLES = [("PERSONAL", "Kişisel", "blue"), ("MANAGER", "Yönetici (ekip)", "purple")]
ensure_field(O, "target", "targetRole", "SELECT", "Rol", TARGET_ROLES, plural="targets")
ensure_field(O, "target", "attainmentPercent", "NUMBER", "Gerçekleşme %",
             settings={"type": "number", "decimals": 1}, **RO)

# --- Hedef kalemi ---
O = ensure_object(O, "targetLine", "targetLines", "Hedef Kalemi", "Hedef Kalemleri", "IconListCheck",
                  "Hedefin bir metriği: hedef tutar, ağırlık, gerçekleşen.")
ensure_relation(O, "targetLine", "target", "Hedef", "target", "Kalemler", "IconTarget", "IconListCheck", "lines")
METRICS = [("GROSS_PROFIT", "Gross Profit", "green"), ("REVENUE", "Revenue (TCV)", "blue"),
           ("ARR", "ARR", "purple"), ("MRR", "MRR", "sky")]
ensure_field(O, "targetLine", "metric", "SELECT", "Metrik", METRICS)
ensure_field(O, "targetLine", "targetAmount", "CURRENCY", "Hedef Tutar")
ensure_field(O, "targetLine", "weightPercent", "NUMBER", "Ağırlık %", settings={"type": "number", "decimals": 0})
ensure_field(O, "targetLine", "actualAmount", "CURRENCY", "Gerçekleşen", **RO)
ensure_field(O, "targetLine", "attainmentPercent", "NUMBER", "Gerçekleşme %",
             settings={"type": "number", "decimals": 1}, **RO)
