"""Twenty Metadata API için ortak yardımcılar.

Betikler sunucuda (Monster) çalışır: `python3 metadata/NN_konu.py`.
API anahtarı ~/twenty/.twenty-api-key dosyasından okunur; ekrana yazılmaz.
Adres TWENTY_URL ortam değişkeniyle değiştirilebilir (varsayılan localhost:3010).
"""
import json
import os
import urllib.parse
import urllib.request
import uuid

URL = os.environ.get("TWENTY_URL", "http://localhost:3010").rstrip("/") + "/metadata"
KEY_FILE = os.path.expanduser(os.environ.get("TWENTY_KEY_FILE", "~/twenty/.twenty-api-key"))

CREATE_FIELD = "mutation($f: CreateFieldInput!) { createOneField(input:{field:$f}) { id name } }"
UPDATE_FIELD = "mutation($id: UUID!, $u: UpdateFieldInput!) { updateOneField(input:{id:$id, update:$u}) { id name } }"


def gql(query, variables=None):
    with open(KEY_FILE) as fh:
        token = fh.read().strip()
    req = urllib.request.Request(
        URL, method="POST",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req).read())
    if data.get("errors"):
        raise SystemExit(json.dumps(data["errors"], ensure_ascii=False)[:800])
    return data["data"]


def load_objects():
    """nameSingular -> {id, fields: {name -> alan}}"""
    q = ("{ objects(paging:{first:200}) { edges { node { id nameSingular "
         "fields(paging:{first:500}) { edges { node { id name label type options defaultValue isUIReadOnly } } } } } } }")
    out = {}
    for e in gql(q)["objects"]["edges"]:
        n = e["node"]
        out[n["nameSingular"]] = {
            "id": n["id"],
            "fields": {f["node"]["name"]: f["node"] for f in n["fields"]["edges"]},
        }
    return out


def count_records(plural, field, value):
    """REST ile `field = value` olan kayıt sayısı (silinmiş kayıtlar hariç)."""
    with open(KEY_FILE) as fh:
        token = fh.read().strip()
    base = URL[: -len("/metadata")]
    q = urllib.parse.quote(f"{field}[eq]:{value}", safe=":")
    req = urllib.request.Request(f"{base}/rest/{plural}?limit=1&filter={q}",
                                 headers={"Authorization": "Bearer " + token})
    return json.loads(urllib.request.urlopen(req).read())["totalCount"]


def build_options(existing, wanted, removable=()):
    """İstenen [(value, label, color)] listesinden seçenek listesi kurar.

    Aynı değerdeki mevcut seçeneğin kimliği korunur. Kullanımdaki bir değer
    sessizce kaybolmasın diye, istenen listede olmayan mevcut değer `removable`
    içinde değilse durur. `removable` değerlerinin kullanılmadığını çağıran doğrular.
    """
    by_value = {o["value"]: o for o in (existing or [])}
    removed = set(by_value) - {v for v, _, _ in wanted} - set(removable)
    if removed:
        raise SystemExit("Seçenek kaldırılıyor, önce kayıtları say/taşı (onay gerekir): " + ", ".join(sorted(removed)))
    return [{"id": by_value.get(v, {}).get("id") or str(uuid.uuid4()),
             "value": v, "label": l, "color": c, "position": i}
            for i, (v, l, c) in enumerate(wanted)]


def same_options(a, b):
    key = lambda o: (o["value"], o["label"], o["color"], o["position"])
    return sorted(map(key, a or [])) == sorted(map(key, b or []))


def ensure_select(objects, obj, name, wanted, default=None, plural=None):
    """Var olan SELECT alanının seçeneklerini istenen hâle getirir; değişiklik yoksa dokunmaz.

    Listeden çıkan bir değer yalnız hiçbir kayıtta kullanılmıyorsa kaldırılır
    (sayım için `plural`, ör. "opportunities", verilmelidir).
    """
    field = objects[obj]["fields"][name]
    gone = {o["value"] for o in field["options"] or []} - {v for v, _, _ in wanted}
    removable = set()
    if gone and plural:
        for v in sorted(gone):
            n = count_records(plural, name, v)
            if n:
                raise SystemExit(f"{obj}.{name} = {v} olan {n} kayıt var: önce taşı (onay gerekir)")
            removable.add(v)
    opts = build_options(field["options"], wanted, removable)
    update = {}
    if not same_options(field["options"], opts):
        update["options"] = opts
    if default is not None and field["defaultValue"] != default:
        update["defaultValue"] = default
    if not update:
        print("değişiklik yok:", obj, name)
        return
    gql(UPDATE_FIELD, {"id": field["id"], "u": update})
    print("güncellendi:", obj, name, "(" + ", ".join(update) + ")")


