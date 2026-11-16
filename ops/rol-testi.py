#!/usr/bin/env python3
"""Rol testi (deneme ortamı): her deneme kullanıcısıyla giriş yapıp yetkileri dener, test kayıtlarını siler.
Ön koşul: ops/test-kullanicilari.py çalışmış ve roller arayüzden atanmış olmalı.
Beklenen: Yönetim düzenleme yalnız Super-user; hedef/dönem/CRM ayarı okuma Satış, Yönetici, Support'ta da var
(13 Kas, pano için), Pazarlama'da yok; şirket açma Pazarlama hariç; sahiplik değişikliği yalnız Super-user;
çöp kutusuna silme yalnız Super-user; Satış kendi şirketinde uyarısız, başkasınınkinde uyarı + onay görevi.
Kullanım (sunucuda): python3 ops/rol-testi.py
"""
import json, os, time, urllib.request, urllib.error
B = "http://localhost:3010"; ORIGIN = os.environ.get("TWENTY_ORIGIN") or next((l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/twenty/.env")) if l.startswith("SERVER_URL=")), "http://localhost:3010")
ADMIN = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
def istek(tok, m, p, b=None):
    h = {"Content-Type": "application/json"}
    if tok: h["Authorization"] = "Bearer " + tok
    r = urllib.request.Request(B + p, method=m, headers=h, data=json.dumps(b).encode() if b is not None else None)
    for deneme in range(8):
        try: return 200, json.loads(urllib.request.urlopen(r).read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(15); continue   # API sınırı (motorla aynı anahtar): bekle, yeniden dene
            return e.code, e.read().decode()[:120]
    return 429, "sınır"
def gql(q, v, tok=None):
    s, d = istek(tok, "POST", "/metadata", {"query": q, "variables": v})
    if s != 200 or d.get("errors"): raise SystemExit(str(d)[:300])
    return d["data"]
def giris(eposta, sifre):
    lt = gql("mutation($e:String!,$p:String!,$o:String!){ getLoginTokenFromCredentials(email:$e,password:$p,origin:$o){ loginToken { token } } }", {"e": eposta, "p": sifre, "o": ORIGIN})
    t = gql("mutation($t:String!,$o:String!){ getAuthTokensFromLoginToken(loginToken:$t,origin:$o){ tokens { accessOrWorkspaceAgnosticToken { token } } } }", {"t": lt["getLoginTokenFromCredentials"]["loginToken"]["token"], "o": ORIGIN})
    return t["getAuthTokensFromLoginToken"]["tokens"]["accessOrWorkspaceAgnosticToken"]["token"]
K = {l.split("\t")[0]: l.strip().split("\t") for l in open(os.path.expanduser("~/twenty/.test-kullanicilar"))}
T = {rol: giris(v[1], v[2]) for rol, v in K.items()}
uye = {m["userEmail"]: m["id"] for m in istek(ADMIN, "GET", "/rest/workspaceMembers?limit=60")[1]["data"]["workspaceMembers"]}
sil = []  # (yol)
sahip_sirket = {}
def ok(s): return "izin var" if s == 200 else f"engellendi ({s})"
def kayit(rol, nesne, govde, tekil):
    s, d = istek(T[rol], "POST", f"/rest/{nesne}", govde)
    if s == 200: sil.append(f"/rest/{nesne}/{d['data'][tekil]['id']}"); return s, d["data"][tekil]["id"]
    return s, None
try:
    for rol in K:
        print(f"{rol:11} Yönetim okuma (CRM Ayarları):", ok(istek(T[rol], "GET", "/rest/crmSettings")[0]))
    hedef = istek(ADMIN, "GET", "/rest/targets?limit=1")[1]["data"]["targets"][0]
    for rol in K:
        s = istek(T[rol], "PATCH", f"/rest/targets/{hedef['id']}", {"name": hedef["name"]})[0]
        print(f"{rol:11} hedef düzenleme:", ok(s))
    for rol in K:
        s, cid = kayit(rol, "companies", {"name": f"TEST rol {rol} - silinecek"}, "createCompany")
        sahip_sirket[rol] = cid
        print(f"{rol:11} şirket açma:", ok(s))
        if cid:
            print(f"{rol:11} şirkette Account Manager değiştirme:", ok(istek(T[rol], "PATCH", f"/rest/companies/{cid}", {"accountManagerId": uye[K[rol][1]]})[0]))
            # Arayüzdeki silme çöp kutusuna atar; REST'te ?soft_delete=true (parametresiz DELETE kalıcı siler)
            print(f"{rol:11} şirketi çöp kutusuna silme:", ok(istek(T[rol], "DELETE", f"/rest/companies/{cid}?soft_delete=true")[0]))
    # Fırsat açma denetimi: Satış kendi açtığı şirkete (yetkili) ve başkasının şirketine (yetkisiz)
    kendi = sahip_sirket["Satış"]
    s1, o1 = kayit("Satış", "opportunities", {"name": "TEST yetkili - silinecek", "companyId": kendi}, "createOpportunity")
    baska = sahip_sirket["Yönetici"]   # Satış'ın sorumlu olmadığı şirket (testin açtığı)
    s2, o2 = kayit("Satış", "opportunities", {"name": "TEST yetkisiz - silinecek", "companyId": baska}, "createOpportunity")
    for _ in range(30):   # motor kuyruğu yoğunsa gecikebilir: uyarıyı en fazla 90 sn bekle
        time.sleep(3)
        if (istek(ADMIN, "GET", f"/rest/opportunities/{o2}")[1]["data"]["opportunity"] or {}).get("systemWarning"): break
    time.sleep(3)
    for oid, ad in ((o1, "kendi açtığı şirkette"), (o2, "yetkisi olmayan şirkette")):
        o = istek(ADMIN, "GET", f"/rest/opportunities/{oid}")[1]["data"]["opportunity"]
        print(f"Satış fırsat {ad}: uyarı={'VAR' if o.get('systemWarning') else 'yok'}, sahibi açan kişi={o.get('ownerId') == uye[K['Satış'][1]]}")
    # 12c: fırsatın şirketi değiştirilemez (Satış'ın değişikliği geri alınır, Super-user'ınki kalır)
    istek(T["Satış"], "PATCH", f"/rest/opportunities/{o1}", {"companyId": sahip_sirket["Yönetici"]})
    for _ in range(30):
        time.sleep(3)
        if istek(ADMIN, "GET", f"/rest/opportunities/{o1}")[1]["data"]["opportunity"]["companyId"] == kendi: break
    print("Satış fırsatın şirketini değiştirme: ", "geri alındı" if istek(ADMIN, "GET", f"/rest/opportunities/{o1}")[1]["data"]["opportunity"]["companyId"] == kendi else "KALDI")
    istek(T["Super-user"], "PATCH", f"/rest/opportunities/{o1}", {"companyId": sahip_sirket["Yönetici"]})
    time.sleep(25)
    print("Super-user fırsatın şirketini değiştirme:", "kaldı" if istek(ADMIN, "GET", f"/rest/opportunities/{o1}")[1]["data"]["opportunity"]["companyId"] == sahip_sirket["Yönetici"] else "GERİ ALINDI")
    gorevler = [g for g in istek(ADMIN, "GET", "/rest/tasks?limit=100")[1]["data"]["tasks"] if "TEST yetki" in g["title"]]
    print("super-user/admin onay görevi:", len(gorevler))
    sil += [f"/rest/tasks/{g['id']}" for g in gorevler]
finally:
    for p in [x for x in sil if "opportunities" in x]:
        oid = p.split("/")[-1]
        for sc in istek(ADMIN, "GET", f"/rest/stageChanges?filter=opportunityId[eq]:{oid}")[1]["data"]["stageChanges"]: istek(ADMIN, "DELETE", f"/rest/stageChanges/{sc['id']}")
        for tt in istek(ADMIN, "GET", f"/rest/taskTargets?filter=targetOpportunityId[eq]:{oid}")[1]["data"]["taskTargets"]: istek(ADMIN, "DELETE", f"/rest/taskTargets/{tt['id']}")
    for p in sorted(sil, key=lambda x: ("companies" in x)): istek(ADMIN, "DELETE", p)
    kalan = [c["name"] for c in istek(ADMIN, "GET", "/rest/companies?limit=60")[1]["data"]["companies"] if c["name"].startswith("TEST")]
    print("temizlik: kalan test şirketi", kalan)
