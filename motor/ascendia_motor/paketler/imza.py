"""Paket IMZA (liste 20; kullanıcı kararları 14 Kas 2026): DocuSign ile teklif imzası.

- Belge sekmesi teklife "İmza İsteği = İmzaya gönder" yazar → teklifin son PDF'i İmzalayacak Kişi'ye DocuSign zarfı
  olarak gider; teklif Gönderildi olur (rakamlar fırsata). Marj onayı bekleyen teklif gönderilmez. Karşı imza yok.
- İmza yeri: belgede (şablondaki {{imza}} → belge servisi beyaz "/imza/" yazar) çapa varsa imza alanı oraya; yoksa
  imzalayan kendisi yerleştirir (serbest imza).
- Durum: 00:00, 08:00, 16:00'da (TR) ve "Durumu kontrol et" istenince DocuSign'a sorulur (Monster dışarıya kapalı,
  DocuSign bildirim gönderemez). İmzalandı → teklif Kabul, imzalı PDF teklifin Belgeler'ine, fırsatın Onaylanan Teklif
  ve Sipariş / Onay Dokümanı alanlarına; fırsat açık aşamadaysa Audit'e geçer (sözleşme süreci başlar; kullanıcı kararı
  14 Kas: müşterinin imzaladığı teklif sipariş onayıdır). Reddedildi → Red; iptal → İptal.
Kimlik: JWT (RS256, konteynerdeki openssl ile imzalanır); belirteç 1 saat, süresi dolmadan yenilenir.
"""
import base64
import datetime as dt
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from ascendia_motor.cekirdek.ayar import OPEN, TR
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.twenty import api, liste
from ascendia_motor.paketler.belge import dosya_yukle
from ascendia_motor.paketler.sablon import dosya_indir

AYAR_FILE = os.environ.get("DOCUSIGN_AYAR_FILE", "/run/sirlar/docusign.json")
KEY_FILE = os.environ.get("DOCUSIGN_KEY_FILE", "/run/sirlar/docusign_key")
CAPA = "/imza/"
KONTROL_SAATLERI = (0, 8, 16)                 # kullanıcı kararı 14 Kas: günde üç kez
BEKLEYEN = ("SENT", "DELIVERED")
DURUM = {"sent": "SENT", "delivered": "DELIVERED", "completed": "COMPLETED", "declined": "DECLINED", "voided": "VOIDED"}

_belirtec = {"deger": None, "bitis": 0}
_son_dilim = None


class AyarYok(Exception):
    pass


def ayar():
    try:
        a = json.load(open(AYAR_FILE))
    except (OSError, ValueError):
        a = {}
    if not all(a.get(k) for k in ("integration_key", "user_id", "account_id", "base_uri", "oauth_host")):
        raise AyarYok("DocuSign bağlantısı kurulmamış (ayar yok)")
    if not os.path.exists(KEY_FILE) or not os.path.getsize(KEY_FILE):
        raise AyarYok("DocuSign bağlantısı kurulmamış (özel anahtar yok)")
    return a


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def belirtec(a):
    if _belirtec["deger"] and time.time() < _belirtec["bitis"] - 300:
        return _belirtec["deger"]
    simdi = int(time.time())
    govde = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()) + "." + _b64(json.dumps({
        "iss": a["integration_key"], "sub": a["user_id"], "aud": a["oauth_host"], "iat": simdi, "exp": simdi + 3600,
        "scope": "signature impersonation"}).encode())
    imza = subprocess.run(["openssl", "dgst", "-sha256", "-sign", KEY_FILE], input=govde.encode(), capture_output=True,
                          check=True).stdout
    veri = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": govde + "." + _b64(imza)}).encode()
    t = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://{a['oauth_host']}/oauth/token", data=veri),
                                          timeout=30).read())
    _belirtec.update(deger=t["access_token"], bitis=time.time() + int(t.get("expires_in") or 3600))
    return _belirtec["deger"]


def ds(a, yontem, yol, govde=None, ham=False):
    url = f"{a['base_uri']}/restapi/v2.1/accounts/{a['account_id']}{yol}"
    r = urllib.request.Request(url, method=yontem, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Authorization": "Bearer " + belirtec(a), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=120) as f:
            veri = f.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"DocuSign {e.code}: {e.read().decode(errors='replace')[:300]}")
    return veri if ham else json.loads(veri or b"{}")