def ensure_field(objects, obj, name, typ, label, options=None, settings=None, plural=None, read_only=False):
    """Alan yoksa oluşturur. Varsa tipini kontrol eder; SELECT ise seçenekleri eşitler."""
    field = objects[obj]["fields"].get(name)
    if field:
        if field["type"] != typ:
            raise SystemExit(f"{obj}.{name} tipi {field['type']}, beklenen {typ}: elle incele")
        if field["label"] != label:
            gql(UPDATE_FIELD, {"id": field["id"], "u": {"label": label}})
            print("etiket güncellendi:", obj, name)
        if read_only and not field.get("isUIReadOnly"):
            gql(UPDATE_FIELD, {"id": field["id"], "u": {"isUIReadOnly": True}})
            print("salt okunur yapıldı:", obj, name)
        if options:
            ensure_select(objects, obj, name, options, plural=plural)
        else:
            print("zaten var:", obj, name)
        return
    f = {"objectMetadataId": objects[obj]["id"], "type": typ, "name": name, "label": label}
    if options:
        f["options"] = build_options([], options)
    if settings:
        f["settings"] = settings
    if read_only:
        f["isUIReadOnly"] = True
    gql(CREATE_FIELD, {"f": f})
    print("oluşturuldu:", obj, name)


CREATE_OBJECT = "mutation($o: CreateObjectInput!) { createOneObject(input:{object:$o}) { id nameSingular } }"
DELETE_FIELD = "mutation($id: UUID!) { deleteOneField(input:{id:$id}) { id name } }"


def ensure_object(objects, singular, plural, label_s, label_p, icon, description=""):
    """Özel nesne yoksa oluşturur; `objects` sözlüğünü yeniler."""
    if singular in objects:
        print("zaten var: nesne", singular)
        return objects
    gql(CREATE_OBJECT, {"o": {"nameSingular": singular, "namePlural": plural, "labelSingular": label_s,
                              "labelPlural": label_p, "icon": icon, "description": description}})
    print("oluşturuldu: nesne", singular)
    return load_objects()


def ensure_relation(objects, obj, name, label, target, target_label, icon="IconLink", target_icon="IconLink",
                    target_name=None):
    """`obj` üzerinde `target`'a çoka-bir (MANY_TO_ONE) ilişki; karşı tarafta liste alanı oluşur.

    Twenty karşı alanın adını etiketten türetir (ör. "Temaslar" -> "temaslar");
    `target_name` verilirse karşı alan bu ada (İngilizce camelCase) çevrilir.
    """
    if name in objects[obj]["fields"]:
        print("zaten var:", obj, name)
    else:
        gql(CREATE_FIELD, {"f": {"objectMetadataId": objects[obj]["id"], "type": "RELATION", "name": name,
                                 "label": label, "icon": icon,
                                 "relationCreationPayload": {"type": "MANY_TO_ONE",
                                                             "targetObjectMetadataId": objects[target]["id"],
                                                             "targetFieldLabel": target_label,
                                                             "targetFieldIcon": target_icon}}})
        print("oluşturuldu: ilişki", obj, name, "→", target)
        objects.update(load_objects())
    if target_name and target_name not in objects[target]["fields"]:
        inverse = [f for f in objects[target]["fields"].values()
                   if f["type"] == "RELATION" and f["label"] == target_label]
        if len(inverse) != 1:
            raise SystemExit(f"{target} üzerinde '{target_label}' etiketli tek ters alan bulunamadı: elle incele")
        gql(UPDATE_FIELD, {"id": inverse[0]["id"], "u": {"name": target_name, "isLabelSyncedWithName": False}})
        print("ters alan adı:", target, inverse[0]["name"], "→", target_name)
        objects.update(load_objects())


def count_filled(plural, field):
    """`field` alanı dolu olan kayıt sayısı (REST `[is]:NOT_NULL`)."""
    with open(KEY_FILE) as fh:
        token = fh.read().strip()
    base = URL[: -len("/metadata")]
    q = urllib.parse.quote(f"{field}[is]:NOT_NULL", safe=":")
    req = urllib.request.Request(f"{base}/rest/{plural}?limit=1&filter={q}",
                                 headers={"Authorization": "Bearer " + token})
    return json.loads(urllib.request.urlopen(req).read())["totalCount"]


def remove_field(objects, obj, plural, name):
    """Özel alanı, hiçbir kayıtta dolu değilse kaldırır (önce pasifleştirir)."""
    field = objects[obj]["fields"].get(name)
    if not field:
        print("zaten yok:", obj, name)
        return
    n = count_filled(plural, name)
    if n:
        raise SystemExit(f"{obj}.{name} {n} kayıtta dolu: önce taşı (onay gerekir)")
    gql(UPDATE_FIELD, {"id": field["id"], "u": {"isActive": False}})
    gql(DELETE_FIELD, {"id": field["id"]})
    del objects[obj]["fields"][name]
    print("kaldırıldı:", obj, name)


