#!/usr/bin/env python3
"""Teklif şablonları (liste 15a; plan: kararlar/2026-11-13-teklif-modulu-plan.md, 15a kararları).

Teklif Şablonu: şirketin Word / PowerPoint dosyası. Belge servisi dosyayı okur; hesap motoru bölümleri (Şablon Bölümü)
ve yer tutucuları yazar. Bölüm türü (Sabit / Teklifte doldurulur / Otomatik) kullanıcı tarafından düzeltilebilir;
dosya yeniden yüklenince aynı adlı bölümlerin seçimi korunur, dosyadan çıkan bölüm silinir. Teklifte şablon seçilir (boşsa varsayılan aktif şablon).
Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, ensure_relation, load_objects  # noqa: E402

O = load_objects()
O = ensure_object(O, "quoteTemplate", "quoteTemplates", "Teklif Şablonu", "Teklif Şablonları", "IconTemplate",
                  "Şirketin Word / PowerPoint teklif şablonu: bölümler ve {{yer_tutucu}} işaretleri dosyadan okunur.")
for name, typ, label, opts, ro in [
    ("status", "SELECT", "Durum", [("DRAFT", "Taslak", "gray"), ("ACTIVE", "Aktif", "green"), ("PASSIVE", "Pasif", "red")], False),
    ("isDefault", "BOOLEAN", "Varsayılan", None, False),
    ("description", "TEXT", "Açıklama", None, False),
    ("format", "SELECT", "Biçim", [("DOCX", "Word", "blue"), ("PPTX", "PowerPoint", "orange")], True),
    ("readFileId", "TEXT", "Okunan Dosya (sistem)", None, True),
    ("readAt", "DATE_TIME", "Okunma Zamanı", None, True),
    ("readWarnings", "TEXT", "Okuma Uyarıları", None, True),
    ("placeholders", "RAW_JSON", "Yer Tutucular", None, True),
]:
    ensure_field(O, "quoteTemplate", name, typ, label, opts, read_only=ro)

# Tek dosya: bir şablon bir Word ya da PowerPoint dosyasıdır (birden fazlası yüklenirse yalnız ilki okunur, uyarı)
ensure_field(O, "quoteTemplate", "templateFile", "FILES", "Şablon Dosyası", settings={"maxNumberOfValues": 1})

O = ensure_object(O, "templateSection", "templateSections", "Şablon Bölümü", "Şablon Bölümleri", "IconLayoutList",
                  "Şablonun bölümleri: sabit metin, teklifte doldurulan ya da tekliften otomatik gelen.")
ensure_relation(O, "templateSection", "quoteTemplate", "Şablon", "quoteTemplate", "Bölümler", "IconTemplate",
                "IconLayoutList", "sections")
for name, typ, label, opts, ro in [
    ("sortOrder", "NUMBER", "Sıra", None, True),
    ("sectionType", "SELECT", "Tür", [("FIXED", "Sabit", "gray"), ("FILL", "Teklifte doldurulur", "orange"),
                                      ("AUTO", "Otomatik (tekliften)", "green")], False),
    ("autoContent", "SELECT", "Otomatik İçerik", [("LINE_TABLE", "Kalem tablosu", "blue"),
                                                  ("PRODUCT_DESCRIPTIONS", "Ürün açıklamaları", "purple")], False),
    ("removable", "BOOLEAN", "Teklifte Kaldırılabilir", None, False),
    ("defaultText", "TEXT", "Varsayılan Metin (doldurulan bölüm)", None, False),
    ("sourceRef", "TEXT", "Dosyadaki Yeri", None, True),
    ("textPreview", "TEXT", "Metin Önizleme", None, True),
    ("placeholders", "RAW_JSON", "Yer Tutucular", None, True),
]:
    ensure_field(O, "templateSection", name, typ, label, opts, read_only=ro)

ensure_relation(O, "quote", "quoteTemplate", "Şablon", "quoteTemplate", "Teklifler", "IconTemplate", "IconFileInvoice",
                "quotes")
