"""Paket EPOSTA (liste 19; kullanıcı kararları 14-15 Kas 2026): eşitlenen e-posta ve takvimden Temas, cevap görevi.

Takvim (15 Kas): müşteri kişisinin (CRM'de kişi, ekipten değil) katıldığı her etkinlik bir Temas: Tür Toplantı, tarih =
başlangıç, Yön = biz düzenlediysek Giden, karşı taraf düzenlediyse Gelen; kişi, şirket, şirketin tek açık fırsatı, Yapan
= ekipten katılımcı. Saat / başlık değişirse Temas güncellenir, etkinlik iptal edilince Temas silinir. İleri tarihli
toplantı TAKIP paketinin "planlı görüşme" kuralını besler.

- Her posta (gelen ve giden) bir Temas: Tür E-posta, Yön Gelen / Giden, kişi, şirket, şirketin tek açık fırsatı,
  Yapan = posta kutusunun sahibi. Karşı taraf CRM'de kişi değilse (Twenty kişi oluşturmadıysa: kişisel / otomatik
  adres, hesap ayarlarına bırakıldı) temas ve görev açılmaz. İki taraf da ekipten ise (iç yazışma) açılmaz.
- Gelen postada konuşma başına tek açık "Cevapla: <konu>" görevi (sahibine; süre hedefi yok). Aynı konuşmada yeni
  gelen posta görevin notuna eklenir.
- Giden posta aynı konuşmadaki açık görevi kapatır; cevaplanmamış gelen postaların Temas'ına cevap süresi (saat).
Posta kutusunun sahibi: katılımcının Twenty'deki üye eşleşmesi; yoksa Ekip → Eşitlenen Posta Adresleri.
(Bağlı hesap / kanal bu sürümde API anahtarıyla okunamıyor — 14 Kas'ta denendi.)
"""
import datetime as dt

from ascendia_motor.cekirdek.ayar import OPEN, TR
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.metin import zengin_metin
from ascendia_motor.cekirdek.twenty import api, liste

GERI_GUN = 7          # her turda son 7 günün postasına bakılır (işlenenler emailMessageId ile atlanır)
ALICI_ROLLERI = ("TO", "CC", "BCC")