_POS = ("position { ... on PageLayoutWidgetVerticalListPosition { layoutMode index } ... on PageLayoutWidgetGridPosition "
        "{ layoutMode row column rowSpan columnSpan } ... on PageLayoutWidgetCanvasPosition { layoutMode } }")


def kayit_sekmesi(objects, obj, sekme_adi, bilesen_adi, widget_basligi=None):
    """Kayıt sayfasının en başına bir sekme ve içine tek ön bileşen widget'ı (liste 14b, 15a). Önce: twenty app apply.
    Tam sayfada ilk sekme dar sol sütuna sabitlenmesin diye sabitleme kapatılır (kullanıcı, 13 Kas). Basit güncelleme
    girdisinde bu alan yok; tam güncelleme sekme ve widget'ları yapılandırma göndermeden geri yollar (yapılandırma
    korunur — 13 Kas'ta denendi, geri okunarak doğrulandı). Idempotent; kullanıcının taşıdığı sekmeye dokunulmaz."""
    oid = objects[obj]["id"]
    fc = next((f["id"] for f in gql("{ frontComponents { id name } }")["frontComponents"] if f["name"] == bilesen_adi), None)
    if not fc:
        raise SystemExit(f"{bilesen_adi} bileşeni yok: önce apps/ascendia-pano → twenty app apply")
    pq = ("{ getPageLayouts(pageLayoutType: RECORD_PAGE) { id objectMetadataId tabs { id title position widgets { id type "
          "configuration { ... on FrontComponentConfiguration { frontComponentId } } } } } }")
    duzen = next(p for p in gql(pq)["getPageLayouts"] if p["objectMetadataId"] == oid)
    sekme = next((t for t in duzen["tabs"] if t["title"] == sekme_adi), None)
    if not sekme:
        en_kucuk = min((t["position"] for t in duzen["tabs"]), default=0)
        sekme = gql("mutation($i: CreatePageLayoutTabInput!) { createPageLayoutTab(input: $i) { id title position } }",
                    {"i": {"title": sekme_adi, "position": en_kucuk - 1, "pageLayoutId": duzen["id"],
                           "layoutMode": "VERTICAL_LIST"}})["createPageLayoutTab"]
        sekme["widgets"] = []
        print(f"oluşturuldu: sekme {sekme_adi}")
    else:
        print(f"var: sekme {sekme_adi}")
    if any((w.get("configuration") or {}).get("frontComponentId") == fc for w in sekme["widgets"]):
        print(f"var: {bilesen_adi} widget'ı")
    else:
        gql("mutation($i: CreatePageLayoutWidgetInput!) { createPageLayoutWidget(input: $i) { id } }",
            {"i": {"pageLayoutTabId": sekme["id"], "title": widget_basligi or sekme_adi, "type": "FRONT_COMPONENT",
                   "position": {"layoutMode": "VERTICAL_LIST", "index": 0},
                   "configuration": {"configurationType": "FRONT_COMPONENT", "frontComponentId": fc}}})
        print(f"oluşturuldu: {bilesen_adi} widget'ı")
    tq = ("{ getPageLayouts(pageLayoutType: RECORD_PAGE) { id name type objectMetadataId isFirstTabPinned tabs { id title "
          "position icon layoutMode widgets { id title type objectMetadataId " + _POS + " } } } }")
    p = next(x for x in gql(tq)["getPageLayouts"] if x["objectMetadataId"] == oid)
    if p["isFirstTabPinned"]:
        girdi = {"name": p["name"], "type": p["type"], "objectMetadataId": oid, "isFirstTabPinned": False,
                 "tabs": [{"id": t["id"], "title": t["title"], "position": t["position"], "icon": t["icon"],
                           "layoutMode": t["layoutMode"],
                           "widgets": [{"id": w["id"], "pageLayoutTabId": t["id"], "title": w["title"], "type": w["type"],
                                        "objectMetadataId": w["objectMetadataId"], "position": w["position"]}
                                       for w in t["widgets"]]} for t in p["tabs"]]}
        gql("mutation($id: String!, $i: UpdatePageLayoutWithTabsInput!) { updatePageLayoutWithTabsAndWidgets(id: $id, input: $i) { id } }",
            {"id": p["id"], "i": girdi})
        print("ilk sekme sabitlemesi kapatıldı")
    else:
        print("var: ilk sekme sabit değil")
