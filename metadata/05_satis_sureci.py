#!/usr/bin/env python3
"""Ascendia şablonu: satış süreci, forecast, gelir/maliyet, kur ve aşama geçmişi alanları.

Kullanıcı kararları (11 Kas 2026):
- Her fırsatta Beklenen Kapanış Tarihi; forecast bununla yönetilir, çeyrek (Q) otomatik hesaplanır.
- Toplam değer gelir kalemlerinden (tek seferlik / aylık / yıllık × süre) otomatik.
- Aynı kalemlerin maliyetleri; Gross Profit otomatik.
- Değer ve Gross Profit, şirketin seçtiği raporlama para biriminde de gösterilir; kur TCMB'den günlük.
- Kapanış (Commit-Audit, Lost, DSQ'ya geçiş) günü Gerçek Kapanış Tarihi olarak sistemce yazılır;
  kapanan fırsatta hesaplar artık güncellenmez. Aşama değişiklikleri tarihleriyle kayıt altında.
- Commit-Audit'e geçen fırsat Sözleşme'ye dönüşür.
Hesapları yapan motor ayrı (bkz. kararlar/); bu betik yalnız veri modelini kurar.
Idempotent: iki kez çalışınca değişiklik yapmaz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, ensure_relation, load_objects  # noqa: E402

O = load_objects()
RO = {"read_only": True}

# --- Fırsat: forecast ---
ensure_field(O, "opportunity", "closeDate", "DATE_TIME", "Beklenen Kapanış Tarihi")
ensure_field(O, "opportunity", "expectedCloseQuarter", "TEXT", "Beklenen Kapanış Çeyreği", **RO)
ensure_field(O, "opportunity", "realCloseDate", "DATE", "Gerçek Kapanış Tarihi", **RO)

# --- Fırsat: gelir (mevcut alanlar 01'de) ve toplam değer ---
# Standart alan: Twenty salt okunur ayarını kabul etmiyor; motor elle girilen değerin üstüne yazar.
ensure_field(O, "opportunity", "amount", "CURRENCY", "Toplam Değer (TCV)")

# --- Fırsat: maliyet ve gross profit ---
for name, label in [("oneTimeCost", "Tek Seferlik Maliyet"), ("monthlyCost", "Aylık Maliyet"),
                    ("annualCost", "Yıllık Maliyet")]:
    ensure_field(O, "opportunity", name, "CURRENCY", label)
ensure_field(O, "opportunity", "totalCost", "CURRENCY", "Toplam Maliyet", **RO)
ensure_field(O, "opportunity", "grossProfit", "CURRENCY", "Gross Profit", **RO)
ensure_field(O, "opportunity", "grossMarginPercent", "NUMBER", "Gross Margin %", **RO)

# --- Fırsat: raporlama para biriminde ---
ensure_field(O, "opportunity", "amountReporting", "CURRENCY", "Toplam Değer (Raporlama)", **RO)
ensure_field(O, "opportunity", "grossProfitReporting", "CURRENCY", "Gross Profit (Raporlama)", **RO)
ensure_field(O, "opportunity", "fxRateDate", "DATE", "Kur Tarihi", **RO)

# --- Ayarlar: raporlama para birimi (tek kayıt) ---
CURRENCIES = [("TRY", "TRY", "red"), ("EUR", "EUR", "blue"), ("USD", "USD", "green"), ("GBP", "GBP", "purple")]
O = ensure_object(O, "crmSetting", "crmSettings", "CRM Ayarı", "CRM Ayarları", "IconSettings",
                  "Çalışma alanı ayarları (tek kayıt): raporlama para birimi.")
ensure_field(O, "crmSetting", "reportingCurrency", "SELECT", "Raporlama Para Birimi", CURRENCIES)

# --- Döviz kuru (TCMB, günlük) ---
O = ensure_object(O, "exchangeRate", "exchangeRates", "Döviz Kuru", "Döviz Kurları", "IconCurrencyLira",
                  "TCMB günlük kurları; sistem doldurur.")
ensure_field(O, "exchangeRate", "rateDate", "DATE", "Kur Tarihi", **RO)
ensure_field(O, "exchangeRate", "foreignCurrency", "SELECT", "Para Birimi",
             [c for c in CURRENCIES if c[0] != "TRY"], **RO)
ensure_field(O, "exchangeRate", "rateTry", "NUMBER", "TRY Karşılığı",
             settings={"type": "number", "decimals": 4}, **RO)

# --- Aşama geçmişi ---
STAGE_OPTS = [(o["value"], o["label"], o["color"])
              for o in sorted(O["opportunity"]["fields"]["stage"]["options"], key=lambda o: o["position"])]
O = ensure_object(O, "stageChange", "stageChanges", "Aşama Değişikliği", "Aşama Geçmişi", "IconTimelineEvent",
                  "Fırsat aşama değişiklikleri; sistem yazar.")
ensure_relation(O, "stageChange", "opportunity", "Fırsat", "opportunity", "Aşama Geçmişi",
                "IconTargetArrow", "IconTimelineEvent", "stageChanges")
ensure_relation(O, "stageChange", "changedBy", "Değiştiren", "workspaceMember", "Aşama Değişiklikleri",
                "IconUserCircle", "IconTimelineEvent", "stageChanges")
ensure_field(O, "stageChange", "fromStage", "SELECT", "Önceki Aşama", STAGE_OPTS, plural="stageChanges", **RO)
ensure_field(O, "stageChange", "toStage", "SELECT", "Yeni Aşama", STAGE_OPTS, plural="stageChanges", **RO)
ensure_field(O, "stageChange", "changedAt", "DATE_TIME", "Tarih", **RO)

# --- Sözleşme: fırsattan dönüşürken maliyet ve gross profit de taşınır ---
for name, label in [("oneTimeCost", "Tek Seferlik Maliyet"), ("monthlyCost", "Aylık Maliyet"),
                    ("annualCost", "Yıllık Maliyet"), ("totalCost", "Toplam Maliyet"),
                    ("grossProfit", "Gross Profit")]:
    ensure_field(O, "contract", name, "CURRENCY", label)

# --- Audit / Delivery / Invoice dönemi: paralel durumlar (kullanıcı, 11 Kas) ---
# Üçü tamamlanınca motor aşamayı Won yapar.
ensure_field(O, "opportunity", "contractStatus", "SELECT", "Sözleşme Durumu",
             [("SIGNING", "İmzada", "yellow"), ("SIGNED", "İmzalandı", "green")])
PROGRESS = [("NOT_STARTED", "Başlamadı", "gray"), ("IN_PROGRESS", "Devam ediyor", "blue"),
            ("DONE", "Tamamlandı", "green")]
ensure_field(O, "opportunity", "deliveryStatus", "SELECT", "Teslimat Durumu", PROGRESS)
ensure_field(O, "opportunity", "invoicingStatus", "SELECT", "Faturalama Durumu", PROGRESS)
