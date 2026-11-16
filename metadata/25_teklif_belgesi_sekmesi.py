#!/usr/bin/env python3
"""Teklif kayıt sayfasına "Belge" sekmesi ve Teklif Belgesi widget'ı (liste 15b). Önce: twenty app apply.
Teklif sekmesi en başta kalır: Belge sekmesi kendi oluşturulduğunda en başa konur, ardından 20_teklif_ekrani yeniden
çalıştırılmaz; bu yüzden burada sekme Teklif'in hemen sonrasına alınır. Idempotent."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import gql, kayit_sekmesi, load_objects  # noqa: E402

O = load_objects()
kayit_sekmesi(O, "quote", "Belge", "Teklif Belgesi")
duzen = next(p for p in gql("{ getPageLayouts(pageLayoutType: RECORD_PAGE) { id objectMetadataId tabs { id title position } } }")
             ["getPageLayouts"] if p["objectMetadataId"] == O["quote"]["id"])
sekmeler = {t["title"]: t for t in duzen["tabs"]}
teklif, belge = sekmeler.get("Teklif"), sekmeler.get("Belge")
digerleri = [t["position"] for t in duzen["tabs"] if t["title"] not in ("Teklif", "Belge")]
if teklif and belge and not (teklif["position"] < belge["position"] < min(digerleri, default=belge["position"] + 1)):
    ilk = min(digerleri, default=0)
    gql("mutation($id: String!, $i: UpdatePageLayoutTabInput!) { updatePageLayoutTab(id: $id, input: $i) { id } }",
        {"id": teklif["id"], "i": {"position": ilk - 2}})
    gql("mutation($id: String!, $i: UpdatePageLayoutTabInput!) { updatePageLayoutTab(id: $id, input: $i) { id } }",
        {"id": belge["id"], "i": {"position": ilk - 1}})
    print("sekme sırası: Teklif, Belge")
else:
    print("var: sekme sırası Teklif, Belge")
