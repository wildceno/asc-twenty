"""Paket SATIS_SURECI: aşama kuralları, kapanış ve kilit, hesaplar (TCV, maliyet, GP, MRR/ARR, raporlama), sözleşme ve belgeler, fırsat açma denetimi."""
import datetime as dt
import time
import traceback

from ascendia_motor.cekirdek.ayar import CLOSED, DELIVERY_PHASE, ETIKET, LOCKED, LOCK_FIELDS, OPEN, TR
from ascendia_motor.cekirdek.donemler import ceyrek, donem_bul, tarih_tr
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.para import ayni, cevir, cur, micros, toplam
from ascendia_motor.cekirdek.twenty import api, dosya_kopyala, gql, liste


def son_asama(opp_id):
    r = liste("stageChanges", filtre=f"opportunityId[eq]:{opp_id}", sira="changedAt[DescNullsLast]", limit=1)
    return r[0]["toStage"] if r else None


def asama_kaydi(opp, onceki, yeni, kim, kapanis_degerleri=None):
    govde = {"name": f"{onceki or '-'} → {yeni}", "opportunityId": opp["id"], "fromStage": onceki, "toStage": yeni,
             "changedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
             "changedById": kim}
    if kapanis_degerleri is not None:
        govde["closingSnapshot"] = kapanis_degerleri
    api("POST", "/rest/stageChanges", govde)


def kapanis_degeri_tamamla(o):
    """Kilit özelliğinden önce kapanmış fırsat: mevcut değerleri son kapanış kaydına bir kez yazar."""
    kayitlar = liste("stageChanges", filtre=f"opportunityId[eq]:{o['id']}", sira="changedAt[DescNullsLast]")
    kapanis = next((k for k in kayitlar if k.get("toStage") in CLOSED
                    and (k.get("fromStage") is None or k.get("fromStage") in OPEN)), None)
    if kapanis:
        api("PATCH", f"/rest/stageChanges/{kapanis['id']}",
            {"closingSnapshot": {f: o.get(f) for f in LOCK_FIELDS}})
        log(f"{o['name']}: kapanış değerleri sonradan kaydedildi (kilit artık geçerli)")


def kapanis_degerleri(opp_id):
    r = liste("stageChanges", filtre=f"and(opportunityId[eq]:{opp_id},closingSnapshot[is]:NOT_NULL)",
              sira="changedAt[DescNullsLast]", limit=1)
    return r[0]["closingSnapshot"] if r else None


def hesapla(o):
    """Fırsatın hesaplanan alanları (yalnız değişenler döner)."""
    k = Durum.kurlar
    varsayilan = Durum.raporlama or "USD"
    yeni = {"expectedCloseQuarter": ceyrek(o.get("closeDate"))}
    ay = o.get("contractMonths")
    gelir = toplam({"tek": o.get("oneTimeFee"), "aylik": o.get("monthlyRecurring"),
                    "yillik": o.get("annualRecurring")}, ay, k, varsayilan)
    maliyet = toplam({"tek": o.get("oneTimeCost"), "aylik": o.get("monthlyCost"),
                      "yillik": o.get("annualCost")}, ay, k, varsayilan)
    if gelir:
        yeni["amount"] = cur(*gelir)
        mal_tutar = cevir(maliyet[0], maliyet[1], gelir[1], k) if maliyet else 0.0
        if mal_tutar is not None:
            yeni["totalCost"] = cur(mal_tutar, gelir[1])
            gp = gelir[0] - mal_tutar
            yeni["grossProfit"] = cur(gp, gelir[1])
            yeni["grossMarginPercent"] = round(gp / gelir[0] * 100, 1) if gelir[0] else None
            if Durum.raporlama:
                v, g = cevir(gelir[0], gelir[1], Durum.raporlama, k), cevir(gp, gelir[1], Durum.raporlama, k)
                if v is not None and g is not None:
                    yeni["amountReporting"] = cur(v, Durum.raporlama)
                    yeni["grossProfitReporting"] = cur(g, Durum.raporlama)
                    tarihler = [k[c][1] for c in {gelir[1], Durum.raporlama} - {"TRY"} if c in k]
                    yeni["fxRateDate"] = min(tarihler) if tarihler else dt.datetime.now(TR).date().isoformat()
    # MRR = aylık + yıllık ÷ 12, ARR = MRR × 12 (kullanıcı, 11 Kas)
    mrr = toplam({"aylik": o.get("monthlyRecurring"), "yillik": o.get("annualRecurring")}, 1, k, varsayilan)
    if mrr:
        yeni["mrr"], yeni["arr"] = cur(mrr[0], mrr[1]), cur(mrr[0] * 12, mrr[1])
        if Durum.raporlama:
            v = cevir(mrr[0], mrr[1], Durum.raporlama, k)
            if v is not None:
                yeni["mrrReporting"], yeni["arrReporting"] = cur(v, Durum.raporlama), cur(v * 12, Durum.raporlama)
    # Geçerli teklif varsa (liste 14a) toplam değer, maliyet ve kâr tekliften: enflasyon, fiyat artışı, kanal payı dahil
    if o.get("currentQuoteId"):
        q = (api("GET", f"/rest/quotes/{o['currentQuoteId']}") or {}).get("quote") or {}
        if q.get("status") in ("SENT", "ACCEPTED") and q.get("revenueReporting"):
            g, m, kanal, brut = (micros(q.get(a)) for a in ("revenueReporting", "costReporting", "channelShareReporting",
                                                              "grossProfitReporting"))
            pb = q["revenueReporting"].get("currencyCode")
            if g is not None:
                yeni.update({"amount": q["revenueReporting"], "amountReporting": q["revenueReporting"],
                             "totalCost": cur(((m or 0) + (kanal or 0)) / 1e6, pb),
                             "grossProfit": q.get("grossProfitReporting"), "grossProfitReporting": q.get("grossProfitReporting"),
                             "grossMarginPercent": q.get("marginPercent")})
    return {a: v for a, v in yeni.items() if not ayni(o.get(a), v)}


