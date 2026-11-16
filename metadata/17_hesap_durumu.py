#!/usr/bin/env python3
"""Şirket → Hesap Durumu (liste 12b, kullanıcı kararı 13 Kas 2026). Hesap motoru doldurur, arayüzde salt okunur.

Müşteri: en az bir Aktif ve bitiş tarihi geçmemiş sözleşme. Eski müşteri: sözleşmesi var, hiçbiri aktif ya da imzada
değil. Aday: hiç sözleşme yok ya da yalnız imzada bekleyen var (varsayım, kullanıcıya bildirildi). Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, load_objects  # noqa: E402

DURUMLAR = [("PROSPECT", "Aday", "gray"), ("CUSTOMER", "Müşteri", "green"), ("FORMER", "Eski müşteri", "orange")]
O = load_objects()
ensure_field(O, "company", "accountStatus", "SELECT", "Hesap Durumu", DURUMLAR, read_only=True)
