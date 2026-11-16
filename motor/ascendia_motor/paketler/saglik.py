"""Paket SAGLIK: sağlık turu, Sistem Durumu ve Sistem Alarmları, Admin görevi, crm-support portalına olaylar; takılma bekçisi."""
import collections
import datetime as dt
import json
import os
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

from ascendia_motor.cekirdek.ayar import TR
from ascendia_motor.cekirdek.gunluk import SAGLIK, log, oku
from ascendia_motor.cekirdek.twenty import api, gql, liste


PORTAL_URL = os.environ.get("PORTAL_URL", "").rstrip("/")


PORTAL_KEY_FILE = os.environ.get("PORTAL_KEY_FILE", "/run/sirlar/portal_key")


KURULUM = os.environ.get("KURULUM_ADI", "kurulum")


CALISMA_ALANI = os.environ.get("CALISMA_ALANI", "")


TAKIP_IS_AKISI = "Takip görevleri"


_portal_kuyruk = collections.deque(maxlen=200)


def _simdi_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def olay(tur, kaynak, kod=None, seviye=None, baslik=None, ayrinti=None, durum=None):
    """Portal olay sözleşmesi (sürüm 1). Kişi verisi taşınmaz."""
    return {"surum": 1, "kurulum": KURULUM, "calisma_alani": CALISMA_ALANI, "tur": tur, "kaynak": kaynak.lower(),
            "kod": kod, "seviye": seviye.lower() if seviye else None,
            "tekil_anahtar": f"{KURULUM}/{kaynak.lower()}/{kod}" if kod else None,
            "baslik": baslik, "ayrinti": ayrinti, "zaman": _simdi_iso(), "durum": durum}


def portal_gonder(o):
    """Adres ya da anahtar yoksa kapalı. Alarm ve düzeldi olayları erişilemezse kuyrukta bekler; kalp atışı biriktirilmez.
    Gönderim hataları HATA diye yazılmaz (kendi alarmını üretip döngüye girmesin)."""
    anahtar = oku(PORTAL_KEY_FILE) if PORTAL_URL and os.path.exists(PORTAL_KEY_FILE) else ""
    if not PORTAL_URL or not anahtar:
        SAGLIK["portal"] = "kapalı (adres ya da anahtar yok)"
        return
    if o["tur"] != "kalp_atisi":
        _portal_kuyruk.append(o)
    for x in list(_portal_kuyruk) + ([o] if o["tur"] == "kalp_atisi" else []):
        try:
            urllib.request.urlopen(urllib.request.Request(
                PORTAL_URL + "/api/v1/olay", method="POST", data=json.dumps(x).encode(),
                headers={"Authorization": "Bearer " + anahtar, "Content-Type": "application/json"}), timeout=10)
            if x in _portal_kuyruk:
                _portal_kuyruk.remove(x)
            SAGLIK["portal"] = "son gönderim " + dt.datetime.now(TR).strftime("%d.%m %H:%M")
        except Exception as e:
            SAGLIK["portal"] = f"gönderilemedi ({len(_portal_kuyruk)} bekliyor): {str(e)[:120]}"
            log("portal: gönderilemedi,", str(e)[:120])
            break


def admin_uyeler():
    for r in gql("{ getRoles { label workspaceMembers { id } } }")["getRoles"]:
        if r["label"] == "Admin":
            return [m["id"] for m in r.get("workspaceMembers") or []]
    return []