def kabul_edilmis_teklif(o):
    """Kabul edilmiş teklif Audit'teki Onaylanan Teklif şartını karşılar (liste 14a; PDF 15'te eklenir)."""
    return any(q.get("status") == "ACCEPTED" for q in liste("quotes", filtre=f"opportunityId[eq]:{o['id']}"))


def firsat_isle(opp_id, kayit=None):
    o = kayit
    if o is None:
        o = api("GET", f"/rest/opportunities/{opp_id}")
        o = o and o.get("opportunity")
    if not o or o.get("deletedAt"):
        return
    asama, onceki = o["stage"], son_asama(opp_id)
    kim = (o.get("updatedBy") or {}).get("workspaceMemberId") \
        if (o.get("updatedBy") or {}).get("source") == "MANUAL" else None
    yama = {}

    def geri_al(asamaya, neden):
        log(f"{o['name']}: {onceki} → {asama} geri alındı: {neden}")
        api("PATCH", f"/rest/opportunities/{opp_id}", {"stage": asamaya, "systemWarning": neden})

    # 1) Kurallara aykırı aşama değişikliği → geri al ve nedenini Sistem Uyarısı'na yaz
    uc_tamam = (o.get("contractStatus") == "SIGNED" and o.get("deliveryStatus") == "DONE"
                and o.get("invoicingStatus") == "DONE")
    if onceki in LOCKED and asama != onceki:
        return geri_al(onceki, f"{ETIKET.get(onceki, onceki)} aşamasındaki fırsat başka aşamaya geçemez.")
    if asama == "WON" and onceki and onceki != "WON" and not uc_tamam:
        return geri_al(onceki, "Won için sözleşme imzalı, teslimat ve faturalama tamamlanmış olmalı.")
    if asama in DELIVERY_PHASE | {"WON"} and (onceki is None or onceki in OPEN) \
            and not (o.get("orderDocument") and (o.get("approvedProposal") or kabul_edilmis_teklif(o))):
        return geri_al(onceki if onceki in OPEN else "COMMIT",
                       "Audit'e geçmek için Sipariş / Onay Dokümanı ve Onaylanan Teklif eklenmeli.")
    # Yeni fırsat: açan kişi o firmada yetkili mi (kullanıcı, 11 Kas)
    if onceki is None:
        firsat_acma_denetimi(o)

    # Fırsat Sahibi boşsa açan kişi (sahiplik sonra super-user'ca değiştirilir)
    acan = o.get("createdBy") or {}
    if not o.get("ownerId") and acan.get("source") == "MANUAL" and acan.get("workspaceMemberId"):
        yama["ownerId"] = acan["workspaceMemberId"]
    # Şirket sorumluları (kullanıcı, 13 Kas; liste 12): yeni fırsatta AM ve Pre-sales, fırsatta boşsa
    if onceki is None:
        yama.update(sirketten_kopyala(o, ["accountManagerId", "preSalesId"]))
    if onceki != asama and o.get("systemWarning"):

        yama["systemWarning"] = None   # kurala uygun yeni bir aşama değişikliği: eski uyarı kalkar

    # 2) Audit / Delivery / Invoice dönemi: durumlar ve aşama birbirini izler
    hedef = asama
    if asama in DELIVERY_PHASE:
        d = {"contractStatus": o.get("contractStatus") or "SIGNING",
             "deliveryStatus": o.get("deliveryStatus") or "NOT_STARTED",
             "invoicingStatus": o.get("invoicingStatus") or "NOT_STARTED"}
        if onceki != asama:
            # aşama elle değişti: ilgili durumu başlat
            if asama == "DELIVERY" and d["deliveryStatus"] == "NOT_STARTED":
                d["deliveryStatus"] = "IN_PROGRESS"
            if asama == "INVOICE" and d["invoicingStatus"] == "NOT_STARTED":
                d["invoicingStatus"] = "IN_PROGRESS"
        # aşama durumlardan türetilir: en ileri başlamış iş
        if d["invoicingStatus"] != "NOT_STARTED":
            hedef = "INVOICE"
        elif d["deliveryStatus"] != "NOT_STARTED" or d["contractStatus"] == "SIGNED":
            hedef = "DELIVERY"
        else:
            hedef = "AUDIT"
        if d["contractStatus"] == "SIGNED" and d["deliveryStatus"] == "DONE" and d["invoicingStatus"] == "DONE":
            hedef = "WON"
        yama.update({a: v for a, v in d.items() if o.get(a) != v})
    if hedef != asama:
        yama["stage"] = hedef
        log(f"{o['name']}: durumlara göre aşama {asama} → {hedef}")

    # 3) Kapanış ve yeniden açılış
    kapanis = hedef in CLOSED and (onceki is None or onceki in OPEN)
    if onceki != hedef:
        if kapanis:
            yama["realCloseDate"] = dt.datetime.now(TR).date().isoformat()
        elif hedef in OPEN and onceki in CLOSED:
            yama["realCloseDate"] = None

    # 3b) Onaylanıp Audit'e alınınca şirketin Service Manager'ı (kullanıcı, 13 Kas; fırsatta boşsa)
    if kapanis and hedef in DELIVERY_PHASE | {"WON"}:
        yama.update(sirketten_kopyala(o, ["serviceManagerId"]))

    # 4) Hesaplar: açıkken, ya da tam kapandığı anda son kez
    if hedef in OPEN or kapanis:
        yama.update(hesapla(o))

    # 4b) Raporlama dönemi ve "Bu Dönemde" (açıkta beklenen, kapanmışta gerçek kapanış tarihi)
    ilgili_tarih = (yama.get("realCloseDate", o.get("realCloseDate")) if hedef in CLOSED
                    else (tarih_tr(o["closeDate"]) if o.get("closeDate") else None))
    bulunan = donem_bul(ilgili_tarih[:10]) if ilgili_tarih else None
    guncel = donem_bul(dt.datetime.now(TR).date().isoformat())
    yama["reportingPeriodName"] = bulunan[0] if bulunan else None
    yama["inCurrentPeriod"] = bool(bulunan and guncel and bulunan[1] == guncel[1])

    # 5) Kapalı fırsatta kilitli alan değiştiyse kapanış değerlerine geri al
    if hedef in CLOSED and not kapanis:
        snap = kapanis_degerleri(opp_id)
        if snap is None:
            kapanis_degeri_tamamla(o)
        geri = {f: snap[f] for f in LOCK_FIELDS if snap and f in snap and not ayni(o.get(f), snap[f])}
        if geri:
            yama.update(geri)
            log(f"{o['name']}: kapalı fırsatta değişiklik geri alındı: {', '.join(geri)}")

    # 7) Aşama geçmişi: önceki → sonuç aşaması tek kayıt (kapanış kaydı, kapanış anındaki değerleri taşır)
    if onceki != hedef:
        snap = {f: yama.get(f, o.get(f)) for f in LOCK_FIELDS} if kapanis else None
        asama_kaydi(o, onceki, hedef, kim, snap)

    yama = {a: v for a, v in yama.items() if not ayni(o.get(a), v)}
    if yama:
        api("PATCH", f"/rest/opportunities/{opp_id}", yama)
        log(f"{o['name']}: güncellendi {', '.join(yama)}")
        o.update(yama)

    # 8) Sözleşme (yeniden kapanışta değerler güncellenir)
    if hedef in DELIVERY_PHASE | {"WON"}:
        sozlesme_esitle(o, kapanis)


