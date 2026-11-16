#!/usr/bin/env python3
"""Ascendia şablonu: roller, nesne ve alan yetkileri, kişisel görünümler (lisanssız kısım).

Kullanıcı kararları (11 Kas 2026):
- Yönetim ve altındakiler yalnız admin ve super-user tarafından görülür.
- Super-user: firmanın yetkili personeli; admin olmasa da güçlü yetkiler.
- Şirket ve fırsat sahiplikleri (Account Manager, hunter sales/SDR, BDM, Pre-sales) yalnız super-user'ca değiştirilir.
- 13 Kas: Satış, Yönetici, Support hedefleri, raporlama dönemlerini ve CRM ayarını yalnız okur (pano için).
- Olmayan müşteriyi BDM ve satış rolleri oluşturabilir.
- "Herkes yalnız kendi alanını görür" Twenty'de satır düzeyi yetki ister (Organization key, ücretli);
  lisans alınmadı: yerine kişisel görünümler (güvenlik değil, kolaylık).
Varsayımlar (kullanıcıya bildirildi): Fırsat Sahibi de sahiplik alanı; super-user dışında silme yok;
Pazarlama şirket/fırsat/sözleşme açamaz (Support açar, kullanıcı 11 Kas); Twenty'de "oluşturma" ayrı yetki değil, düzenleme yetkisine dahil.
Idempotent.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import gql, load_objects  # noqa: E402

O = load_objects()

YONETIM = ["crmSetting", "reportingPeriod", "exchangeRate", "stageChange", "target", "targetLine", "teamMember",
           "forecastRate", "followUpRule", "systemStatus", "systemAlarm", "marginRule", "inflationForecast"]
IS_AKISI = ["workflow", "workflowRun", "workflowVersion"]
SAHIPLIK = {"company": ["accountManager", "preSales", "serviceManager"],
            "opportunity": ["owner", "bdm", "sdr", "accountManager", "preSales", "serviceManager"]}
# Kullanıcı (13 Kas): panodaki hedef ve CRM ayarı için satış rolleri bunları yalnız OKUR (düzenleyemez)
PANO_OKUMA = ["crmSetting", "reportingPeriod", "target", "targetLine", "forecastRate"]
# Teklif şablonları (14 Kas, liste 15a): satış rolleri teklifte şablon seçer, şablonu yalnız Super-user / Admin düzenler
SABLON = ["quoteTemplate", "templateSection"]
TICARI = ["company", "opportunity", "contract", "contractDocument", "partner", "competitorService", "quote", "quoteLine",
          "catalogItem"]

TEMEL = {"canUpdateAllSettings": False, "canReadAllObjectRecords": True, "canUpdateAllObjectRecords": True,
         "canSoftDeleteAllObjectRecords": False, "canDestroyAllObjectRecords": False, "canBeAssignedToUsers": True}
ROLLER = {
    "Super-user": {"description": "Firmanın yetkili personeli: tüm kayıtlar, Yönetim, sahiplik atamaları.",
                   "icon": "IconShieldStar", **TEMEL, "canSoftDeleteAllObjectRecords": True,
                   "_gizli": [], "_salt_okunur": [], "_sahiplik_kilitli": False,
                   "_bayraklar": ["WORKFLOWS", "VIEWS", "LAYOUTS", "IMPORT_CSV", "EXPORT_CSV"]},
    "Satış": {"description": "SDR, BDM, Account Manager: müşteri ve fırsat açar; sahiplikleri değiştiremez.",
              "icon": "IconBriefcase", **TEMEL, "_gizli": YONETIM + IS_AKISI, "_silebilir": ["quoteLine"], "_salt_okunur": PANO_OKUMA + SABLON,
              "_sahiplik_kilitli": True, "_bayraklar": []},
    "Yönetici": {"description": "Satış yöneticisi: ekibini izler; sahiplikleri super-user değiştirir.",
                 "icon": "IconUserStar", **TEMEL, "_gizli": YONETIM + IS_AKISI, "_silebilir": ["quoteLine"], "_salt_okunur": PANO_OKUMA + SABLON,
                 "_sahiplik_kilitli": True, "_bayraklar": []},
    # Kullanıcı (11 Kas): Support şirket, fırsat, sözleşme açar ve düzenler
    "Support": {"description": "Destek: şirket, fırsat, sözleşme açar ve düzenler; sahiplikleri değiştiremez.",
                "icon": "IconLifebuoy", **TEMEL, "_gizli": YONETIM + IS_AKISI, "_silebilir": ["quoteLine"], "_salt_okunur": PANO_OKUMA + SABLON,
                "_sahiplik_kilitli": True, "_bayraklar": []},
    # Kullanıcı (13 Kas, liste 18): Claude MCP bağlantısı için; yalnız API anahtarına atanır
    "Claude Asistan": {"description": "Claude (MCP) için: okur, oluşturur, günceller; silemez, ayar değiştiremez, e-posta göndermez.",
                       "icon": "IconRobot", **TEMEL, "canBeAssignedToUsers": False, "canBeAssignedToApiKeys": True,
                       "_gizli": [], "_salt_okunur": [], "_sahiplik_kilitli": False, "_bayraklar": []},
    "Pazarlama": {"description": "Pazarlama: kişi ve aktivite girer; şirket ve fırsat açamaz.",
                  "icon": "IconSpeakerphone", **TEMEL, "_gizli": YONETIM + IS_AKISI, "_salt_okunur": TICARI + SABLON,
                  "_sahiplik_kilitli": True, "_bayraklar": []},
}

ROL_Q = ("{ getRoles { id label description icon canUpdateAllSettings canReadAllObjectRecords canBeAssignedToApiKeys "
         "canUpdateAllObjectRecords canSoftDeleteAllObjectRecords canDestroyAllObjectRecords canBeAssignedToUsers "
         "permissionFlags { flag } objectPermissions { objectMetadataId canReadObjectRecords canUpdateObjectRecords "
         "canSoftDeleteObjectRecords canDestroyObjectRecords } fieldPermissions { fieldMetadataId canReadFieldValue "
         "canUpdateFieldValue } } }")


def roller():
    return {r["label"]: r for r in gql(ROL_Q)["getRoles"]}


mevcut = roller()
for ad, tanim in ROLLER.items():
    alanlar = {k: v for k, v in tanim.items() if not k.startswith("_")}
    if ad not in mevcut:
        gql("mutation($i: CreateRoleInput!) { createOneRole(createRoleInput: $i) { id } }", {"i": {"label": ad, **alanlar}})
        print("rol oluşturuldu:", ad)
        mevcut = roller()
    r = mevcut[ad]
    fark = {k: v for k, v in alanlar.items() if r.get(k) != v}
    if fark:
        gql("mutation($i: UpdateRoleInput!) { updateOneRole(updateRoleInput: $i) { id } }",
            {"i": {"id": r["id"], "update": fark}})
        print("rol güncellendi:", ad, ", ".join(fark))

    # İzin bayrakları
    istenen = sorted(tanim["_bayraklar"])
    if sorted(f["flag"] for f in r.get("permissionFlags") or []) != istenen:
        gql("mutation($i: UpsertPermissionFlagsInput!) { upsertPermissionFlags(upsertPermissionFlagsInput: $i) "
            "{ flag } }", {"i": {"roleId": r["id"], "permissionFlagKeys": istenen}})
        print("bayraklar:", ad, istenen)

    # Nesne yetkileri
    nesne_istenen = {}
    for n in tanim["_gizli"]:
        if n in O:
            nesne_istenen[O[n]["id"]] = {"canReadObjectRecords": False, "canUpdateObjectRecords": False,
                                         "canSoftDeleteObjectRecords": False, "canDestroyObjectRecords": False}
    for n in tanim["_salt_okunur"]:
        if n in O:
            nesne_istenen[O[n]["id"]] = {"canReadObjectRecords": True, "canUpdateObjectRecords": False,
                                         "canSoftDeleteObjectRecords": False, "canDestroyObjectRecords": False}
    # 13 Kas (liste 14b): satış rolleri teklif kalemini çöp kutusuna silebilir (teklif ekranındaki Sil)
    for n in tanim.get("_silebilir", []):
        if n in O:
            nesne_istenen[O[n]["id"]] = {"canReadObjectRecords": True, "canUpdateObjectRecords": True,
                                         "canSoftDeleteObjectRecords": True, "canDestroyObjectRecords": False}
    # upsertObjectPermissions rolün listesini gönderilenle DEĞİŞTİRİR (gönderilmeyen silinir): tam liste gönderilir.
    var = {p["objectMetadataId"]: p for p in r.get("objectPermissions") or []}
    tam = [{"objectMetadataId": oid, **v} for oid, v in nesne_istenen.items()]
    ayni_mi = set(var) == set(nesne_istenen) and all(
        var[oid].get(k) == val for oid, v in nesne_istenen.items() for k, val in v.items())
    if not ayni_mi:
        gql("mutation($i: UpsertObjectPermissionsInput!) { upsertObjectPermissions(upsertObjectPermissionsInput: $i)"
            " { objectMetadataId } }", {"i": {"roleId": r["id"], "objectPermissions": tam}})
        print("nesne yetkileri:", ad, len(tam))

    # Alan yetkileri: sahiplik alanları okunur, değiştirilemez
    if tanim["_sahiplik_kilitli"]:
        var_alan = {p["fieldMetadataId"]: p for p in r.get("fieldPermissions") or []}
        # Alan yetkisi yalnız kısıtlar (Twenty: ONLY_FIELD_RESTRICTION_ALLOWED); okuma rolden gelir.
        # Eksik varsa tam liste gönderilir (toplu işlem listeyi değiştiriyor olabilir).
        istenen_alan = [{"objectMetadataId": O[n]["id"], "fieldMetadataId": O[n]["fields"][a]["id"],
                         "canUpdateFieldValue": False} for n, alanlar_ in SAHIPLIK.items() for a in alanlar_]
        # Artık istenmeyen kısıt (şirket ve fırsat alanlarında) null ile kaldırılır (13 Kas: upsert listeyi değiştirmez;
        # canUpdateFieldValue = null kısıtı siler, doğrulandı). Karşı taraf alanlarını (workspaceMember.*) Twenty kendisi tutar.
        istenen_idler = {x["fieldMetadataId"] for x in istenen_alan}
        kapsam = {O[n]["fields"][a]["id"]: (n, a) for n in SAHIPLIK for a in O[n]["fields"]}
        fazla = [f for f, v in var_alan.items() if v.get("canUpdateFieldValue") is False and f in kapsam and f not in istenen_idler]
        if fazla:
            gql("mutation($i: UpsertFieldPermissionsInput!) { upsertFieldPermissions(upsertFieldPermissionsInput: $i)"
                " { fieldMetadataId } }", {"i": {"roleId": r["id"], "fieldPermissions": [
                    {"objectMetadataId": O[kapsam[f][0]]["id"], "fieldMetadataId": f, "canUpdateFieldValue": None} for f in fazla]}})
            print("alan kısıtı kaldırıldı:", ad, ", ".join(".".join(kapsam[f]) for f in fazla))
        if any(var_alan.get(x["fieldMetadataId"], {}).get("canUpdateFieldValue") is not False for x in istenen_alan):
            gql("mutation($i: UpsertFieldPermissionsInput!) { upsertFieldPermissions(upsertFieldPermissionsInput: $i)"
                " { fieldMetadataId } }", {"i": {"roleId": r["id"], "fieldPermissions": istenen_alan}})
            print("alan yetkileri:", ad, len(istenen_alan))

# --- Kişisel görünümler (herkese açık, filtre: giriş yapan kişi) ---
BEN = json.dumps({"isCurrentWorkspaceMemberSelected": True, "selectedRecordIds": []})
GORUNUMLER = [("opportunity", "Benim Fırsatlarım", "owner"), ("company", "Benim Şirketlerim", "accountManager"),
              ("touchpoint", "Benim Temaslarım", "performedBy")]
for nesne, ad, alan in GORUNUMLER:
    views = gql("query($o: String) { getViews(objectMetadataId: $o) { id name key type } }",
                {"o": O[nesne]["id"]})["getViews"]
    if any(v["name"] == ad for v in views):
        print("zaten var: görünüm", ad)
        continue
    kaynak = next((v for v in views if v["key"] == "INDEX"), None) or next(v for v in views if v["type"] == "TABLE")
    yeni = gql("mutation($i: CreateViewInput!) { createView(input: $i) { id } }",
               {"i": {"name": ad, "objectMetadataId": O[nesne]["id"], "type": "TABLE", "icon": "IconUser",
                      "visibility": "WORKSPACE", "position": 1}})["createView"]["id"]
    alanlar_ = gql("query($v: String!) { getViewFields(viewId: $v) { fieldMetadataId isVisible size position } }",
                   {"v": kaynak["id"]})["getViewFields"]
    if alanlar_:
        gql("mutation($i: [CreateViewFieldInput!]!) { createManyViewFields(inputs: $i) { id } }",
            {"i": [{"viewId": yeni, **f} for f in alanlar_]})
    gql("mutation($i: CreateViewFilterInput!) { createViewFilter(input: $i) { id } }",
        {"i": {"viewId": yeni, "fieldMetadataId": O[nesne]["fields"][alan]["id"], "operand": "IS", "value": BEN}})
    print("görünüm oluşturuldu:", ad)