def _an(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def sahip_ve_karsi(yon, katilimcilar, kutu_sahipleri):
    """(posta kutusu sahibi üye id, karşı taraf katılımcısı) — saf.
    yon: INCOMING / OUTGOING; katilimcilar: [{'role','handle','personId','workspaceMemberId'}];
    kutu_sahipleri: {adres (küçük harf): üye id} (Ekip → Eşitlenen Posta Adresleri)."""
    def uye(k):
        return k.get("workspaceMemberId") or kutu_sahipleri.get((k.get("handle") or "").strip().lower())
    if yon == "INCOMING":
        biz = [k for k in katilimcilar if k.get("role") in ALICI_ROLLERI and uye(k)]
        karsi = [k for k in katilimcilar if k.get("role") == "FROM" and not uye(k)]
    else:
        biz = [k for k in katilimcilar if k.get("role") == "FROM" and uye(k)]
        karsi = [k for k in katilimcilar if k.get("role") in ALICI_ROLLERI and not uye(k) and k.get("personId")]
    return (uye(biz[0]) if biz else None), (karsi[0] if karsi and karsi[0].get("personId") else None)


def cevap_saatleri(gelenler, giden_an):
    """Cevaplanmamış gelen temaslara cevap süresi (saat, 1 ondalık) — saf. gelenler: [(temas id, gelen an)]."""
    return {tid: round((giden_an - an).total_seconds() / 3600, 1) for tid, an in gelenler if an <= giden_an}


def _kutu_sahipleri():
    out = {}
    for e in liste("teamMembers"):
        for adres in (e.get("mailboxEmails") or "").replace(";", ",").split(","):
            if adres.strip() and e.get("memberId"):
                out[adres.strip().lower()] = e["memberId"]
    return out


def _tek_acik_firsat(sirket_id):
    if not sirket_id:
        return None
    acik = [f for f in liste("opportunities", filtre=f"companyId[eq]:{sirket_id}") if f.get("stage") in OPEN]
    return acik[0]["id"] if len(acik) == 1 else None


def _hedefler(gorev_id, kisi_id, sirket_id, firsat_id):
    for alan, deger in (("targetPersonId", kisi_id), ("targetCompanyId", sirket_id), ("targetOpportunityId", firsat_id)):
        if deger:
            api("POST", "/rest/taskTargets", {"taskId": gorev_id, alan: deger})


def isle(anahtar=None):
    bas = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=GERI_GUN)).strftime("%Y-%m-%dT%H:%M:%SZ")   # Twenty küsurat kabul etmez
    iliskiler = liste("messageChannelMessageAssociations", filtre=f"createdAt[gte]:{bas}")
    if not iliskiler:
        return
    islenmis = {t["emailMessageId"] for t in liste("touchpoints", filtre=f"createdAt[gte]:{bas}") if t.get("emailMessageId")}
    yeni = [a for a in iliskiler if a.get("messageId") and a["messageId"] not in islenmis]
    if not yeni:
        return
    sahipler = _kutu_sahipleri()
    postalar = []
    for a in {a["messageId"]: a for a in yeni}.values():   # aynı posta iki kanalda olabilir: bir kez
        m = (api("GET", f"/rest/messages/{a['messageId']}") or {}).get("message")
        if m:
            postalar.append((a, m))
    for a, m in sorted(postalar, key=lambda x: x[1].get("receivedAt") or ""):
        kat = liste("messageParticipants", filtre=f"messageId[eq]:{m['id']}")
        sahip, karsi = sahip_ve_karsi(a.get("direction"), kat, sahipler)
        if not karsi:
            continue   # iç yazışma ya da CRM'de kişisi olmayan adres
        kisi = (api("GET", f"/rest/people/{karsi['personId']}") or {}).get("person") or {}
        sirket_id = kisi.get("companyId")
        firsat_id = _tek_acik_firsat(sirket_id)
        konu = (m.get("subject") or "(konu yok)").strip()
        gelen = a.get("direction") == "INCOMING"
        konusma = m.get("messageThreadId")
        api("POST", "/rest/touchpoints", {
            "name": f"E-posta: {konu}"[:250], "channel": "EMAIL", "direction": "INBOUND" if gelen else "OUTBOUND",
            "occurredAt": m.get("receivedAt"), "summary": konu, "personId": kisi.get("id"), "companyId": sirket_id,
            "opportunityId": firsat_id, "performedById": sahip, "emailMessageId": m["id"], "emailThreadId": konusma})
        log(f"e-posta teması: {'gelen' if gelen else 'giden'} · {konu}")
        acik_gorevler = [g for g in liste("tasks", filtre=f"emailThreadId[eq]:{konusma}") if g.get("status") != "DONE"] if konusma else []
        zaman = _an(m["receivedAt"]).astimezone(TR).strftime("%d.%m.%Y %H:%M") if m.get("receivedAt") else ""
        satir = f"- {zaman} · {karsi.get('displayName') or karsi.get('handle')} · {konu}"
        if gelen:
            if acik_gorevler:
                g = acik_gorevler[0]
                md = (((g.get("bodyV2") or {}).get("markdown")) or "").rstrip() + "\n" + satir
                api("PATCH", f"/rest/tasks/{g['id']}", {"bodyV2": zengin_metin(md)})
            else:
                g = api("POST", "/rest/tasks", {"title": f"Cevapla: {konu}"[:250], "status": "TODO", "assigneeId": sahip,
                                                "emailThreadId": konusma,
                                                "bodyV2": zengin_metin("Cevap bekleyen e-posta:\n" + satir)})["createTask"]
                _hedefler(g["id"], kisi.get("id"), sirket_id, firsat_id)
                log(f"cevap görevi açıldı: {konu}")
        elif m.get("receivedAt"):
            for g in acik_gorevler:
                api("PATCH", f"/rest/tasks/{g['id']}", {"status": "DONE"})
                log(f"cevap görevi kapandı (cevap gitti): {g.get('title')}")
            bekleyen = [(t["id"], _an(t["occurredAt"])) for t in liste("touchpoints", filtre=f"emailThreadId[eq]:{konusma}")
                        if t.get("direction") == "INBOUND" and t.get("responseHours") is None and t.get("occurredAt")] if konusma else []
            for tid, saat in cevap_saatleri(bekleyen, _an(m["receivedAt"])).items():
                api("PATCH", f"/rest/touchpoints/{tid}", {"responseHours": saat})


