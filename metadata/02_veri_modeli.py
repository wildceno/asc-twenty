#!/usr/bin/env python3
"""Ascendia şablonu: şirket, kişi, fırsat (lead dahil) alanları ve yeni nesneler.

Kullanıcı kararları (11 Kas 2026):
- Lead ayrı nesne değil; uygunluk, sinyal ve takip bilgisi fırsatta.
- Şirkette kimlik + ticari/finansal bilgi.
- Sözleşme: yalnız Ascendia'nın imzaladıkları (LTV buradan).
- Rakip Hizmeti: şirketin rakiplerden aldığı işler, şirket başına istediği kadar.
- Temas: kim, kime, ne zaman, hangi kanal, sekans adımı, sonuç.
Idempotent: iki kez çalışınca değişiklik yapmaz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import (ensure_field, ensure_object, ensure_relation,  # noqa: E402
                    load_objects, remove_field)

O = load_objects()

# --- Eski tekil rakip alanları (veri yoksa kaldırılır) ---
remove_field(O, "company", "companies", "incumbentProvider")
remove_field(O, "company", "companies", "incumbentContractEnd")

# --- Şirket: kimlik + ticari/finansal ---
CURRENCIES = [("TRY", "TRY", "red"), ("EUR", "EUR", "blue"), ("USD", "USD", "green"), ("GBP", "GBP", "purple")]
for name, typ, label, opts in [
    ("sector", "TEXT", "Sektör", None),
    ("employeeCount", "NUMBER", "Çalışan Sayısı", None),
    ("legalName", "TEXT", "Ticari Unvan", None),
    ("taxOffice", "TEXT", "Vergi Dairesi", None),
    ("taxNumber", "TEXT", "Vergi No", None),
    ("mersisNumber", "TEXT", "MERSİS No", None),
    ("billingAddress", "ADDRESS", "Fatura Adresi", None),
    ("eInvoice", "BOOLEAN", "E-Fatura Mükellefi", None),
    ("billingEmail", "EMAILS", "Fatura E-postası", None),
    ("paymentTermDays", "NUMBER", "Ödeme Vadesi (Gün)", None),
    ("defaultCurrency", "SELECT", "Para Birimi", CURRENCIES),
]:
    ensure_field(O, "company", name, typ, label, opts)

# --- Kişi ---
DATA_SOURCES = [("APOLLO", "Apollo", "blue"), ("LUSHA", "Lusha", "purple"),
                ("LINKEDIN", "LinkedIn", "sky"), ("MANUAL", "Elle", "gray")]
for name, typ, label, opts in [
    ("dataSource", "SELECT", "Veri Kaynağı", DATA_SOURCES),
    ("doNotContact", "BOOLEAN", "İletişim İstemiyor", None),
    ("optOutDate", "DATE", "Ret Tarihi", None),
]:
    ensure_field(O, "person", name, typ, label, opts)

# --- Fırsat: lead aşamasının uygunluk, sinyal ve takip bilgisi ---
ICP_FIT = [("HIGH", "Yüksek", "green"), ("MEDIUM", "Orta", "yellow"), ("LOW", "Düşük", "red")]
for name, typ, label, opts in [
    ("icpFit", "SELECT", "ICP Uyumu", ICP_FIT),
    ("fitRationale", "TEXT", "Uygunluk Gerekçesi", None),
    ("whyNow", "TEXT", "Neden Şimdi", None),
    ("signalSource", "LINKS", "Sinyal Kaynağı", None),
    ("campaign", "TEXT", "Parti / Kampanya", None),
    ("closeReason", "TEXT", "DSQ / Lost Nedeni", None),
]:
    ensure_field(O, "opportunity", name, typ, label, opts)

# --- Sözleşme (yalnız Ascendia'nın imzaladıkları) ---
O = ensure_object(O, "contract", "contracts", "Sözleşme", "Sözleşmeler", "IconFileCertificate",
                  "Ascendia'nın imzaladığı sözleşmeler. LTV ve yenileme buradan.")
ensure_relation(O, "contract", "company", "Şirket", "company", "Sözleşmeler", "IconBuildingSkyscraper", "IconFileCertificate", "contracts")
ensure_relation(O, "contract", "opportunity", "Fırsat", "opportunity", "Sözleşmeler", "IconTargetArrow", "IconFileCertificate", "contracts")
CONTRACT_STATUS = [("SIGNING", "İmzada", "yellow"), ("ACTIVE", "Aktif", "green"), ("ENDED", "Bitti", "gray"),
                   ("RENEWED", "Yenilendi", "blue"), ("CANCELLED", "İptal", "red")]
for name, typ, label, opts in [
    ("service", "TEXT", "Hizmet", None),
    ("startDate", "DATE", "Başlangıç", None),
    ("endDate", "DATE", "Bitiş", None),
    ("contractMonths", "NUMBER", "Süre (Ay)", None),
    ("oneTimeFee", "CURRENCY", "Tek Seferlik Ücret", None),
    ("monthlyFee", "CURRENCY", "Aylık Ücret", None),
    ("annualFee", "CURRENCY", "Yıllık Ücret", None),
    ("totalValue", "CURRENCY", "Toplam Değer", None),
    ("remainingDays", "NUMBER", "Kalan Gün", None),
    ("status", "SELECT", "Durum", CONTRACT_STATUS),
]:
    ensure_field(O, "contract", name, typ, label, opts)
# Sözleşme dosyaları 08'deki Sözleşme Belgeleri nesnesinde (tek dosya alanı kaldırıldı, 11 Kas)

# --- Rakip Hizmeti ---
O = ensure_object(O, "competitorService", "competitorServices", "Rakip Hizmeti", "Rakip Hizmetleri",
                  "IconSwords", "Şirketin rakip firmalardan aldığı hizmetler ve bitiş tarihleri.")
ensure_relation(O, "competitorService", "company", "Şirket", "company", "Rakip Hizmetleri", "IconBuildingSkyscraper", "IconSwords", "competitorServices")
for name, typ, label in [
    ("competitor", "TEXT", "Rakip Firma"),
    ("service", "TEXT", "Hizmet"),
    ("contractEnd", "DATE", "Sözleşme Bitişi"),
    ("note", "TEXT", "Not"),
]:
    ensure_field(O, "competitorService", name, typ, label)

# --- Temas ---
O = ensure_object(O, "touchpoint", "touchpoints", "Temas", "Temaslar", "IconMessages",
                  "Kişiyle her temas: e-posta, arama, toplantı, LinkedIn; kim yaptı, sekans adımı, sonuç.")
ensure_relation(O, "touchpoint", "person", "Kişi", "person", "Temaslar", "IconUser", "IconMessages", "touchpoints")
ensure_relation(O, "touchpoint", "company", "Şirket", "company", "Temaslar", "IconBuildingSkyscraper", "IconMessages", "touchpoints")
ensure_relation(O, "touchpoint", "opportunity", "Fırsat", "opportunity", "Temaslar", "IconTargetArrow", "IconMessages", "touchpoints")
ensure_relation(O, "touchpoint", "performedBy", "Yapan", "workspaceMember", "Yaptığı Temaslar", "IconUserCircle", "IconMessages", "performedTouchpoints")
TP_TYPE = [("EMAIL", "E-posta", "blue"), ("CALL", "Arama", "green"),
           ("MEETING", "Toplantı", "purple"), ("LINKEDIN", "LinkedIn mesajı", "sky")]
TP_DIR = [("OUTBOUND", "Giden", "orange"), ("INBOUND", "Gelen", "turquoise")]
TP_RESULT = [("NO_REPLY", "Cevap yok", "gray"), ("POSITIVE", "Olumlu", "green"), ("NEGATIVE", "Olumsuz", "red"),
             ("REFERRED", "Yönlendirdi", "yellow"), ("MEETING_BOOKED", "Toplantı alındı", "purple")]
for name, typ, label, opts in [
    ("channel", "SELECT", "Tür", TP_TYPE),
    ("direction", "SELECT", "Yön", TP_DIR),
    ("sequenceStep", "NUMBER", "Sekans Adımı", None),
    ("occurredAt", "DATE_TIME", "Tarih", None),
    ("summary", "TEXT", "Özet", None),
    ("result", "SELECT", "Sonuç", TP_RESULT),
]:
    ensure_field(O, "touchpoint", name, typ, label, opts)
