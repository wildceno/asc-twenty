#!/usr/bin/env python3
"""Katalog "Detay Açıklama" biçimli metin (RICH_TEXT) olur (kullanıcı kararı 14 Kas 2026): tek satırlık TEXT alanı
yapıştırılan metindeki satır sonlarını siliyordu; biçimli metinde paragraf ve madde işaretleri korunur ve belgeye taşınır.

Adımlar (idempotent): yeni alan `details` (RICH_TEXT) → eski `description` (TEXT) metni markdown olarak kopyalanır ve
geri okunarak doğrulanır → eski alan boşaltılır → boş eski alan kaldırılır. Önce yedek: ~/twenty/backups/elle/.
"""
import json
import os
import sys
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import ensure_field, load_objects, remove_field  # noqa: E402

KEY = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()


def rest(m, yol, govde=None):
    r = urllib.request.Request("http://localhost:3010" + yol, method=m, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read() or b"{}")


def blok(markdown):
    """Düz metin / basit markdown → BlockNote paragrafları (Twenty kayıt ekranı blok biçimini gösterir; API'ye yalnız
    markdown yazılınca blok boş kalıyor — 14 Kas'ta denendi)."""
    out = []
    for satir in (markdown or "").split("\n"):
        out.append({"id": str(uuid.uuid4()), "type": "paragraph",
                    "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
                    "content": [{"type": "text", "text": satir, "styles": {}}] if satir else [], "children": []})
    return json.dumps(out, ensure_ascii=False)


O = load_objects()
ensure_field(O, "catalogItem", "details", "RICH_TEXT", "Detay Açıklama")
if "description" in O["catalogItem"]["fields"]:
    for k in rest("GET", "/rest/catalogItems?limit=200")["data"]["catalogItems"]:
        eski = k.get("description")
        if not eski:
            continue
        if not ((k.get("details") or {}).get("markdown") or "").strip():
            rest("PATCH", f"/rest/catalogItems/{k['id']}", {"details": {"markdown": eski}})
        geri = rest("GET", f"/rest/catalogItems/{k['id']}")["data"]["catalogItem"]
        if ((geri.get("details") or {}).get("markdown") or "").strip() != eski.strip():
            raise SystemExit(f"{k['name']}: kopya doğrulanamadı, eski alana dokunulmadı")
        rest("PATCH", f"/rest/catalogItems/{k['id']}", {"description": None})
        print("taşındı:", k["name"])
    O = load_objects()
    remove_field(O, "catalogItem", "catalogItems", "description")
for k in rest("GET", "/rest/catalogItems?limit=200")["data"]["catalogItems"]:
    d = k.get("details") or {}
    if (d.get("markdown") or "").strip() and not d.get("blocknote"):
        rest("PATCH", f"/rest/catalogItems/{k['id']}", {"details": {"markdown": d["markdown"], "blocknote": blok(d["markdown"])}})
        print("blok biçimi yazıldı:", k["name"])
