#!/usr/bin/env python3
"""Teklif Şablonu kayıt sayfasına "Şablon" sekmesi ve Şablon Düzenleyici widget'ı (liste 15a).
Önce: apps/ascendia-pano → twenty app apply. Ayrıntı: twenty.kayit_sekmesi. Idempotent."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import kayit_sekmesi, load_objects  # noqa: E402

kayit_sekmesi(load_objects(), "quoteTemplate", "Şablon", "Şablon Düzenleyici")
