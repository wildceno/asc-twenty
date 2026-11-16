#!/usr/bin/env python3
"""Deneme ortamı (Monster) için her role bir test kullanıcısı açar; idempotent. Müşteri ortamında çalıştırılmaz.

- Çalışma alanının herkese açık davet bağlantısıyla şifreli kayıt (signUpInWorkspace).
- Rol ataması API anahtarıyla yapılamıyor (v2.57.1): betik dener, olmazsa arayüzden atanacakları listeler.
- Şifreler sohbete/repoya yazılmaz: ~/twenty/.test-kullanicilar (600) dosyasına eklenir.
- Ekip kayıtları: Satış kullanıcısının yöneticisi Yönetici, support'u Support kullanıcısı.
Kullanım (sunucuda): python3 ops/test-kullanicilari.py
"""
import json
import os
import secrets
import string
import urllib.request

API = os.environ.get("TWENTY_URL", "http://localhost:3010")
KEY = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
DOSYA = os.path.expanduser("~/twenty/.test-kullanicilar")
ORIGIN = os.environ.get("TWENTY_ORIGIN") or next((l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/twenty/.env")) if l.startswith("SERVER_URL=")), "http://localhost:3010")

KULLANICILAR = [  # (rol, e-posta parçası, ad, soyad, Ekip görevi)
    ("Super-user", "superuser", "Test", "Super-user", None),
    ("Satış", "satis", "Test", "Satış", "SALES"),
    ("Yönetici", "yonetici", "Test", "Yönetici", "MANAGER"),
    ("Support", "support", "Test", "Support", "SUPPORT"),
    ("Pazarlama", "pazarlama", "Test", "Pazarlama", "MARKETING"),
]


def istek(yol, govde=None, method="POST", anahtar=KEY):
    h = {"Content-Type": "application/json"}
    if anahtar:
        h["Authorization"] = "Bearer " + anahtar
    r = urllib.request.Request(API + yol, method=method, headers=h,
                               data=json.dumps(govde).encode() if govde is not None else None)
    return json.loads(urllib.request.urlopen(r).read() or b"{}")


def gql(sorgu, degisken=None, anahtar=KEY):
    d = istek("/metadata", {"query": sorgu, "variables": degisken or {}}, anahtar=anahtar)
    if d.get("errors"):
        raise SystemExit(json.dumps(d["errors"], ensure_ascii=False)[:400])
    return d["data"]


def uyeler():
    return {(m.get("userEmail") or "").lower(): m for m in istek("/rest/workspaceMembers?limit=60", method="GET")
            ["data"]["workspaceMembers"]}


ws = gql("{ currentWorkspace { id inviteHash isPublicInviteLinkEnabled } }")["currentWorkspace"]
if not ws["isPublicInviteLinkEnabled"]:
    raise SystemExit("Herkese açık davet bağlantısı kapalı")
roller = {r["label"]: r["id"] for r in gql("{ getRoles { id label } }")["getRoles"]}
os.umask(0o077)

for rol, parca, ad, soyad, _ in KULLANICILAR:
    eposta = f"test.{parca}@ascendia.test"
    m = uyeler().get(eposta)
    if not m:
        sifre = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20)) + "!7a"
        su = gql("mutation($e:String!,$p:String!,$w:UUID!,$h:String!){ signUpInWorkspace(email:$e,password:$p,"
                 "workspaceId:$w,workspaceInviteHash:$h){ loginToken { token } } }",
                 {"e": eposta, "p": sifre, "w": ws["id"], "h": ws["inviteHash"]}, anahtar=None)
        gql("mutation($t:String!,$o:String!){ getAuthTokensFromLoginToken(loginToken:$t, origin:$o)"
            "{ tokens { accessOrWorkspaceAgnosticToken { token } } } }",
            {"t": su["signUpInWorkspace"]["loginToken"]["token"], "o": ORIGIN}, anahtar=None)
        with open(DOSYA, "a") as fh:
            fh.write(f"{rol}\t{eposta}\t{sifre}\n")
        m = uyeler().get(eposta)
        if not m:
            raise SystemExit(f"{eposta} kaydoldu ama çalışma alanı üyesi görünmüyor: elle incele")
        print("kullanıcı açıldı:", eposta)
    if (m.get("name") or {}).get("firstName") != ad or (m.get("name") or {}).get("lastName") != soyad:
        istek(f"/rest/workspaceMembers/{m['id']}", {"name": {"firstName": ad, "lastName": soyad}}, method="PATCH")
    # Rol ataması API anahtarına kapalı (Twenty: oturumdaki yönetici gerekir) → arayüzden: Ayarlar → Üyeler
    try:
        gql("mutation($m:UUID!,$r:UUID!){ updateWorkspaceMemberRole(workspaceMemberId:$m, roleId:$r){ id } }",
            {"m": m["id"], "r": roller[rol]})
        print("rol:", eposta, "→", rol)
    except SystemExit:
        print("rol arayüzden atanmalı:", eposta, "→", rol)

# Ekip kayıtları
u = uyeler()
uid = {parca: u[f"test.{parca}@ascendia.test"]["id"] for _, parca, *_ in KULLANICILAR}
ekip = {e.get("memberId"): e for e in istek("/rest/teamMembers?limit=60", method="GET")["data"]["teamMembers"]}
for rol, parca, ad, soyad, gorev in KULLANICILAR:
    govde = {"name": f"{ad} {soyad}", "memberId": uid[parca], "jobFunction": gorev}
    if parca == "satis":
        govde.update({"managerId": uid["yonetici"], "supportId": uid["support"]})
    govde = {k: v for k, v in govde.items() if v is not None}
    if uid[parca] in ekip:
        fark = {k: v for k, v in govde.items() if ekip[uid[parca]].get(k) != v}
        if fark:
            istek(f"/rest/teamMembers/{ekip[uid[parca]]['id']}", fark, method="PATCH")
    else:
        istek("/rest/teamMembers", govde)
        print("ekip kaydı:", govde["name"])
print("bitti; giriş bilgileri:", DOSYA)
