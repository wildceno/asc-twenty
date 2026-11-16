#!/usr/bin/env python3
"""Paraşüt'e bir kerelik yetki (liste 21): OAuth2 Authorization Code + PKCE (S256), Paraşüt OAuth rehberi (devhub, 15 Kas).

Ön koşul: ~/twenty/.parasut.json {"client_id", "company_id", "api", "token_url", "auth_url", "redirect_uri"} ve
gizli istemcide ~/twenty/.parasut-client-secret (600). Kullanım (sunucuda):
  python3 ops/parasut-baglan.py baslat          → yetki adresini yazar (tarayıcıda açın, Paraşüt'te onaylayın)
  pbpaste | ssh monster 'python3 ~/ascendia-crm/ops/parasut-baglan.py bitir'
      (dönüş sayfasının TÜM adresini kopyalayın; sayfa "bulunamadı" gösterse de adreste code= vardır)
Sonuç: ~/twenty/parasut/oturum.json (600; yenileme belirteci, motor her kullanımda yeniler).
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

TW = os.path.expanduser("~/twenty")
AYAR = json.load(open(f"{TW}/.parasut.json"))
KLASOR = f"{TW}/parasut"
GECICI = f"{KLASOR}/pkce.json"
os.makedirs(KLASOR, mode=0o700, exist_ok=True)
os.umask(0o077)

if sys.argv[1:] == ["baslat"]:
    dogrulayici = secrets.token_urlsafe(64)
    zorluk = base64.urlsafe_b64encode(hashlib.sha256(dogrulayici.encode()).digest()).rstrip(b"=").decode()
    durum = secrets.token_urlsafe(16)
    json.dump({"dogrulayici": dogrulayici, "durum": durum}, open(GECICI, "w"))
    print(AYAR["auth_url"] + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": AYAR["client_id"], "redirect_uri": AYAR["redirect_uri"],
        "scope": "openid offline_access", "state": durum, "code_challenge": zorluk, "code_challenge_method": "S256"}))
elif sys.argv[1:] == ["bitir"]:
    donus = urllib.parse.urlparse(sys.stdin.read().strip())
    q = dict(urllib.parse.parse_qsl(donus.query))
    g = json.load(open(GECICI))
    if q.get("state") != g["durum"]:
        sys.exit("state uyuşmuyor: adres bu oturuma ait değil, 'baslat' ile yeniden deneyin")
    veri = {"grant_type": "authorization_code", "code": q["code"], "redirect_uri": AYAR["redirect_uri"],
            "client_id": AYAR["client_id"], "code_verifier": g["dogrulayici"]}
    sir = f"{TW}/.parasut-client-secret"
    if os.path.exists(sir) and os.path.getsize(sir):
        veri["client_secret"] = open(sir).read().strip()
    t = json.loads(urllib.request.urlopen(urllib.request.Request(AYAR["token_url"], data=urllib.parse.urlencode(veri).encode()), timeout=30).read())
    json.dump({"refresh_token": t["refresh_token"]}, open(f"{KLASOR}/oturum.json", "w"))
    os.remove(GECICI)
    print("Paraşüt oturumu kaydedildi (yenileme belirteci süresi:", t.get("refresh_expires_in"), "sn)")
else:
    sys.exit(__doc__)
