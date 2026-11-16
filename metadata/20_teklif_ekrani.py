#!/usr/bin/env python3
"""Teklif kayıt sayfasına "Teklif" sekmesi ve Teklif Ekranı widget'ı (liste 14b). Önce: apps/ascendia-pano → twenty app apply.
Ayrıntı: twenty.kayit_sekmesi (sekme en başta, ilk sekme sabitlemesi kapalı). Idempotent."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import kayit_sekmesi, load_objects  # noqa: E402

kayit_sekmesi(load_objects(), "quote", "Teklif", "Teklif Ekranı")
