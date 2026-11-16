#!/usr/bin/env python3
"""E-posta temas ve cevap görevi (liste 19; kullanıcı kararları 14 Kas 2026).

Eşitlenen her posta (gelen ve giden) bir Temas olur; gelen postada konuşma başına tek "Cevapla" görevi açılır, cevap
gidince kapanır ve cevap süresi (saat) gelen postanın Temas'ına yazılır (süre ölçülür, hedef konmaz). Posta kutusunun
sahibi katılımcıdan bulunur; Twenty'nin eşleştiremediği adres (ör. kişisel deneme kutusu) Ekip → Eşitlenen Posta
Adresleri ile üyeye bağlanır. Hesap motoru EPOSTA paketi yazar. Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, load_objects  # noqa: E402

O = load_objects()
for name, typ, label in [("emailMessageId", "TEXT", "E-posta (sistem)"), ("emailThreadId", "TEXT", "E-posta Konuşması (sistem)"),
                         ("responseHours", "NUMBER", "Cevap Süresi (saat)"),
                         ("calendarEventId", "TEXT", "Takvim Etkinliği (sistem)")]:
    ensure_field(O, "touchpoint", name, typ, label, read_only=True)
ensure_field(O, "task", "emailThreadId", "TEXT", "E-posta Konuşması (sistem)", read_only=True)
ensure_field(O, "teamMember", "mailboxEmails", "TEXT", "Eşitlenen Posta Adresleri (virgülle)")
