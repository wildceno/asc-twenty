#!/usr/bin/env python3
"""Ascendia şablonu: menü sırası, açılış ekranı ve kanban sütunları.

Kullanıcı isteği (11 Kas 2026):
- Giriş yapınca ilk dashboard açılsın, menüde Dashboard en üstte olsun.
  Twenty açılışta menüdeki ilk öğenin bağlantısını açar (twenty-front
  getFirstNavigationMenuItemLink); bu yüzden ilk dashboard kaydını açan bir öğe en üste konur.
- Fırsatlar "By Stage" kanbanında her aşama bir sütun olsun (aşama listesi
  değiştiğinde sütunlar kaybolmuştu).
Idempotent: iki kez çalışınca değişiklik yapmaz.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import KEY_FILE, URL, gql, load_objects  # noqa: E402

O = load_objects()
ID2NAME = {v["id"]: k for k, v in O.items()}


def rest(path, method="GET", body=None):
    with open(KEY_FILE) as fh:
        token = fh.read().strip()
    req = urllib.request.Request(URL[: -len("/metadata")] + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["data"]


def rest_get(path):
    return rest(path)


# --- Kanban: aşamaya göre fırsatlar ---
# Twenty aşama seçenekleri değişince bu görünümü tabloya çevirip sütunlarını siliyor
# (11 Kas 2026, v2.57.1). Aşama listesi her değiştiğinde bu betik yeniden çalıştırılır.
KANBAN_NAME = "By Stage"


def stage_kanban():
    opp = O["opportunity"]
    stage_id, amount_id = opp["fields"]["stage"]["id"], opp["fields"]["amount"]["id"]
    views = gql("query($o: String) { getViews(objectMetadataId: $o) { id name type mainGroupByFieldMetadataId "
                "kanbanAggregateOperation kanbanAggregateOperationFieldMetadataId } }", {"o": opp["id"]})["getViews"]
    v = next((x for x in views if x["name"] == KANBAN_NAME), None)
    if not v:
        raise SystemExit(f"'{KANBAN_NAME}' görünümü yok: elle incele")
    want = {"type": "KANBAN", "mainGroupByFieldMetadataId": stage_id,
            "kanbanAggregateOperation": "SUM", "kanbanAggregateOperationFieldMetadataId": amount_id}
    diff = {k: val for k, val in want.items() if v.get(k) != val}
    if diff:
        gql("mutation($id: String!, $i: UpdateViewInput!) { updateView(id: $id, input: $i) { id } }",
            {"id": v["id"], "i": diff})
        print("kanban görünümü düzeltildi:", ", ".join(diff))
    values = [o["value"] for o in sorted(opp["fields"]["stage"]["options"], key=lambda o: o["position"])]
    groups = gql("query($v: String!) { getViewGroups(viewId: $v) { id fieldValue } }", {"v": v["id"]})["getViewGroups"]
    have = {g["fieldValue"] for g in groups}
    missing = [{"viewId": v["id"], "fieldValue": val, "isVisible": True, "position": i}
               for i, val in enumerate(values) if val not in have]
    if missing:
        gql("mutation($i: [CreateViewGroupInput!]!) { createManyViewGroups(inputs: $i) { id } }", {"i": missing})
        print("kanban sütunu eklendi:", ", ".join(m["fieldValue"] for m in missing))
    # Sütun sırası aşama sırasıyla aynı olsun (Twenty yeni değerleri sona ekliyor)
    groups = gql("query($v: String!) { getViewGroups(viewId: $v) { id fieldValue position } }",
                 {"v": v["id"]})["getViewGroups"]
    order = {val: i for i, val in enumerate(values)}
    moves = [{"id": g["id"], "update": {"position": order[g["fieldValue"]]}}
             for g in groups if g["fieldValue"] in order and g["position"] != order[g["fieldValue"]]]
    if moves:
        gql("mutation($i: [UpdateViewGroupInput!]!) { updateManyViewGroups(inputs: $i) { id } }", {"i": moves})
        print("kanban sütun sırası düzeltildi")
    if not diff and not missing and not moves:
        print("değişiklik yok: kanban", KANBAN_NAME)


stage_kanban()

# --- Menü ---
ITEMS_Q = ("{ navigationMenuItems { id position type name icon targetObjectMetadataId targetRecordId folderId "
           "userWorkspaceId } }")


def menu():
    return [i for i in gql(ITEMS_Q)["navigationMenuItems"] if not i["userWorkspaceId"]]


items = menu()
dashboards = sorted(rest_get("/rest/dashboards?limit=60")["dashboards"], key=lambda d: d["position"])
if not dashboards:
    raise SystemExit("Dashboard kaydı yok: önce arayüzden bir dashboard oluştur")
first = dashboards[0]
DASHBOARD_TITLE = "Dashboard"  # kullanıcı, 11 Kas
if first["title"] != DASHBOARD_TITLE:
    rest(f"/rest/dashboards/{first['id']}", "PATCH", {"title": DASHBOARD_TITLE})
    print("dashboard adı:", first["title"], "→", DASHBOARD_TITLE)
if not any(i["type"] == "RECORD" and i["targetRecordId"] == first["id"] for i in items):
    gql("mutation($i: CreateNavigationMenuItemInput!) { createNavigationMenuItem(input: $i) { id } }",
        {"i": {"type": "RECORD", "targetObjectMetadataId": O["dashboard"]["id"], "targetRecordId": first["id"],
               "position": -1}})
    print("menü öğesi eklendi: dashboard", first["title"])
    items = menu()
rec = next(i for i in items if i["type"] == "RECORD" and i["targetRecordId"] == first["id"])
if rec.get("icon") != "IconLayoutDashboard":
    gql("mutation($i: UpdateOneNavigationMenuItemInput!) { updateNavigationMenuItem(input: $i) { id } }",
        {"i": {"id": rec["id"], "update": {"icon": "IconLayoutDashboard"}}})
    print("dashboard menü simgesi ayarlandı")

# Klasörler (kullanıcı, 11 Kas): müşteriyle yaşananlar tek yerde
FOLDERS = {"Aktiviteler": ["touchpoint", "note", "task"],
           # Sistem ve ayar kayıtları; alt kayıtlar (hedef kalemi, sözleşme belgesi) üst kaydın sayfasından da açılır
           # Kullanıcı, 11 Kas: İş akışları ve Hedefler Yönetim altında (Workflows klasörü iç içe)
           "Yönetim": ["target", "teamMember", "forecastRate", "followUpRule", "marginRule", "quoteTemplate", "inflationForecast", "systemAlarm", "systemStatus", "Workflows", "crmSetting", "reportingPeriod",
                       "exchangeRate", "stageChange", "targetLine", "contractDocument", "quoteLine", "templateSection"]}
for fname in FOLDERS:
    if not any(i["type"] == "FOLDER" and i["name"] == fname for i in items):
        gql("mutation($i: CreateNavigationMenuItemInput!) { createNavigationMenuItem(input: $i) { id } }",
            {"i": {"type": "FOLDER", "name": fname, "position": 99,
                   "icon": {"Aktiviteler": "IconActivity", "Yönetim": "IconSettings"}.get(fname, "IconFolder")}})
        print("klasör eklendi:", fname)
        items = menu()
folder_id = {i["name"]: i["id"] for i in items if i["type"] == "FOLDER"}

# Üst seviye sıra; listede olmayanlar sona, mevcut sıralarıyla
# Kullanıcı, 11 Kas: Dashboard, Fırsatlar, Aktiviteler, Sözleşmeler, Şirketler, Kişiler, İş Ortakları,
# Rakip Hizmetleri, sonra diğerleri
ORDER = ["dashboard-record", "opportunity", "quote", "Aktiviteler", "contract", "company", "person", "partner",
         "competitorService", "catalogItem", "dashboard", "Campaigns", "Yönetim"]   # 13 Kas: Teklifler, Katalog


def key(i):
    if i["type"] == "RECORD" and i["targetRecordId"] == first["id"]:
        return "dashboard-record"
    if i["type"] == "FOLDER":
        return i["name"]
    return ID2NAME.get(i["targetObjectMetadataId"])


# İstenen klasör ve sıra: {öğe id: (klasör id ya da None, sıra)}
want = {}
in_folder = {obj: fname for fname, objs in FOLDERS.items() for obj in objs}
for fname, objs in FOLDERS.items():
    for n, obj in enumerate(objs):
        for i in items:
            if i["type"] in ("OBJECT", "FOLDER") and key(i) == obj and i["id"] != folder_id[fname]:
                want[i["id"]] = (folder_id[fname], n)
top = [i for i in items if not i["folderId"] and i["id"] not in want]
top.sort(key=lambda i: (ORDER.index(key(i)) if key(i) in ORDER else len(ORDER), i["position"]))
for n, i in enumerate(top):
    want[i["id"]] = (None, n)

updates = []
for i in items:
    if i["id"] not in want:
        continue
    fid, pos = want[i["id"]]
    u = {}
    if i["folderId"] != fid:
        u["folderId"] = fid
    if i["position"] != pos:
        u["position"] = pos
    if u:
        updates.append({"id": i["id"], "update": u})
if updates:
    gql("mutation($i: [UpdateOneNavigationMenuItemInput!]!) { updateManyNavigationMenuItems(inputs: $i) { id } }",
        {"i": updates})
    print("menü güncellendi:", " > ".join(str(key(i)) for i in top), "|",
          ", ".join(f"{f}: {'/'.join(o)}" for f, o in FOLDERS.items()))
else:
    print("değişiklik yok: menü")