def toplanti_taraflari(katilimcilar, kutu_sahipleri):
    """(ekipten katılımcı üye id, düzenleyen bizden mi, karşı taraf kişi katılımcıları) — saf."""
    def uye(k):
        return k.get("workspaceMemberId") or kutu_sahipleri.get((k.get("handle") or "").strip().lower())
    biz = [k for k in katilimcilar if uye(k)]
    duzenleyen = next((k for k in katilimcilar if k.get("isOrganizer")), None)
    sahip = uye(duzenleyen) if duzenleyen and uye(duzenleyen) else (uye(biz[0]) if biz else None)
    karsi, gorulen = [], set()
    for k in katilimcilar:
        if k.get("personId") and not uye(k) and k["personId"] not in gorulen:
            gorulen.add(k["personId"])
            karsi.append(k)
    return sahip, bool(duzenleyen and uye(duzenleyen)), karsi


def takvim_isle(anahtar=None):
    bas = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    etkinlikler = liste("calendarEvents", filtre=f"startsAt[gte]:{bas}")
    if not etkinlikler:
        return
    mevcut = {t["calendarEventId"]: t for t in liste("touchpoints", filtre="calendarEventId[is]:NOT_NULL")}
    sahipler = _kutu_sahipleri()
    for e in etkinlikler:
        t = mevcut.get(e["id"])
        if e.get("isCanceled"):
            if t:
                api("DELETE", f"/rest/touchpoints/{t['id']}")
                log(f"toplantı iptal, temas silindi: {e.get('title')}")
            continue
        sahip, biz_duzenledik, karsi = toplanti_taraflari(liste("calendarEventParticipants", filtre=f"calendarEventId[eq]:{e['id']}"), sahipler)
        if not karsi:
            continue   # müşteri kişisi yok (iç toplantı ya da CRM'de kişisi olmayan misafir)
        kisi = (api("GET", f"/rest/people/{karsi[0]['personId']}") or {}).get("person") or {}
        sirket_id = kisi.get("companyId")
        baslik = (e.get("title") or "(başlıksız)").strip()
        veri = {"name": f"Toplantı: {baslik}"[:250], "channel": "MEETING", "direction": "OUTBOUND" if biz_duzenledik else "INBOUND",
                "occurredAt": e.get("startsAt"), "summary": baslik, "personId": kisi.get("id"), "companyId": sirket_id,
                "performedById": sahip}
        if t:
            fark = {a: v for a, v in veri.items() if (t.get(a) or None) != (v or None) and a != "occurredAt"}
            if (t.get("occurredAt") or "")[:16] != (e.get("startsAt") or "")[:16]:
                fark["occurredAt"] = e.get("startsAt")
            if fark:
                api("PATCH", f"/rest/touchpoints/{t['id']}", fark)
                log(f"toplantı teması güncellendi: {baslik} ({', '.join(fark)})")
        else:
            api("POST", "/rest/touchpoints", {**veri, "opportunityId": _tek_acik_firsat(sirket_id), "calendarEventId": e["id"]})
            log(f"toplantı teması: {baslik}")


# ---------------- paket tanımı ----------------
AD = "EPOSTA"
# Yeni kişi: Twenty o adresin eski postalarını kişiye bağlar; atlanmış postalar bu kez temas / görev olur
OLAYLAR = [(("messageChannelMessageAssociation.created", "message.created", "person.created"), lambda ad, kayit: ["eposta"]),
           (("calendarEvent.", "calendarEventParticipant.", "person.created"), lambda ad, kayit: ["takvim"])]
ISLER = {"eposta": isle, "takvim": takvim_isle}
BIRLESTIRME = {"eposta": 30, "takvim": 30}


def tumunu_isle():
    isle()
    takvim_isle()
PERIYODIK = ["eposta", "takvim"]
