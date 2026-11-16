#!/usr/bin/env python3
"""Ascendia şablonu: ekip yapısı (yönetici ve support atamaları).

Kullanıcı kararları (11 Kas 2026):
- Kişiye yönetici atanabilir; support rolündeki kişiye destek verdiği kişiler atanabilir.
- Yöneticilere satıcılar gibi hedef girilebilir; support'un şimdilik hedefi yok.
Çalışma alanı kullanıcısına (workspaceMember) arayüzden alan eklenemediği için ayrı "Ekip" nesnesi:
her çalışan için bir kayıt (Çalışan, Görev, Yönetici, Support).
Kullanıcı (11 Kas): herkesin gerçekleşeni Fırsat Sahibi olduğu fırsatlardan; yöneticininki kendisine bağlı
kişilerin (varsayım: dolaylı bağlılar dahil) sahibi olduğu fırsatlardan, kendi fırsatları hariç.
Idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, ensure_object, ensure_relation, load_objects  # noqa: E402

O = load_objects()
WM = "workspaceMember"

O = ensure_object(O, "teamMember", "teamMembers", "Ekip Üyesi", "Ekip", "IconUsersGroup",
                  "Çalışan başına bir kayıt: görev, yönetici, support.")
ensure_relation(O, "teamMember", "member", "Çalışan", WM, "Ekip Kaydı", "IconUserCircle", "IconUsersGroup",
                "teamRecords")
ensure_relation(O, "teamMember", "manager", "Yönetici", WM, "Yönettiği Kişiler", "IconUserStar", "IconUsersGroup",
                "managedMembers")
ensure_relation(O, "teamMember", "support", "Support", WM, "Destek Verdiği Kişiler", "IconLifebuoy",
                "IconUsersGroup", "supportedMembers")
ensure_field(O, "teamMember", "jobFunction", "SELECT", "Görev",   # "position" sistem alanı
             [("SALES", "Satış", "blue"), ("MANAGER", "Yönetici", "purple"), ("SUPPORT", "Support", "turquoise"),
              ("MARKETING", "Pazarlama", "orange")])

# Hedef türü: kişisel ya da yönetici (ekip)
TARGET_ROLES = [("PERSONAL", "Kişisel", "blue"), ("MANAGER", "Yönetici (ekip)", "purple")]
ensure_field(O, "target", "targetRole", "SELECT", "Rol", TARGET_ROLES, plural="targets")