SOZLESME_ALANLARI = [("oneTimeFee", "oneTimeFee"), ("monthlyRecurring", "monthlyFee"), ("annualRecurring", "annualFee"),
                     ("amount", "totalValue"), ("oneTimeCost", "oneTimeCost"), ("monthlyCost", "monthlyCost"),
                     ("annualCost", "annualCost"), ("totalCost", "totalCost"), ("grossProfit", "grossProfit")]


def sozlesme_degerleri(o):
    govde = {"contractMonths": o.get("contractMonths")}
    for src, dst in SOZLESME_ALANLARI:
        govde[dst] = {"amountMicros": micros(o[src]), "currencyCode": o[src]["currencyCode"]} \
            if micros(o.get(src)) is not None else None
    return govde


def sozlesme_esitle(o, kapanis=False):
    mevcut = liste("contracts", filtre=f"opportunityId[eq]:{o['id']}", limit=5)
    imzali = o.get("contractStatus") == "SIGNED"
    if not mevcut:
        govde = {"name": o["name"], "opportunityId": o["id"], "companyId": o.get("companyId"),
                 "status": "ACTIVE" if imzali else "SIGNING", **sozlesme_degerleri(o)}
        c = api("POST", "/rest/contracts", {a: v for a, v in govde.items() if v is not None})["createContract"]
        log(f"{o['name']}: sözleşme oluşturuldu")
        belgeleri_ekle(o, c["id"])
        return
    c, yama = mevcut[0], {}
    if kapanis:
        belgeleri_ekle(o, c["id"])
    if kapanis:
        yama = {a: v for a, v in sozlesme_degerleri(o).items() if not ayni(c.get(a), v)}
    if imzali and c.get("status") == "SIGNING":
        yama["status"] = "ACTIVE"
    if yama:
        api("PATCH", f"/rest/contracts/{c['id']}", yama)
        log(f"{o['name']}: sözleşme güncellendi {', '.join(yama)}")