def zarf(konu, pdf, dosya_adi, imzalayan_ad, imzalayan_eposta):
    """DocuSign zarf gövdesi (saf). İmza alanı çapaya; çapa yoksa yok sayılır ve imzalayan serbest imzalar."""
    return {
        "emailSubject": f"İmzanız için: {konu}"[:100],
        "emailBlurb": "Teklifimizi inceleyip imzalamanızı rica ederiz.",
        "documents": [{"documentBase64": base64.b64encode(pdf).decode(), "name": dosya_adi, "fileExtension": "pdf",
                       "documentId": "1"}],
        "recipients": {"signers": [{
            "email": imzalayan_eposta, "name": imzalayan_ad, "recipientId": "1", "routingOrder": "1",
            "tabs": {"signHereTabs": [{"anchorString": CAPA, "anchorUnits": "pixels", "anchorXOffset": "0",
                                       "anchorYOffset": "0", "anchorIgnoreIfNotPresent": "true"}]}}]},
        "status": "sent",
    }


def dosya_listesi(dosyalar):
    """FILES alanı okunduğu biçimle (url, uzantı) geri yazılamaz; yazmak için yalnız kimlik ve ad (saf)."""
    return [{"fileId": d["fileId"], "label": d.get("label") or ""} for d in (dosyalar or []) if d.get("fileId")]


def kontrol_dilimi(simdi_tr, son_dilim):
    """Kontrol saati geldiyse bu dilimin anahtarı (aynı dilimde bir kez), değilse None (saf)."""
    if simdi_tr.hour not in KONTROL_SAATLERI:
        return None
    dilim = simdi_tr.strftime("%Y-%m-%d %H")
    return None if dilim == son_dilim else dilim


def _simdi():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gonder(t, a):
    if t.get("esignEnvelopeId") and t.get("esignStatus") in BEKLEYEN + ("COMPLETED",):
        return {"esignMessage": "Bu teklif zaten imzaya gönderildi."}
    if t.get("approverId") and not t.get("approvedById"):
        return {"esignMessage": "Marj kuralı gereği önce onay gerekiyor; onaydan sonra gönderin."}
    if not t.get("signerId"):
        return {"esignMessage": "İmzalayacak kişi seçilmedi."}
    kisi = (api("GET", f"/rest/people/{t['signerId']}") or {}).get("person") or {}
    eposta = (kisi.get("emails") or {}).get("primaryEmail")
    if not eposta:
        return {"esignMessage": "İmzalayacak kişinin e-posta adresi yok."}
    pdfler = [d for d in (t.get("documents") or []) if (d.get("label") or "").lower().endswith(".pdf")]
    if not pdfler:
        return {"esignMessage": "Önce PDF üretin (Belge üret → PDF)."}
    pdf = dosya_indir(pdfler[-1]["url"])
    ad = " ".join(x for x in ((kisi.get("name") or {}).get("firstName"), (kisi.get("name") or {}).get("lastName")) if x) or eposta
    z = ds(a, "POST", "/envelopes", zarf(t.get("name") or "Teklif", pdf, pdfler[-1]["label"], ad, eposta))
    log(f"{t.get('name')}: DocuSign zarfı gönderildi ({ad})")
    yama = {"esignEnvelopeId": z.get("envelopeId"), "esignStatus": "SENT", "esignSentAt": _simdi(),
            "esignMessage": f"{ad} ({eposta}) kişisine imzaya gönderildi."}
    if t.get("status") in ("DRAFT", "APPROVED", None):
        yama["status"] = "SENT"   # teklif gönderildi: rakamlar fırsata (TEKLIF paketi)
    return yama


