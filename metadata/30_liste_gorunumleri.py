#!/usr/bin/env python3
"""Liste görünümlerinin sütunları (16 Kas 2026). Twenty v2.57.1 her nesne için asıl varsayılan görünümün (key=INDEX)
yanında aynı adlı, anahtarsız bir TABLE görünümü de açıyor; arayüz bunu gösteriyor ve içinde yalnız sistem sütunları
var (Katalog, Rakip Hizmetleri, Hedefler, Temaslar… listelerinde alanlar görünmüyordu). Betik kopyayı silmez: INDEX
görünümünde olup kopyada olmayan sütunları aynı sıra, görünürlük ve genişlikle ekler. İki kez çalışınca zarar vermez.
Kullanım (sunucuda): python3 metadata/30_liste_gorunumleri.py
"""
from twenty import gql, load_objects

O = load_objects()
eklenen = 0
for ad, o in sorted(O.items()):
    vs = gql("query($o: String) { getViews(objectMetadataId: $o) { id name type key } }", {"o": o["id"]})["getViews"]
    asil = next((v for v in vs if v["key"] == "INDEX" and v["type"] == "TABLE"), None)
    if not asil:
        continue
    for kopya in (v for v in vs if v["key"] is None and v["type"] == "TABLE" and v["name"] == asil["name"]):
        alan = lambda v: gql("query($v: String!) { getViewFields(viewId: $v) { fieldMetadataId isVisible size position } }",
                             {"v": v})["getViewFields"]
        var = {f["fieldMetadataId"] for f in alan(kopya["id"])}
        eksik = [f for f in alan(asil["id"]) if f["fieldMetadataId"] not in var]
        if eksik:
            gql("mutation($i: [CreateViewFieldInput!]!) { createManyViewFields(inputs: $i) { id } }",
                {"i": [{"viewId": kopya["id"], **f} for f in eksik]})
            eklenen += len(eksik)
            print(f"{ad}: '{kopya['name']}' görünümüne {len(eksik)} sütun eklendi")
print("eklenen sütun:", eklenen if eklenen else "yok (zaten tamam)")
