#!/usr/bin/env python3
"""Paraşüt fatura entegrasyonu (liste 21; kullanıcı kararları 15 Kas 2026).

Fırsat Invoice aşamasına geçince onaylanan tekliften Paraşüt'te satış faturası kaydı (resmîleştirme e-fatura / e-arşiv
Paraşüt'te elle). Tek seferlik kalemler ilk faturada; aylık / yıllık kalemleri sözleşme süresince her dönem hesap motoru
faturalar (Paraşüt API tekrarlama planını açmıyor — 15 Kas OpenAPI v4.1.0 okundu). Cari vergi no, yoksa adla eşlenir,
yoksa oluşturulur (şirketin Vergi No, Vergi Dairesi ve Fatura Adresi alanları 02_veri_modeli.py'de). KDV kalemden, yoksa CRM Ayarı'ndaki varsayılandan. Tahsilat durumu 00/08/16'da Paraşüt'ten. Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, load_objects  # noqa: E402

O = load_objects()
for nesne, name, typ, label, opts, ro in [
    ("company", "parasutContactId", "TEXT", "Paraşüt Cari (sistem)", None, True),
    ("catalogItem", "vatRate", "NUMBER", "KDV %", None, False),
    ("quoteLine", "vatRate", "NUMBER", "KDV %", None, False),
    ("crmSetting", "defaultVatRate", "NUMBER", "Varsayılan KDV %", None, False),
    ("opportunity", "invoiceSchedule", "RAW_JSON", "Fatura Planı (Paraşüt)", None, True),
    ("opportunity", "collectionStatus", "SELECT", "Tahsilat Durumu",
     [("UNPAID", "Ödenmedi", "gray"), ("PARTIAL", "Kısmen ödendi", "orange"), ("PAID", "Ödendi", "green"),
      ("OVERDUE", "Gecikmiş", "red")], True),
    ("opportunity", "parasutMessage", "TEXT", "Paraşüt Mesajı", None, True),
    ("opportunity", "parasutCheckedAt", "DATE_TIME", "Paraşüt Kontrolü", None, True),
]:
    ensure_field(O, nesne, name, typ, label, opts, read_only=ro)
