#!/usr/bin/env python3
"""Teklif modülü veri modeli (liste 14a; plan: kararlar/2026-11-13-teklif-modulu-plan.md).

Katalog (ürün / hizmet), Teklif, Teklif Kalemi, Marj Kuralı; fırsatta Geçerli Teklif; CRM Ayarı'nda teklif geçerlilik
hatırlatma günü. Hesaplanan alanları hesap motorunun TEKLIF paketi yazar (salt okunur). Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, ensure_relation, load_objects  # noqa: E402

RO = {"read_only": True}
WM = "workspaceMember"
ODEME = [("ONE_TIME", "Tek seferlik", "gray"), ("MONTHLY", "Aylık", "blue"), ("YEARLY", "Yıllık", "purple")]
MALIYET = [("PERSONNEL", "Personel", "blue"), ("LICENSE", "Lisans / Tedarikçi", "purple"),
           ("SUBCONTRACT", "Taşeron", "orange"), ("OTHER", "Diğer", "gray")]
DURUM = [("DRAFT", "Taslak", "gray"), ("PENDING_APPROVAL", "Onay bekliyor", "orange"), ("APPROVED", "Onaylandı", "sky"),
         ("SENT", "Gönderildi", "blue"), ("ACCEPTED", "Kabul", "green"), ("REJECTED", "Red", "red"),
         ("REVISED", "Revize edildi", "gray")]

O = load_objects()

# --- Katalog: ürün ya da hizmet (kullanıcı, 13 Kas) ---
O = ensure_object(O, "catalogItem", "catalogItems", "Katalog Kalemi", "Katalog", "IconPackage",
                  "Ürün ve hizmet kataloğu: teklif kalemleri buradan seçilir; değerler teklife kopyalanır.")
for name, typ, label, opts in [
    ("kind", "SELECT", "Tür", [("PRODUCT", "Ürün", "blue"), ("SERVICE", "Hizmet", "green")]),
    ("shortDescription", "TEXT", "Kısa Tanım", None),
    # Detay Açıklama: 26_katalog_aciklama.py (biçimli metin, `details`)
    ("unit", "TEXT", "Birim", None),
    ("unitCost", "CURRENCY", "Birim Maliyet", None),
    ("listPrice", "CURRENCY", "Liste Fiyatı", None),
    ("billing", "SELECT", "Maliyetlendirme", ODEME),
    ("costType", "SELECT", "Maliyet Türü", MALIYET),
    ("active", "BOOLEAN", "Aktif", None),
]:
    ensure_field(O, "catalogItem", name, typ, label, opts)
ensure_relation(O, "catalogItem", "supplier", "Tedarikçi", "partner", "Katalog Kalemleri", "IconTruck", "IconPackage",
                "catalogItems")

# --- Teklif ---
O = ensure_object(O, "quote", "quotes", "Teklif", "Teklifler", "IconFileInvoice",
                  "Fırsata bağlı teklif; her revizyon yeni sürüm. Gönderilen teklif fırsatın rakamlarını belirler.")
ensure_relation(O, "quote", "opportunity", "Fırsat", "opportunity", "Teklifler", "IconTargetArrow", "IconFileInvoice",
                "quotes")
for name, typ, label, opts, ro in [
    ("status", "SELECT", "Durum", DURUM, False),
    ("version", "NUMBER", "Sürüm", None, True),
    ("validUntil", "DATE", "Geçerlilik Tarihi", None, False),
    ("contractMonths", "NUMBER", "Süre (Ay)", None, False),
    ("channelShareRate", "NUMBER", "Kanal Payı %", None, False),
    ("channelShareBase", "SELECT", "Kanal Payı Tabanı", [("REVENUE", "Ciro", "blue"), ("GROSS_PROFIT", "Brüt kâr", "green")], False),
    ("channelShareScope", "MULTI_SELECT", "Kanal Payı Kapsamı (boş = tümü)", MALIYET, False),
    ("priceEscalation", "SELECT", "Fiyat Artışı",
     [("NONE", "Yok", "gray"), ("FIXED", "Sabit yıllık %", "blue"), ("INFLATION", "Enflasyon kadar", "orange")], False),
    ("priceEscalationRate", "NUMBER", "Yıllık Fiyat Artışı %", None, False),
    ("sentAt", "DATE_TIME", "Gönderim", None, True),
    ("fxRateDate", "DATE", "Kur Tarihi", None, True),
    ("currencyBreakdown", "RAW_JSON", "Para Birimi Kırılımı", None, True),
    ("revenueReporting", "CURRENCY", "Gelir (Raporlama)", None, True),
    ("costReporting", "CURRENCY", "Maliyet (Raporlama)", None, True),
    ("channelShareReporting", "CURRENCY", "Kanal Payı (Raporlama)", None, True),
    ("grossProfitReporting", "CURRENCY", "Brüt Kâr (Raporlama)", None, True),
    ("marginPercent", "NUMBER", "Marj %", None, True),
    ("systemWarning", "TEXT", "Sistem Uyarısı", None, True),
    ("reminderSentFor", "TEXT", "Hatırlatma (sistem)", None, True),
]:
    ensure_field(O, "quote", name, typ, label, opts, read_only=ro)
ensure_relation(O, "quote", "approver", "Onaylayıcı", WM, "Onaylanacak Teklifler", "IconUserCheck", "IconFileInvoice",
                "quotesToApprove")
ensure_relation(O, "quote", "approvedBy", "Onaylayan", WM, "Onayladığı Teklifler", "IconUserCheck", "IconFileInvoice",
                "approvedQuotes")
ensure_relation(O, "opportunity", "currentQuote", "Geçerli Teklif", "quote", "Geçerli Olduğu Fırsatlar", "IconFileInvoice",
                "IconTargetArrow", "currentForOpportunities")

# --- Teklif Kalemi ---
O = ensure_object(O, "quoteLine", "quoteLines", "Teklif Kalemi", "Teklif Kalemleri", "IconListDetails",
                  "Teklifin kalemleri: katalogdan ya da teklife özel. Katalog değerleri kopyalanır.")
ensure_relation(O, "quoteLine", "quote", "Teklif", "quote", "Kalemler", "IconFileInvoice", "IconListDetails", "lines")
ensure_relation(O, "quoteLine", "catalogItem", "Katalog Kalemi", "catalogItem", "Teklif Kalemleri", "IconPackage",
                "IconListDetails", "quoteLines")
ensure_relation(O, "quoteLine", "supplier", "Tedarikçi", "partner", "Teklif Kalemleri (Tedarikçi)", "IconTruck",
                "IconListDetails", "supplierQuoteLines")
for name, typ, label, opts, ro in [
    ("section", "TEXT", "Bölüm", None, False),
    ("sortOrder", "NUMBER", "Sıra", None, False),
    ("description", "TEXT", "Açıklama", None, False),
    ("quantity", "NUMBER", "Miktar", None, False),
    ("unit", "TEXT", "Birim", None, False),
    ("unitCost", "CURRENCY", "Birim Maliyet", None, False),
    ("unitPrice", "CURRENCY", "Birim Fiyat", None, False),
    ("listPrice", "CURRENCY", "Liste Fiyatı", None, False),
    ("discountPercent", "NUMBER", "İndirim %", None, False),
    ("billing", "SELECT", "Ödeme Şekli", ODEME, False),
    ("months", "NUMBER", "Süre (Ay, boş = teklif süresi)", None, False),
    ("costType", "SELECT", "Maliyet Türü", MALIYET, False),
    ("optionGroup", "TEXT", "Seçenek Grubu", None, False),
    ("isDefaultOption", "BOOLEAN", "Varsayılan Seçenek", None, False),
    ("lineRevenue", "CURRENCY", "Kalem Geliri", None, True),
    ("lineCost", "CURRENCY", "Kalem Maliyeti", None, True),
]:
    ensure_field(O, "quoteLine", name, typ, label, opts, read_only=ro)

# --- Marj Kuralı (Yönetim) ---
O = ensure_object(O, "marginRule", "marginRules", "Marj Kuralı", "Marj Kuralları", "IconShieldCheck",
                  "Teklif marjı eşiğin altındaysa onaylayıcının onayı gerekir; birden fazla eşik olabilir.")
ensure_field(O, "marginRule", "thresholdPercent", "NUMBER", "Eşik Marj %")
ensure_relation(O, "marginRule", "approver", "Onaylayıcı", WM, "Onaylayıcısı Olduğu Marj Kuralları", "IconUserCheck",
                "IconShieldCheck", "marginRulesToApprove")

# --- CRM Ayarı ---
ensure_field(O, "crmSetting", "quoteReminderDays", "NUMBER", "Teklif Geçerlilik Hatırlatma (gün)")