def belgeleri_ekle(o, sozlesme_id):
    """Fırsattaki Sipariş/Onay ve Onaylanan Teklif dosyalarını sözleşme belgesi olarak kopyalar (türü yoksa)."""
    var = {d.get("documentType") for d in liste("contractDocuments", filtre=f"contractId[eq]:{sozlesme_id}")}
    for alan, tur, ad in [("orderDocument", "ORDER", "Sipariş / Onay"),
                          ("approvedProposal", "APPROVED_PROPOSAL", "Onaylanan teklif")]:
        if tur in var or not o.get(alan):
            continue
        dosyalar = dosya_kopyala(o[alan], "contractDocument", "file")
        api("POST", "/rest/contractDocuments", {"name": f"{ad} - {o['name']}", "contractId": sozlesme_id,
                                                "documentType": tur, "file": dosyalar})
        log(f"{o['name']}: sözleşme belgesi eklendi ({ad}, {len(dosyalar)} dosya)")


def yetkili_roller():
    """Admin ve Super-user rolündeki çalışma alanı üyeleri."""
    sonuc = set()
    for r in gql("{ getRoles { label workspaceMembers { id } } }")["getRoles"]:
        if r["label"] in ("Admin", "Super-user"):
            sonuc |= {m["id"] for m in r.get("workspaceMembers") or []}
    return sonuc


