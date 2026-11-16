#!/usr/bin/env python3
"""Teklif belgesi (liste 15b; plan: kararlar/2026-11-13-teklif-modulu-plan.md).

Teklifte: belge bölüm seçimi (kaldırılabilir bölümler çıkarılır), teklifte doldurulan alanlar, belge isteği (Belge
sekmesindeki düğme yazar; hesap motoru üretip temizler), üretilen belgeler ve durum. Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, load_objects  # noqa: E402

O = load_objects()
for name, typ, label, opts, ro, ayar in [
    ("documentSections", "RAW_JSON", "Belge Bölümleri", None, False, None),
    ("fillValues", "RAW_JSON", "Doldurulan Alanlar", None, False, None),
    ("documentRequest", "SELECT", "Belge İsteği", [("NATIVE", "Word / PowerPoint", "blue"), ("PDF", "PDF", "red"),
                                                   ("BOTH", "Word / PowerPoint + PDF", "purple")], False, None),
    ("documentStatus", "TEXT", "Belge Durumu", None, True, None),
    ("documentAt", "DATE_TIME", "Belge Üretimi", None, True, None),
    # Son üretilen belge (ve PDF'i); yeni üretim öncekilerin yerini alır (revizyon yeni teklif kaydıdır)
    ("documents", "FILES", "Belgeler", None, True, {"maxNumberOfValues": 4}),
]:
    ensure_field(O, "quote", name, typ, label, opts, settings=ayar, read_only=ro)
