"""Ortam değişkenleri ve sabitler (aşama kümeleri, kilitli alanlar)."""
import datetime as dt
import os


API = os.environ.get("TWENTY_API_URL", "http://server:3000").rstrip("/")


KEY_FILE = os.environ.get("TWENTY_KEY_FILE", "/run/secrets/twenty_api_key")


SECRET_FILE = os.environ.get("WEBHOOK_SECRET_FILE", "/run/secrets/webhook_secret")


PORT = int(os.environ.get("PORT", "8080"))


KUR_SAATI = os.environ.get("KUR_SAATI", "16:05")


TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"


TR = dt.timezone(dt.timedelta(hours=3))


OPEN = {"LEAD_GEN", "LEAD_IN_TOUCH", "PIPELINE", "UPSIDE", "COMMIT"}


DELIVERY_PHASE = {"AUDIT", "DELIVERY", "INVOICE"}


LOCKED = {"WON", "LOST", "DISQUALIFIED"}


CLOSED = DELIVERY_PHASE | LOCKED


# Kapanan fırsatta değişmeyen alanlar (kullanıcı, 11 Kas): teklif, maliyet ve forecast değerleri
LOCK_FIELDS = ["oneTimeFee", "monthlyRecurring", "annualRecurring", "contractMonths", "oneTimeCost", "monthlyCost",
               "annualCost", "amount", "totalCost", "grossProfit", "grossMarginPercent", "amountReporting",
               "grossProfitReporting", "fxRateDate", "closeDate", "expectedCloseQuarter",
               "mrr", "arr", "mrrReporting", "arrReporting"]


ETIKET = {"WON": "Won", "LOST": "Lost", "DISQUALIFIED": "DSQ", "AUDIT": "Audit", "DELIVERY": "Delivery",
          "INVOICE": "Invoice", "COMMIT": "Commit"}


AY_ADLARI = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
