#!/usr/bin/env python3
"""Ascendia şablonu: fırsat aşamaları ve temel alanlar.

Rakip alanları şirketten kaldırıldı (11 Kas): rakipteki işler 02'deki ayrı nesnede.

İlk sürüm 11 Kas 2026 (Ürün rolü, Monster). Aşama listesi taslak; sahibi Ürün rolü.
Idempotent: iki kez çalışınca değişiklik yapmaz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_select, load_objects  # noqa: E402

O = load_objects()

# Satış süreci (kullanıcı kararları 11 Kas 2026):
# Lead-Gen → Lead-inTouch → Pipeline → Upside → Commit → (onay) Audit (sözleşme imzası)
# → Delivery (ürün/hizmet) → Invoice (faturalama) → Won. Audit/Delivery/Invoice arası geçiş serbest;
# Won = sözleşme, teslimat ve faturalamanın üçü de tamamlandı. Lost, DSQ ve Won kilitli.
# Kapanış: Audit, Delivery, Invoice, Won, Lost ya da DSQ'ya ilk geçiş günü.
# ("Commit-Audit" vb. adlar karışıklık yarattığı için Audit / Delivery / Invoice oldu.)
STAGES = [
    ("LEAD_GEN", "Lead-Gen", "blue"),
    ("LEAD_IN_TOUCH", "Lead-inTouch", "turquoise"),
    ("PIPELINE", "Pipeline", "sky"),
    ("UPSIDE", "Upside", "purple"),
    ("COMMIT", "Commit", "orange"),
    ("AUDIT", "Audit", "yellow"),
    ("DELIVERY", "Delivery", "yellow"),
    ("INVOICE", "Invoice", "yellow"),
    ("WON", "Won", "green"),
    ("LOST", "Lost", "red"),
    ("DISQUALIFIED", "DSQ", "gray"),
]
ensure_select(O, "opportunity", "stage", STAGES, default="'LEAD_GEN'", plural="opportunities")

# Fırsat kaynağı (kullanıcı, 11 Kas): kanal ise hangi iş ortağı, 03'teki channelPartner ilişkisinde.
LEAD_SOURCES = [
    ("CHANNEL", "Kanal", "blue"),
    ("OUTBOUND", "Outbound", "orange"),
    ("INBOUND", "Inbound", "green"),
    ("REFERRAL", "Referans", "purple"),
    ("EXISTING_CUSTOMER", "Mevcut müşteri", "turquoise"),
    ("EVENT", "Etkinlik", "yellow"),
]

FIELDS = [
    ("opportunity", "oneTimeFee", "CURRENCY", "Tek Seferlik Ücret", None),
    ("opportunity", "monthlyRecurring", "CURRENCY", "Aylık Yinelenen (MRR)", None),
    ("opportunity", "annualRecurring", "CURRENCY", "Yıllık Yinelenen", None),
    ("opportunity", "contractMonths", "NUMBER", "Sözleşme Süresi (Ay)", None),
    ("opportunity", "renewalDate", "DATE", "Yenileme Tarihi", None),
]
for obj, name, typ, label, options in FIELDS:
    ensure_field(O, obj, name, typ, label, options)
ensure_field(O, "opportunity", "leadSource", "SELECT", "Fırsat Kaynağı", LEAD_SOURCES, plural="opportunities")