def alarm_ac(kod, kaynak, seviye, baslik, ayrinti):
    """Aynı sorun (Tekil Anahtar) açıksa yalnız son görülme ve tekrar güncellenir; yeni alarmda kritikse Admin'e tek görev."""
    anahtar = f"{KURULUM}/{kaynak.lower()}/{kod}"
    acik = [a for a in liste("systemAlarms", filtre=f"uniqueKey[eq]:{anahtar}") if a.get("alarmStatus") == "OPEN"]
    if acik:
        a = acik[0]
        api("PATCH", f"/rest/systemAlarms/{a['id']}", {"lastSeenAt": _simdi_iso(), "detail": ayrinti,
                                                        "repeatCount": (a.get("repeatCount") or 1) + 1})
        return
    kayit = api("POST", "/rest/systemAlarms", {
        "name": baslik, "code": kod, "source": kaynak, "severity": seviye, "alarmStatus": "OPEN", "uniqueKey": anahtar,
        "detail": ayrinti, "firstSeenAt": _simdi_iso(), "lastSeenAt": _simdi_iso(), "repeatCount": 1})["createSystemAlarm"]
    if seviye == "KRITIK":
        adminler = admin_uyeler()
        if adminler:
            g = api("POST", "/rest/tasks", {"title": f"Sistem alarmı: {baslik}", "status": "TODO", "assigneeId": adminler[0],
                                           "dueAt": _simdi_iso(), "bodyV2": {"markdown": ayrinti or ""}})["createTask"]
            api("PATCH", f"/rest/systemAlarms/{kayit['id']}", {"taskId": g["id"]})
    portal_gonder(olay("alarm", kaynak, kod, seviye, baslik, ayrinti))
    log(f"alarm açıldı: {kod} ({seviye}) {baslik}")


def alarm_kapat(kod, kaynak):
    anahtar = f"{KURULUM}/{kaynak.lower()}/{kod}"
    for a in liste("systemAlarms", filtre=f"uniqueKey[eq]:{anahtar}"):
        if a.get("alarmStatus") != "OPEN":
            continue
        api("PATCH", f"/rest/systemAlarms/{a['id']}", {"alarmStatus": "RESOLVED", "resolvedAt": _simdi_iso()})
        if a.get("taskId"):
            try:
                api("PATCH", f"/rest/tasks/{a['taskId']}", {"status": "DONE"})
            except Exception:
                pass   # görev silinmiş olabilir
        portal_gonder(olay("cozuldu", kaynak, kod, baslik=a.get("name")))
        log(f"alarm düzeldi: {kod}")


def durum_kaydi():
    r = liste("systemStatuses", limit=1)
    return r[0] if r else api("POST", "/rest/systemStatuses", {"name": "Sistem"})["createSystemStatus"]


