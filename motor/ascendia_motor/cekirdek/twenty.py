"""Twenty REST ve GraphQL istemcisi: anahtar başına dakikada 100 istek sınırı (80'de tutulur), 429'da yeniden dener; dosya kopyalama."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from ascendia_motor.cekirdek.ayar import API, KEY_FILE
from ascendia_motor.cekirdek.gunluk import log, oku


# Twenty API anahtarı başına dakikada 100 istek sınırı var (v2.57.1, 429 RATE_LIMITED): kendimizi 80'de tutarız,
# yine de 429 gelirse bekleyip yeniden deneriz.
HIZ_SINIRI, HIZ_PENCERE = 80, 60.0


_istekler, _hiz_kilit = [], threading.Lock()


def _bekle_sira():
    with _hiz_kilit:
        while True:
            simdi = time.monotonic()
            while _istekler and simdi - _istekler[0] > HIZ_PENCERE:
                _istekler.pop(0)
            if len(_istekler) < HIZ_SINIRI:
                _istekler.append(simdi)
                return
            time.sleep(HIZ_PENCERE - (simdi - _istekler[0]) + 0.05)


def _istek(method, url, body=None):
    for deneme in range(6):
        _bekle_sira()
        req = urllib.request.Request(url, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + oku(KEY_FILE),
                                              "Content-Type": "application/json"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429 and deneme < 5:
                try:
                    bekle = float(json.loads(e.read()).get("retryAfterSeconds") or 5)
                except ValueError:
                    bekle = 5
                time.sleep(max(bekle, 1) * (deneme + 1))
                continue
            if e.code == 404 and method == "GET":
                return None
            if e.code == 404 and method == "PATCH":
                # Kayıt bu arada silinmiş (ör. tarama sırasında kullanıcı sildi): hata değil, atlanır
                log(f"kayıt silinmiş, güncelleme atlandı: {url[len(API):]}")
                return None
            raise RuntimeError(f"{method} {url[len(API):]}: {e.code} {e.read().decode()[:400]}")


def gql(sorgu, degisken=None):
    d = _istek("POST", API + "/metadata", {"query": sorgu, "variables": degisken or {}})
    if d.get("errors"):
        raise RuntimeError(json.dumps(d["errors"])[:400])
    return d["data"]


_alanlar = {}


def alan_id(nesne, alan):
    if not _alanlar:
        for e in gql("{ objects(paging:{first:300}) { edges { node { nameSingular "
                     "fields(paging:{first:500}) { edges { node { id name } } } } } } }")["objects"]["edges"]:
            for f in e["node"]["fields"]["edges"]:
                _alanlar[(e["node"]["nameSingular"], f["node"]["name"])] = f["node"]["id"]
    return _alanlar[(nesne, alan)]


def ic_adres(url):
    """Twenty'nin verdiği dış adresi (SERVER_URL) iç ağ adresine çevirir."""
    p = urllib.parse.urlsplit(url)
    return API + p.path + ("?" + p.query if p.query else "")


def dosya_kopyala(dosyalar, nesne, alan):
    """FILES değerindeki dosyaları indirip hedef alana yeni dosya olarak yükler (kaynak silinse de kalır)."""
    yeni = []
    for f in dosyalar or []:
        if not f.get("url"):
            continue
        icerik = urllib.request.urlopen(ic_adres(f["url"]), timeout=60).read()
        ad = f.get("label") or ("dosya" + (f.get("extension") or ""))
        t = gql("mutation($n:String!,$s:Float!,$a:String!){ createFileUpload(filename:$n,size:$s,"
                "fileFolder:FilesField,fieldMetadataId:$a){ fileId uploadUrl contentType } }",
                {"n": ad, "s": len(icerik), "a": alan_id(nesne, alan)})["createFileUpload"]
        _bekle_sira()
        urllib.request.urlopen(urllib.request.Request(ic_adres(t["uploadUrl"]), method="PUT", data=icerik,
                                                      headers={"Content-Type": t["contentType"]}), timeout=60)
        gql("mutation($f:String!){ completeFileUpload(fileId:$f){ id } }", {"f": t["fileId"]})
        yeni.append({"fileId": t["fileId"], "label": ad})
    return yeni


def api(method, path, body=None):
    d = _istek(method, API + path, body)
    return d and d.get("data")


def q(s):
    return urllib.parse.quote(s, safe=":,[]")


def liste(plural, filtre=None, sira=None, limit=60):
    out, imlec = [], None
    while True:
        p = f"?limit={limit}"
        if filtre:
            p += "&filter=" + q(filtre)
        if sira:
            p += "&order_by=" + q(sira)
        if imlec:
            p += "&starting_after=" + q(imlec)
        d = _istek("GET", API + f"/rest/{plural}{p}")
        out += d["data"][plural]
        if limit < 60 or not d["pageInfo"]["hasNextPage"]:
            return out
        imlec = d["pageInfo"]["endCursor"]
