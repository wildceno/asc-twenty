#!/usr/bin/env python3
"""Ascendia şablonu: Audit'e geçiş belgeleri ve sözleşme belgeleri.

Kullanıcı kararları (11 Kas 2026):
- Commit'ten Audit'e geçerken Sipariş/Onay Dokümanı ve Onaylanan Teklif eklenmeli; bu dosyalar sözleşmeye de gider.
- Bir sözleşmenin altında birden fazla belge olabilir: ana sözleşme, NDA, çerçeve, tedarikçiyle ek sözleşme vb.
Motor kurallara uymayan değişikliği geri aldığında nedenini fırsattaki Sistem Uyarısı alanına yazar.
Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, ensure_relation, load_objects, remove_field  # noqa: E402

O = load_objects()
DOSYA = {"maxNumberOfValues": 10}

ensure_field(O, "opportunity", "orderDocument", "FILES", "Sipariş / Onay Dokümanı", settings=DOSYA)
ensure_field(O, "opportunity", "approvedProposal", "FILES", "Onaylanan Teklif", settings=DOSYA)
ensure_field(O, "opportunity", "systemWarning", "TEXT", "Sistem Uyarısı", read_only=True)

O = ensure_object(O, "contractDocument", "contractDocuments", "Sözleşme Belgesi", "Sözleşme Belgeleri",
                  "IconFileText", "Bir sözleşmenin altındaki belgeler: ana sözleşme, NDA, çerçeve, tedarikçi sözleşmesi vb.")
ensure_relation(O, "contractDocument", "contract", "Sözleşme", "contract", "Belgeler",
                "IconFileCertificate", "IconFileText", "documents")
ensure_relation(O, "contractDocument", "partner", "İş Ortağı / Tedarikçi", "partner", "Sözleşme Belgeleri",
                "IconHeartHandshake", "IconFileText", "contractDocuments")
DOC_TYPES = [("MAIN", "Ana sözleşme", "green"), ("NDA", "NDA", "gray"), ("FRAMEWORK", "Çerçeve sözleşme", "blue"),
             ("ORDER", "Sipariş / Onay", "orange"), ("APPROVED_PROPOSAL", "Onaylanan teklif", "yellow"),
             ("SUPPLIER", "Tedarikçi sözleşmesi", "purple"), ("ADDENDUM", "Ek protokol", "sky"),
             ("OTHER", "Diğer", "gray")]
ensure_field(O, "contractDocument", "documentType", "SELECT", "Belge Türü", DOC_TYPES)
ensure_field(O, "contractDocument", "signedDate", "DATE", "İmza Tarihi")
ensure_field(O, "contractDocument", "validUntil", "DATE", "Geçerlilik Bitişi")
ensure_field(O, "contractDocument", "file", "FILES", "Dosya", settings=DOSYA)

# Sözleşmedeki tek dosya alanı yerine Belgeler listesi (boşsa kaldırılır)
if "document" in O["contract"]["fields"]:
    remove_field(O, "contract", "contracts", "document")