def saglik_turu():
    """5 dakikada bir: kontroller → alarm aç/kapat, Sistem Durumu kaydı, portala kalp atışı."""
    simdi = time.time()
    simdi_tr = dt.datetime.now(TR)
    try:
        d = durum_kaydi()
    except Exception as e:
        SAGLIK["twenty_yok"] = True
        portal_gonder(olay("alarm", "TWENTY", "TWENTY_ERISILEMIYOR", "KRITIK", "Hesap motoru Twenty'ye ulaşamıyor", str(e)[:300]))
        return
    if SAGLIK["twenty_yok"]:
        SAGLIK["twenty_yok"] = False
        portal_gonder(olay("cozuldu", "TWENTY", "TWENTY_ERISILEMIYOR", baslik="Hesap motoru Twenty'ye ulaşamıyor"))
    saat = [t for t in SAGLIK["hatalar"] if simdi - t < 3600]
    gun = [t for t in SAGLIK["hatalar"] if simdi - t < 86400]
    son_hata = SAGLIK["son_hata"]
    kur = liste("exchangeRates", sira="rateDate[DescNullsLast]", limit=1)
    son_kur = (kur[0].get("rateDate") or "")[:10] if kur else None
    kosu = liste("workflowRuns", filtre=f"name[like]:%{TAKIP_IS_AKISI}%", sira="createdAt[DescNullsLast]", limit=1)
    kosu = kosu[0] if kosu else {}
    son_yedek = d.get("lastBackupAt")
    yedek_yas = (simdi - dt.datetime.fromisoformat(son_yedek.replace("Z", "+00:00")).timestamp()) / 3600 if son_yedek else None

    kontroller = [
        ("MOTOR_HATA", "MOTOR", "UYARI", bool(saat), f"Hesap motorunda son 1 saatte {len(saat)} hata",
         son_hata[1] if son_hata else ""),
        # TCMB hafta sonu ve resmî tatilde kur yayımlamaz: hafta içi 16:35'ten sonra günün kuru yoksa uyarı
        ("KUR_ALINAMADI", "KUR", "UYARI",
         simdi_tr.weekday() < 5 and simdi_tr.strftime("%H:%M") >= "16:35" and son_kur != simdi_tr.date().isoformat(),
         "Günün TCMB kuru alınamadı", f"Son kur tarihi: {son_kur or 'yok'}. Resmî tatilde TCMB kur yayımlamaz."),
        ("YEDEK_YOK", "YEDEK", "KRITIK", yedek_yas is None or yedek_yas > 26, "Son 26 saatte başarılı yedek yok",
         f"Son yedek: {son_yedek or 'kayıt yok'}"),
        ("IS_AKISI_HATA", "IS_AKISI", "UYARI", kosu.get("status") == "FAILED", "Takip iş akışının son çalışması başarısız",
         f"{kosu.get('name')} · {kosu.get('startedAt')}"),
    ]
    for kod, kaynak, seviye, sorun, baslik, ayrinti in kontroller:
        if sorun:
            alarm_ac(kod, kaynak, seviye, baslik, ayrinti)
        else:
            alarm_kapat(kod, kaynak)
    alarm_kapat("MOTOR_TAKILDI", "MOTOR")   # bu tur çalışıyorsa motor yeniden başlamış ve ilerliyor

    yama = {"lastHeartbeatAt": _simdi_iso(),
            "motorStartedAt": dt.datetime.fromtimestamp(SAGLIK["baslangic"], dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "lastRateDate": son_kur, "lastWorkflowRunAt": kosu.get("startedAt"), "lastWorkflowStatus": kosu.get("status"),
            "errors24h": len(gun), "lastError": son_hata[1][:900] if son_hata else None,
            "lastErrorAt": dt.datetime.fromtimestamp(son_hata[0], dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if son_hata else None,
            "portalStatus": SAGLIK["portal"]}
    api("PATCH", f"/rest/systemStatuses/{d['id']}", yama)
    portal_gonder(olay("kalp_atisi", "MOTOR", durum={"son_kur": son_kur, "son_yedek": son_yedek,
                                                       "is_akisi": kosu.get("status"), "is_akisi_zamani": kosu.get("startedAt"),
                                                       "hata_24s": len(gun)}))


def takilma_kontrol():
    """Kuyruk bir işte (tümü 60, diğerleri 15 dk) ya da zamanlayıcı 45 dk ilerlemezse süreç kapanır; Docker yeniden başlatır."""
    simdi, neden = time.time(), None
    if SAGLIK["mesgul_basi"]:
        sinir = 3600 if SAGLIK["mesgul_is"] == "hepsi" else 900
        if simdi - SAGLIK["mesgul_basi"] > sinir:
            neden = f"iş kuyruğu {int((simdi - SAGLIK['mesgul_basi']) / 60)} dakikadır '{SAGLIK['mesgul_is']}' işinde"
    if simdi - SAGLIK["zamanlayici_son"] > 2700:
        neden = f"zamanlayıcı {int((simdi - SAGLIK['zamanlayici_son']) / 60)} dakikadır ilerlemiyor"
    if neden:
        log("HATA motor takıldı:", neden, "— yeniden başlatılıyor")
        try:
            alarm_ac("MOTOR_TAKILDI", "MOTOR", "KRITIK", "Hesap motoru takıldı ve yeniden başlatıldı", neden)
        except Exception:
            pass
        os._exit(1)


def bekci():
    son_tur = 0.0
    while True:
        time.sleep(60)
        try:
            takilma_kontrol()
        except Exception:
            log("HATA bekçi", traceback.format_exc(limit=2))
        from ascendia_motor.cekirdek import paketler   # döngüsel içe aktarmayı önlemek için burada
        if time.time() - son_tur >= 300 and paketler.acik(AD):
            son_tur = time.time()
            try:
                saglik_turu()
            except Exception:
                log("HATA sağlık turu", traceback.format_exc(limit=2))


# ---------------- paket tanımı ----------------
AD = "SAGLIK"   # sağlık turu ve alarmlar; takılma bekçisi paketten bağımsız her zaman çalışır
