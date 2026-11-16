#!/usr/bin/env python3
"""Ascendia şablonu: hesap ve fırsat rolleri, İş Ortakları.

Kullanıcı kararları (11 Kas 2026):
- Rol adları çevrilmez: Account Manager, Pre-sales, BDM, SDR, Service Manager.
- Şirket: Account Manager (mevcut müşteride hesap yönetimi), Pre-sales,
  Service Manager (satış sonrası hizmetin verilmesinden ve sözleşme süresince hizmetten sorumlu).
- Fırsat: BDM, SDR (hunter), Account Manager, Pre-sales; SDR ile Account Manager birlikte olabilir.
  Her rolde tek kişi. "Sahibi" (owner) forecast sorumlusu olarak kalır.
- İş Ortakları ayrı sayfa: bize iş getirenler (kanal) ve hizmet/ürün aldığımız firmalar (tedarikçi).
  Fırsatta: kaynak kanal ise hangi kanal ortağı; satılacak şeyin alındığı tedarikçi.
Idempotent: iki kez çalışınca değişiklik yapmaz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import (ensure_field, ensure_object, ensure_relation,  # noqa: E402
                    load_objects, remove_field)

O = load_objects()
WM = "workspaceMember"

# --- Roller (çalışma alanı kullanıcısına bağlı) ---
ROLLER = [
    # (nesne, alan, etiket, karşı etiket, karşı alan adı)
    ("company", "accountManager", "Account Manager", "Şirketler (Account Manager)", "accountManagerCompanies"),
    ("company", "preSales", "Pre-sales", "Şirketler (Pre-sales)", "preSalesCompanies"),
    ("company", "serviceManager", "Service Manager", "Şirketler (Service Manager)", "serviceManagerCompanies"),
    ("opportunity", "bdm", "BDM", "Fırsatlar (BDM)", "bdmOpportunities"),
    ("opportunity", "sdr", "SDR", "Fırsatlar (SDR)", "sdrOpportunities"),
    ("opportunity", "accountManager", "Account Manager", "Fırsatlar (Account Manager)", "accountManagerOpportunities"),
    ("opportunity", "preSales", "Pre-sales", "Fırsatlar (Pre-sales)", "preSalesOpportunities"),
    # Kullanıcı (13 Kas): fırsat Audit'e alınınca şirketin Service Manager'ı kopyalanır (motor, liste 12)
    ("opportunity", "serviceManager", "Service Manager", "Fırsatlar (Service Manager)", "serviceManagerOpportunities"),
]
for obj, name, label, inv_label, inv_name in ROLLER:
    ensure_relation(O, obj, name, label, WM, inv_label, "IconUserCircle", "IconBriefcase", inv_name)

# --- İş Ortakları ---
O = ensure_object(O, "partner", "partners", "İş Ortağı", "İş Ortakları", "IconHeartHandshake",
                  "Bize iş getiren kanal ortakları ve hizmet/ürün aldığımız tedarikçiler.")
PARTNER_TYPES = [("CHANNEL", "Kanal ortağı", "blue"), ("SUPPLIER", "Tedarikçi", "orange")]
for name, typ, label, opts in [
    ("partnerType", "MULTI_SELECT", "Ortaklık Türü", PARTNER_TYPES),
    ("domainName", "LINKS", "Alan Adı", None),
    ("linkedinLink", "LINKS", "LinkedIn", None),
    ("note", "TEXT", "Not", None),
]:
    ensure_field(O, "partner", name, typ, label, opts)
ensure_relation(O, "person", "partner", "İş Ortağı", "partner", "Kişiler", "IconHeartHandshake", "IconUser", "people")

# --- Fırsat: kanal ortağı (metin alanı yerine ilişki) ve tedarikçi ---
if O["opportunity"]["fields"].get("channelPartner", {}).get("type") == "TEXT":
    remove_field(O, "opportunity", "opportunities", "channelPartner")
ensure_relation(O, "opportunity", "channelPartner", "Kanal Ortağı", "partner", "Getirdiği Fırsatlar",
                "IconHeartHandshake", "IconTargetArrow", "channelOpportunities")
ensure_relation(O, "opportunity", "supplier", "Tedarikçi", "partner", "Tedarik Ettiği Fırsatlar",
                "IconTruck", "IconTargetArrow", "supplierOpportunities")