def durum_kontrol(t, a):
    z = ds(a, "GET", f"/envelopes/{t['esignEnvelopeId']}")
    yeni = DURUM.get((z.get("status") or "").lower())
    yama = {"esignCheckedAt": _simdi()}
    if not yeni or yeni == t.get("esignStatus"):
        return yama
    yama["esignStatus"] = yeni
    if yeni == "COMPLETED":
        pdf = ds(a, "GET", f"/envelopes/{t['esignEnvelopeId']}/documents/combined", ham=True)
        ad = f"{(t.get('name') or 'Teklif')} - imzalı.pdf".replace("/", "-")
        mevcut = dosya_listesi(t.get("documents"))
        if not any(d["label"] == ad for d in mevcut):
            mevcut = mevcut[-3:] + [dosya_yukle("quote", "documents", ad, pdf)]   # alan en fazla 4 dosya
        yama.update({"documents": mevcut, "status": "ACCEPTED",
                     "esignMessage": "İmzalandı; imzalı PDF teklife ve fırsatın Onaylanan Teklif alanına eklendi."})
        if t.get("opportunityId"):
            firsat_ilerlet(t["opportunityId"], ad, pdf)
        log(f"{t.get('name')}: imzalandı")
    elif yeni == "DECLINED":
        yama["status"] = "REJECTED"
        yama["esignMessage"] = "İmzalayan kişi reddetti."
        log(f"{t.get('name')}: imza reddedildi")
    elif yeni == "VOIDED":
        yama["esignMessage"] = "Zarf DocuSign'da iptal edildi."
    return yama


def firsat_ilerlet(firsat_id, ad, pdf):
    """İmzalı teklif (kullanıcı kararı 14 Kas): fırsatın Onaylanan Teklif'i ve Sipariş / Onay Dokümanı olur; fırsat açık
    aşamadaysa Audit'e geçer → SATIS_SURECI sözleşmeyi (İmzada) açar, belgeleri kopyalar, kapanış tarihini yazar.
    Idempotent: aynı adlı dosya ikinci kez eklenmez, Audit ve sonrasındaki fırsatın aşamasına dokunulmaz."""
    f = (api("GET", f"/rest/opportunities/{firsat_id}") or {}).get("opportunity") or {}
    if not f:
        return
    yama = {}
    for alan in ("approvedProposal", "orderDocument"):
        mevcut = dosya_listesi(f.get(alan))
        if not any(d["label"] == ad for d in mevcut):
            yama[alan] = mevcut + [dosya_yukle("opportunity", alan, ad, pdf)]
    if f.get("stage") in OPEN:
        yama["stage"] = "AUDIT"
    if yama:
        api("PATCH", f"/rest/opportunities/{firsat_id}", yama)
        log(f"{f.get('name')}: imzalı teklif fırsata eklendi" + (" ve Audit'e geçti (sözleşme süreci)" if "stage" in yama else ""))


def teklif_isle(anahtar):
    tid = anahtar.split(":", 1)[1]
    t = (api("GET", f"/rest/quotes/{tid}") or {}).get("quote")
    if not t or not t.get("esignRequest"):
        return
    istek = t["esignRequest"]
    try:
        a = ayar()
        yama = gonder(t, a) if istek == "SEND" else (durum_kontrol(t, a) if t.get("esignEnvelopeId")
                                                     else {"esignMessage": "Henüz imzaya gönderilmedi."})
    except AyarYok as e:
        yama = {"esignMessage": str(e)}
    except Exception as e:   # noqa: BLE001 — DocuSign hatası teklifi kilitlemesin
        log(f"HATA DocuSign: {e}")
        yama = {"esignStatus": "ERROR" if istek == "SEND" else t.get("esignStatus"), "esignMessage": f"DocuSign hatası: {str(e)[:250]}"}
    yama["esignRequest"] = None
    api("PATCH", f"/rest/quotes/{tid}", yama)


def zamanli_kontrol(anahtar=None):
    """Yarım saatte bir çağrılır; yalnız 00, 08, 16 dilimlerinde bekleyen zarfları sorar."""
    global _son_dilim
    dilim = kontrol_dilimi(dt.datetime.now(TR), _son_dilim)
    if not dilim:
        return
    _son_dilim = dilim
    try:
        a = ayar()
    except AyarYok:
        return
    for t in liste("quotes", filtre="esignStatus[in]:[SENT,DELIVERED]"):
        try:
            yama = durum_kontrol(t, a)
            api("PATCH", f"/rest/quotes/{t['id']}", yama)
        except Exception as e:   # noqa: BLE001
            log(f"HATA DocuSign durum ({t.get('name')}): {e}")


# ---------------- paket tanımı ----------------
AD = "IMZA"
OLAYLAR = [(("quote.updated",), lambda ad, kayit: [f"imza:{kayit['id']}"] if kayit.get("esignRequest") and kayit.get("id") else [])]
ISLER = {"imza": teklif_isle, "imza_kontrol": zamanli_kontrol}
PERIYODIK = ["imza_kontrol"]
