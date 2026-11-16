#!/usr/bin/env python3
"""DocuSign e-imza (liste 20; kullanıcı kararları 14 Kas 2026).

Teklifte İmzalayacak Kişi seçilir; Belge sekmesi "imzaya gönder" isteği yazar, hesap motoru (IMZA paketi) teklifin PDF'ini
DocuSign zarfı olarak gönderir. Durum 00:00, 08:00, 16:00'da (ve istenince hemen) DocuSign'dan sorulur: Monster dışarıya
kapalı olduğu için DocuSign bildirim gönderemez. İmzalanınca teklif Kabul, imzalı PDF teklife ve fırsatın Onaylanan Teklif
alanına; reddedilince Red. Karşı imza yok. İmza yeri şablondaki {{imza}}; yoksa imzalayan kendisi yerleştirir. Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_relation, load_objects  # noqa: E402

O = load_objects()
ensure_relation(O, "quote", "signer", "İmzalayacak Kişi", "person", "İmzalayacağı Teklifler", "IconSignature", "IconFileInvoice",
                "quotesToSign")
for name, typ, label, opts, ro in [
    ("esignRequest", "SELECT", "İmza İsteği", [("SEND", "İmzaya gönder", "blue"), ("CHECK", "Durumu kontrol et", "gray")], False),
    ("esignStatus", "SELECT", "İmza Durumu", [("SENT", "İmzaya gönderildi", "blue"), ("DELIVERED", "Görüldü", "sky"),
                                              ("COMPLETED", "İmzalandı", "green"), ("DECLINED", "Reddedildi", "red"),
                                              ("VOIDED", "İptal edildi", "gray"), ("ERROR", "Hata", "orange")], True),
    ("esignEnvelopeId", "TEXT", "DocuSign Zarfı (sistem)", None, True),
    ("esignSentAt", "DATE_TIME", "İmzaya Gönderim", None, True),
    ("esignCheckedAt", "DATE_TIME", "İmza Durumu Kontrolü", None, True),
    ("esignMessage", "TEXT", "İmza Mesajı", None, True),
]:
    ensure_field(O, "quote", name, typ, label, opts, read_only=ro)
