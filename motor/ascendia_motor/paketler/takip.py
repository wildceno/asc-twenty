"""Paket TAKIP: son temas, temassız gün, planlı görüşme ve temassızlık takibi (görevi Takip iş akışı açar)."""
import datetime as dt

from ascendia_motor.cekirdek.ayar import OPEN, TR
from ascendia_motor.cekirdek.donemler import AY_TAM
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.twenty import api, gql, liste


LEAD_ASAMALARI = {"LEAD_GEN", "LEAD_IN_TOUCH"}


SORUMLU_SIRASI = {"lead": ["bdmId", "ownerId", "accountManagerId", "sdrId", "preSalesId"],
                  "satis": ["ownerId", "accountManagerId", "sdrId", "bdmId", "preSalesId"]}


TAKIP_ALANLARI = ("lastTouchAt", "daysWithoutTouch", "followUpStatus", "followUpDueAt", "followUpTitle",
                  "followUpAssigneeId")


def _an(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _gun_metni(an):
    t = an.astimezone(TR)
    return f"{t.day} {AY_TAM[t.month - 1]} {t.hour:02d}:{t.minute:02d}"


def takip_hesapla():
    """Açık fırsatlarda Son Temas / Temassız Gün ve Takip Durumu'nu hesaplar; görevi Takip iş akışı açar.
    Planlı görüşme: ileri tarihli Temas → o tarihe görev (o gün açık görev yoksa). Temassızlık: eşik aşıldı ve ileri
    tarihli açık görev, açık takip görevi ya da planlı görüşme yok → bugün 09:00'a görev."""
    kurallar = {k["stage"]: k.get("days") for k in liste("followUpRules") if k.get("stage")}
    simdi = dt.datetime.now(dt.timezone.utc)
    bugun = simdi.astimezone(TR).date()
    temas = {}
    for t in liste("touchpoints"):
        if t.get("opportunityId") and t.get("occurredAt"):
            temas.setdefault(t["opportunityId"], []).append(_an(t["occurredAt"]))
    gorev = {g["id"]: g for g in liste("tasks")}
    firsat_gorevleri = {}
    for h in liste("taskTargets"):
        if h.get("targetOpportunityId") and h.get("taskId") in gorev:
            firsat_gorevleri.setdefault(h["targetOpportunityId"], []).append(gorev[h["taskId"]])
    for o in liste("opportunities"):
        yeni = dict.fromkeys(TAKIP_ALANLARI)
        if o.get("stage") in OPEN:
            anlar = temas.get(o["id"], [])
            gecmis = [a for a in anlar if a <= simdi]
            ileri = sorted(a for a in anlar if a > simdi)
            son = max(gecmis) if gecmis else None
            referans = son or _an(o["createdAt"])   # hiç temas yoksa fırsatın açıldığı günden sayılır
            gun = (bugun - referans.astimezone(TR).date()).days
            yeni.update(lastTouchAt=son.isoformat().replace("+00:00", "Z") if son else None, daysWithoutTouch=gun)
            acik = [g for g in firsat_gorevleri.get(o["id"], []) if g.get("status") != "DONE"]
            acik_gunler = {_an(g["dueAt"]).astimezone(TR).date() for g in acik if g.get("dueAt")}
            sira = SORUMLU_SIRASI["lead" if o["stage"] in LEAD_ASAMALARI else "satis"]
            sorumlu = next((o[a] for a in sira if o.get(a)), None)
            durum = tarih = baslik = None
            for a in ileri:
                if a.astimezone(TR).date() not in acik_gunler:
                    durum, tarih, baslik = "MEETING", a, f"Görüşme: {o['name']} — {_gun_metni(a)}"
                    break
            esik = kurallar.get(o["stage"])
            if not durum and esik and gun >= esik and not ileri \
                    and not any(d >= bugun for d in acik_gunler) \
                    and not any((g.get("title") or "").startswith("Takip:") for g in acik):
                durum = "INACTIVITY"
                tarih = dt.datetime.combine(bugun, dt.time(9, 0), TR)
                baslik = f"Takip: {o['name']} — {gun} gündür temas yok"
            if durum and not sorumlu:
                log(f"takip: {o['name']} için sorumlu yok (sahiplik alanları boş), görev açılamadı")
                durum = None
            if durum:
                yeni.update(followUpStatus=durum, followUpTitle=baslik, followUpAssigneeId=sorumlu,
                            followUpDueAt=tarih.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"))
        fark = {k: v for k, v in yeni.items() if not ayni_takip(o.get(k), v)}
        if fark:
            api("PATCH", f"/rest/opportunities/{o['id']}", fark)
            if "followUpStatus" in fark and fark["followUpStatus"]:
                log(f"takip: {o['name']} → {fark['followUpStatus']} ({yeni['followUpTitle']})")


def ayni_takip(a, b):
    """Tarih alanlarında API'nin döndürdüğü biçim farkını (milisaniye) yok sayar."""
    if isinstance(a, str) and isinstance(b, str) and a[:4].isdigit() and "T" in a and "T" in b:
        return _an(a) == _an(b)
    return a == b


# ---------------- rakip sözleşme yenileme (liste 11; metadata/18_rakip_yenileme.py) ----------------
def rakip_yenileme_hatirlat():
    """Rakip Hizmeti'nin Sözleşme Bitişi'ne CRM Ayarı'ndaki gün sayısı (varsayılan 90) kadar kala, o bitiş tarihi için bir
    kez görev: şirketin Account Manager'ı → Pre-sales → Admin. Fırsat açılmaz (kullanıcı, 13 Kas). Bitiş tarihi
    değişirse (ör. rakiple yenilendi) yeni tarih için yeniden hatırlatılır. Geçmiş bitişler hatırlatılmaz."""
    bugun = dt.datetime.now(TR).date()
    sirketler = {}
    adminler = None
    for r in liste("competitorServices"):
        bitis = (r.get("contractEnd") or "")[:10]
        if not bitis or (r.get("renewalRemindedFor") or "")[:10] == bitis:
            continue
        kalan = (dt.date.fromisoformat(bitis) - bugun).days
        if kalan < 0 or kalan > Durum.rakip_gun or not r.get("companyId"):
            continue
        s = sirketler.get(r["companyId"]) or (api("GET", f"/rest/companies/{r['companyId']}") or {}).get("company") or {}
        sirketler[r["companyId"]] = s
        sorumlu = s.get("accountManagerId") or s.get("preSalesId")
        if not sorumlu:
            if adminler is None:
                adminler = next((([m["id"] for m in x.get("workspaceMembers") or []]) for x in
                                 gql("{ getRoles { label workspaceMembers { id } } }")["getRoles"] if x["label"] == "Admin"), [])
            sorumlu = adminler[0] if adminler else None
        if not sorumlu:
            log(f"rakip yenileme: {s.get('name')} için sorumlu yok, görev açılamadı")
            continue
        tarih = ".".join(reversed(bitis.split("-")))
        neyi = " · ".join(x for x in (r.get("competitor"), r.get("service")) if x)
        g = api("POST", "/rest/tasks", {
            "title": f"Rakip sözleşmesi bitiyor: {s.get('name')} — {neyi} ({tarih})", "status": "TODO",
            "assigneeId": sorumlu, "dueAt": dt.datetime.combine(bugun, dt.time(9, 0), TR).astimezone(dt.timezone.utc)
            .isoformat().replace("+00:00", "Z"),
            "bodyV2": {"markdown": f"Rakipten alınan hizmetin sözleşmesi {tarih} tarihinde bitiyor ({kalan} gün). "
                                   "Fırsat açmayı değerlendir."}})["createTask"]
        api("POST", "/rest/taskTargets", {"taskId": g["id"], "targetCompanyId": r["companyId"]})
        api("POST", "/rest/taskTargets", {"taskId": g["id"], "targetCompetitorServiceId": r["id"]})
        api("PATCH", f"/rest/competitorServices/{r['id']}", {"renewalRemindedFor": bitis})
        log(f"rakip yenileme: {s.get('name')} — {neyi}, {kalan} gün kala görev açıldı")


# ---------------- paket tanımı ----------------
AD = "TAKIP"
OLAYLAR = [(("touchpoint.", "task.", "taskTarget.", "followUpRule.", "opportunity."), lambda ad, kayit: ["takip"]),
           (("competitorService.created", "competitorService.updated", "crmSetting."), lambda ad, kayit: ["rakip"])]
ISLER = {"takip": lambda anahtar: takip_hesapla(), "rakip": lambda anahtar: rakip_yenileme_hatirlat()}
BIRLESTIRME = {"takip": 60, "rakip": 30}   # tam tarama: olay yağmurunda birleştirilir
PERIYODIK = ["takip", "rakip"]             # temassız gün ve kalan gün zamanla değişir