def firsat_acma_denetimi(o):
    """Firmada BDM, SDR, Account Manager, Pre-sales ya da bunların Support'u olan açabilir; Service Manager açamaz.
    Admin ve Super-user her zaman açabilir. Yetkisizse fırsat silinmez: Sistem Uyarısı + super-user'lara görev."""
    acan = (o.get("createdBy") or {})
    kisi = acan.get("workspaceMemberId") if acan.get("source") == "MANUAL" else None
    if not kisi or not o.get("companyId"):
        return
    ust = yetkili_roller()
    if kisi in ust:
        return
    sirket = (api("GET", f"/rest/companies/{o['companyId']}") or {}).get("company") or {}
    yetkili = {sirket.get("accountManagerId"), sirket.get("preSalesId"),
               (sirket.get("createdBy") or {}).get("workspaceMemberId")}
    for d in liste("opportunities", filtre=f"companyId[eq]:{o['companyId']}"):
        if d["id"] != o["id"]:
            yetkili |= {d.get("ownerId"), d.get("bdmId"), d.get("sdrId"), d.get("accountManagerId"), d.get("preSalesId")}
    yetkili.discard(None)
    if kisi in yetkili:
        return
    destek = {e.get("supportId") for e in liste("teamMembers") if e.get("memberId") in yetkili}
    if kisi in destek:
        return
    neden = ("Bu firmada fırsat açma yetkiniz yok (firmada BDM, SDR, Account Manager, Pre-sales ya da Support "
             "değilsiniz). Super-user onayı bekleniyor.")
    api("PATCH", f"/rest/opportunities/{o['id']}", {"systemWarning": neden})
    for su in ust:
        g = api("POST", "/rest/tasks", {"title": f"Yetkisiz fırsat onayı: {o['name']}", "status": "TODO",
                                        "assigneeId": su})["createTask"]
        api("POST", "/rest/taskTargets", {"taskId": g["id"], "targetOpportunityId": o["id"]})
    log(f"{o['name']}: yetkisiz açan, uyarı ve {len(ust)} görev")


# ---------------- şirket sorumluları (liste 12; kararlar/2026-11-13-sorumlu-kopyalama.md) ----------------
SIRKET_SORUMLULARI = ["accountManager", "preSales"]   # şirkette değişince açık fırsatlara yansır


def sirketten_kopyala(o, alanlar):
    """Fırsatta boş olan sorumlu alanlarını şirketten alır (yama döner)."""
    bos = [a for a in alanlar if not o.get(a)]
    if not bos or not o.get("companyId"):
        return {}
    sirket = (api("GET", f"/rest/companies/{o['companyId']}") or {}).get("company") or {}
    return {a: sirket[a] for a in bos if sirket.get(a)}


def sirket_sorumlu_esitle(anahtar):
    """Şirkette AM / Pre-sales değişti: açık fırsatlarda eski kişi yazılı alanı yenisiyle değiştirir (elle başka biri
    yazılmışsa dokunmaz; kapanmış fırsatlar değişmez). Önceki değer Twenty'nin değişiklik geçmişinden okunur (webhook
    olayı önceki değeri taşımaz); geçmiş kaydı birkaç saniye gecikebildiği için birkaç kez denenir."""
    sid = anahtar.split(":", 1)[1]
    sirket = (api("GET", f"/rest/companies/{sid}") or {}).get("company") or {}
    if not sirket:
        return
    degisim = {}
    for deneme in range(5):
        for t in liste("timelineActivities", filtre=f"targetCompanyId[eq]:{sid}", sira="happensAt[DescNullsLast]", limit=20):
            fark = (t.get("properties") or {}).get("diff") or {}
            for alan in SIRKET_SORUMLULARI:
                if alan in fark and alan not in degisim:
                    sonra = ((fark[alan] or {}).get("after") or {}).get("id")
                    if sonra == sirket.get(alan + "Id"):
                        degisim[alan] = (((fark[alan] or {}).get("before") or {}).get("id"), sonra)
        if degisim:
            break
        time.sleep(3)
    for alan, (once, sonra) in degisim.items():
        if once == sonra:
            continue
        for o in liste("opportunities", filtre=f"companyId[eq]:{sid}"):
            if o.get("stage") in OPEN and o.get(alan + "Id") == once:
                api("PATCH", f"/rest/opportunities/{o['id']}", {alan + "Id": sonra})
                log(f"{o['name']}: şirketin {alan} değişikliği fırsata yansıdı")


def firsat_sirket_kilidi(anahtar):
    """Fırsatın şirketi oluştuktan sonra değiştirilemez; yalnız Super-user / Admin değiştirir (kullanıcı, 13 Kas; liste 12c).
    Alan yetkisiyle kilitlenemiyor (Twenty'de oluşturma da güncelleme yetkisi ister): değişiklik geri alınır.
    Önceki şirket ve değiştiren kişi Twenty'nin değişiklik geçmişinden okunur. Boş şirkete ilk atama serbesttir."""
    oid = anahtar.split(":", 1)[1]
    o = (api("GET", f"/rest/opportunities/{oid}") or {}).get("opportunity")
    if not o:
        return
    for deneme in range(5):
        for t in liste("timelineActivities", filtre=f"targetOpportunityId[eq]:{oid}", sira="happensAt[DescNullsLast]", limit=20):
            fark = ((t.get("properties") or {}).get("diff") or {}).get("company")
            if not fark:
                continue
            if ((fark.get("after") or {}).get("id")) != o.get("companyId"):
                break   # en son şirket değişikliği bu değil (bir sonraki olay işler)
            once, kim = (fark.get("before") or {}).get("id"), t.get("workspaceMemberId")
            if once and kim and kim not in yetkili_roller():
                api("PATCH", f"/rest/opportunities/{oid}", {"companyId": once, "systemWarning":
                    "Fırsatın şirketi değiştirilemez; gerekiyorsa Super-user değiştirir. Önceki şirket geri yüklendi."})
                log(f"{o['name']}: şirket değişikliği geri alındı")
            return
        time.sleep(3)


