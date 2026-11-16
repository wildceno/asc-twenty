#!/usr/bin/env python3
"""CRM Ayarı → Açık Paketler (7c, kullanıcı kararı 13 Kas 2026: tek servis, ayrı paketler, müşteri bazında aç/kapat).

Hesap motoru bu alanı okur; boş bırakılırsa bütün paketler açıktır (varsayılan). Çekirdek (kur, ayar, dönemler)
her zaman açıktır. Paketler: motor/ascendia_motor/paketler/. Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, load_objects  # noqa: E402

PAKETLER = [("SATIS_SURECI", "Satış süreci ve hesaplar", "blue"), ("HEDEFLER", "Hedefler ve forecast", "green"),
            ("TAKIP", "Takip kuralları", "orange"), ("SAGLIK", "Sistem sağlığı", "red"),
            ("TEKLIF", "Teklif ve katalog", "purple"), ("EPOSTA", "E-posta temas ve cevap görevi", "sky"),
            ("IMZA", "DocuSign e-imza", "turquoise"), ("FATURA", "Paraşüt fatura", "yellow")]
O = load_objects()
ensure_field(O, "crmSetting", "activeModules", "MULTI_SELECT", "Açık Paketler", PAKETLER)
