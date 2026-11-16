#!/usr/bin/env python3
"""Claude ↔ Twenty MCP anahtarını doğrular (liste 18). Sunucuda: python3 ops/claude-mcp-dogrula.py

Anahtar ~/twenty/.claude-mcp-key (600). Twenty'de API anahtarını yalnız oturum açmış kullanıcı oluşturur (API anahtarı
anahtar üretemez, doğrulandı): Ayarlar → Geliştiriciler → API anahtarı oluştur, ad "Claude MCP", rol "Claude Asistan".
Panodan Monster'a: ! pbpaste | ssh monster 'umask 077; cat > ~/twenty/.claude-mcp-key && chmod 600 ~/twenty/.claude-mcp-key'
Beklenen: okuma çalışır; ana nesnelerde silme aracı ve e-posta gönderme aracı sunulmaz. Kalan sistem nesnesi silme
araçları (ekler, görev/not bağlantıları, zaman çizelgesi, görünümler) 6-CRM/.claude/settings.json deny kuralıyla kapalı.
"""
import json
import os
import sys
import urllib.request

K = open(os.path.expanduser("~/twenty/.claude-mcp-key")).read().strip()


def mcp(method, params):
    r = urllib.request.Request("http://localhost:3010/mcp", method="POST",
                               data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                               headers={"Authorization": "Bearer " + K, "Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    t = urllib.request.urlopen(r, timeout=30).read().decode()
    return json.loads(t[t.find("{"):])


araclar = {t["name"] for t in mcp("tools/list", {})["result"]["tools"]}
oku = mcp("tools/call", {"name": "find_many_opportunities", "arguments": {"limit": 1, "select": ["id", "name"]}})
sonuc = [
    ("Okuma çalışıyor", '"success":true' in oku["result"]["content"][0]["text"]),
    ("Ana nesnelerde silme yok", not araclar & {f"delete_one_{n}" for n in ("company", "person", "opportunity", "contract", "target")}),
    ("E-posta gönderme yok", "send_email" not in araclar),
]
for ad, ok in sonuc:
    print(("GEÇTİ " if ok else "KALDI ") + ad)
print(len(araclar), "araç sunuluyor")
sys.exit(0 if all(ok for _, ok in sonuc) else 1)