# ---------------- hesap durumu (liste 12b) ----------------
def hesap_durumu(sozlesmeler, bugun):
    """Müşteri: Aktif ve bitişi geçmemiş sözleşme; Eski müşteri: sözleşme var, hiçbiri aktif ya da imzada değil;
    Aday: sözleşme yok ya da yalnız imzada."""
    if any(c.get("status") == "ACTIVE" and (not c.get("endDate") or c["endDate"][:10] >= bugun) for c in sozlesmeler):
        return "CUSTOMER"
    if sozlesmeler and not any(c.get("status") == "SIGNING" for c in sozlesmeler):
        return "FORMER"
    return "PROSPECT"


def hesap_durumu_esitle(anahtar):
    sid = anahtar.split(":", 1)[1]
    sirket = (api("GET", f"/rest/companies/{sid}") or {}).get("company")
    if not sirket:
        return
    yeni = hesap_durumu(liste("contracts", filtre=f"companyId[eq]:{sid}"), dt.datetime.now(TR).date().isoformat())
    if sirket.get("accountStatus") != yeni:
        api("PATCH", f"/rest/companies/{sid}", {"accountStatus": yeni})
        log(f"{sirket.get('name')}: Hesap Durumu {sirket.get('accountStatus')} → {yeni}")


# ---------------- paket tanımı ----------------
AD = "SATIS_SURECI"
OLAYLAR = [("opportunity.", lambda ad, kayit: [f"firsat:{kayit['id']}"] if kayit.get("id") and not ad.endswith(".deleted") else []),
           ("opportunity.updated", lambda ad, kayit: [f"firsat_sirket:{kayit['id']}"] if kayit.get("id") and any(
               a in (kayit.get("_degisen") or []) for a in ("company", "companyId")) else []),
           ("contract.", lambda ad, kayit: [f"hesap:{kayit['companyId']}"] if kayit.get("companyId") else []),
           ("company.created", lambda ad, kayit: [f"hesap:{kayit['id']}"] if kayit.get("id") else []),
           ("company.updated", lambda ad, kayit: [f"sirket:{kayit['id']}"] if kayit.get("id") and any(
               a in (kayit.get("_degisen") or []) for a in SIRKET_SORUMLULARI + [x + "Id" for x in SIRKET_SORUMLULARI]) else [])]
ISLER = {"firsat": lambda anahtar: firsat_isle(anahtar.split(":", 1)[1]), "sirket": sirket_sorumlu_esitle,
         "firsat_sirket": firsat_sirket_kilidi, "hesap": hesap_durumu_esitle}
SONRAKI = {"firsat": ["hedefler"]}   # fırsat değişince hedef gerçekleşmesi yeniden hesaplanır


def tumunu_isle():
    for o in liste("opportunities"):
        try:
            firsat_isle(o["id"], o)
        except Exception:
            log("HATA fırsat", o.get("id"), traceback.format_exc(limit=3))
    bugun = dt.datetime.now(TR).date()
    tum = liste("contracts")
    for sirket in liste("companies"):   # Hesap Durumu: bitiş tarihi geçen sözleşme ertesi gün Eski müşteri yapar
        yeni = hesap_durumu([c for c in tum if c.get("companyId") == sirket["id"]], bugun.isoformat())
        if sirket.get("accountStatus") != yeni:
            api("PATCH", f"/rest/companies/{sirket['id']}", {"accountStatus": yeni})
    for c in tum:
        if c.get("endDate"):
            kalan = (dt.date.fromisoformat(c["endDate"][:10]) - bugun).days
            if c.get("remainingDays") != kalan:
                api("PATCH", f"/rest/contracts/{c['id']}", {"remainingDays": kalan})
