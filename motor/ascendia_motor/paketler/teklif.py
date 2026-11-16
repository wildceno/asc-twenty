"""Paket TEKLIF (liste 14a): katalogdan kalem kopyalama, teklif toplamları ve P&L, marj kuralı ve onay, gönderilen teklifin
fırsata yazılması, revizyon, fırsattaki tutar kilidi, geçerlilik hatırlatması. Hesap: teklif_hesap.py (saf, birim testli).
Plan ve kullanıcı kararları: kararlar/2026-11-13-teklif-modulu-plan.md."""
import datetime as dt

from ascendia_motor.cekirdek.ayar import TR
from ascendia_motor.cekirdek.durum import Durum
from ascendia_motor.cekirdek.gunluk import log
from ascendia_motor.cekirdek.para import cevir, cur
from ascendia_motor.cekirdek.twenty import api, gql, liste
from ascendia_motor.paketler import belge, enflasyon, sablon
from ascendia_motor.paketler.teklif_hesap import enflasyonsuz_pb, gereken_onaylayici, kalem_hesap, teklif_ozet

KATALOG_KOPYA = [("unit", "unit"), ("unitCost", "unitCost"), ("listPrice", "listPrice"), ("billing", "billing"),
                 ("costType", "costType"), ("supplierId", "supplierId"), ("vatRate", "vatRate")]
FIRSAT_ALANLARI = {"ONE_TIME": ("oneTimeFee", "oneTimeCost"), "MONTHLY": ("monthlyRecurring", "monthlyCost"),
                   "YEARLY": ("annualRecurring", "annualCost")}
ACIK_DURUMLAR = {"DRAFT", "PENDING_APPROVAL", "APPROVED"}
YONETICI_ROLLER = ("Admin", "Super-user")


def _simdi():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _bugun():
    return dt.datetime.now(TR).date().isoformat()


def kurlar_tarihte(gun):
    """gun ve öncesindeki en son TCMB kuru (kod → (TRY karşılığı, tarih)); gönderilen teklifin kuru sabitlenir."""
    k = {}
    for r in liste("exchangeRates", filtre=f"rateDate[lte]:{gun}", sira="rateDate[DescNullsLast]"):
        if r.get("foreignCurrency") and r["foreignCurrency"] not in k and r.get("rateTry"):
            k[r["foreignCurrency"]] = (float(r["rateTry"]), r.get("rateDate"))
    return k


def yetkili_uyeler():
    out = set()
    for r in gql("{ getRoles { label workspaceMembers { id } } }")["getRoles"]:
        if r["label"] in YONETICI_ROLLER:
            out |= {m["id"] for m in r.get("workspaceMembers") or []}
    return out


def katalogdan_kopyala(kalem):
    """Katalog kalemi seçilmişse boş alanları katalogdan doldurur (bir kez; katalog sonradan değişse de kalem değişmez)."""
    if not kalem.get("catalogItemId"):
        return {}
    kat = (api("GET", f"/rest/catalogItems/{kalem['catalogItemId']}") or {}).get("catalogItem") or {}
    yama = {hedef: kat[kaynak] for kaynak, hedef in KATALOG_KOPYA
            if kat.get(kaynak) not in (None, "") and not _dolu(kalem.get(hedef))}
    if not kalem.get("name") and kat.get("name"):
        yama["name"] = kat["name"]
    detay = belge.md_metin((kat.get("details") or {}).get("markdown"))
    if not kalem.get("description") and (kat.get("shortDescription") or detay):
        yama["description"] = kat.get("shortDescription") or detay
    if not _dolu(kalem.get("unitPrice")) and _dolu(kat.get("listPrice")):
        yama["unitPrice"] = kat["listPrice"]   # liste fiyatı varsa başlangıç fiyatı; satışçı değiştirir
    if kalem.get("quantity") is None:
        yama["quantity"] = 1
    return yama


def _dolu(v):
    if isinstance(v, dict):
        return v.get("amountMicros") not in (None, "")
    return v not in (None, "")


def teklif_isle(anahtar):
    """Teklif ya da kalemi değişti: kalemleri tamamla, toplamları hesapla, onay ve gönderim kurallarını uygula."""
    tid = anahtar.split(":", 1)[1]
    t = (api("GET", f"/rest/quotes/{tid}") or {}).get("quote")
    if not t:
        return
    ilk = dict(t)   # yazılacak farklar bu ilk hâle göre bulunur
    yama = {}
    firsat = (api("GET", f"/rest/opportunities/{t['opportunityId']}") or {}).get("opportunity") if t.get("opportunityId") else None

    # Yeni teklif: durum, sürüm, ad, süre
    if not t.get("status"):
        yama["status"] = "DRAFT"
    if not t.get("version") and t.get("opportunityId"):
        surumler = [q.get("version") or 0 for q in liste("quotes", filtre=f"opportunityId[eq]:{t['opportunityId']}") if q["id"] != tid]
        yama["version"] = max(surumler, default=0) + 1
    if not t.get("name") and firsat:
        yama["name"] = f"{firsat['name']} — Sürüm {yama.get('version') or t.get('version') or 1}"
    if not t.get("status") and not t.get("quoteTemplateId"):   # yeni teklife varsayılan aktif şablon (15a)
        v = sablon.varsayilan_sablon()
        if v:
            yama["quoteTemplateId"] = v
    if not t.get("contractMonths") and firsat and firsat.get("contractMonths"):
        yama["contractMonths"] = firsat["contractMonths"]
    t.update(yama)

    # Kalemler: katalogdan tamamla, kalem gelir / maliyetini yaz
    kalemler = liste("quoteLines", filtre=f"quoteId[eq]:{tid}")
    for k in kalemler:
        kk = katalogdan_kopyala(k)
        if kk:
            api("PATCH", f"/rest/quoteLines/{k['id']}", kk)
            k.update(kk)

    # Kur: gönderilmiş teklifin kuru gönderim gününde sabittir
    gonderildi = t.get("status") in ("SENT", "ACCEPTED", "REJECTED", "REVISED")
    kur_gunu = (t.get("fxRateDate") or "")[:10] if gonderildi and t.get("fxRateDate") else _bugun()
    kurlar = kurlar_tarihte(kur_gunu)
    # Enflasyon (14c): gönderilmiş teklifte gönderim anındaki öngörü sabittir (kur gibi); açık teklifte güncel tablo
    if gonderildi and t.get("sentAt"):
        enf_kullanilan = t.get("inflationUsed") or {}
    else:
        oranlar, kaynak = enflasyon.tablo()
        enf_kullanilan = {"oranlar": oranlar, "kaynak": kaynak}
    enf = enf_kullanilan.get("oranlar") or {}
    rap = Durum.raporlama or "USD"
    o = teklif_ozet(t, kalemler, lambda tt, a, b: cevir(tt, a, b, kurlar), rap, enf)
    for k in kalemler:   # kalem satırındaki tutarlar (kendi para biriminde)
        h = kalem_hesap(k, t.get("contractMonths"), t.get("priceEscalation") or "NONE", float(t.get("priceEscalationRate") or 0), enf)
        ky = {}
        if h["gelir_pb"]:
            ky["lineRevenue"] = cur(round(h["gelir"], 2), h["gelir_pb"])
        if h["maliyet_pb"]:
            ky["lineCost"] = cur(round(h["maliyet"], 2), h["maliyet_pb"])
        ky = {a: v for a, v in ky.items() if not _ayni_para(k.get(a), v)}
        if ky:
            api("PATCH", f"/rest/quoteLines/{k['id']}", ky)

    yama.update({"currencyBreakdown": o["kirilim"], "revenueReporting": cur(o["gelir"], rap),
                 "costReporting": cur(o["maliyet"], rap), "channelShareReporting": cur(o["kanal"], rap),
                 "grossProfitReporting": cur(o["brut"], rap), "marginPercent": o["marj"], "inflationUsed": enf_kullanilan})
    uyarilar = []
    if o["eksik_kur"]:
        uyarilar.append(f"Kur bulunamadı: {', '.join(o['eksik_kur'])} (bu kalemler toplama girmedi).")
    eksik_enf = enflasyonsuz_pb([k for k in kalemler if k.get("id") in set(o["sayilan"])], t.get("contractMonths"), enf,
                                t.get("priceEscalation") or "NONE")
    if eksik_enf:
        uyarilar.append(f"Enflasyon öngörüsü yok: {', '.join(eksik_enf)} (bu para biriminde yıllar arası artış 0 alındı; "
                        "Yönetim → Enflasyon Öngörüleri'ne elle eklenebilir).")
    uyari = " ".join(uyarilar) or None

    # Marj kuralı ve onay
    onaylayici = gereken_onaylayici(o["marj"], liste("marginRules"))
    yama["approverId"] = onaylayici
    durum = t.get("status")
    degistiren = (t.get("updatedBy") or {}).get("workspaceMemberId") if (t.get("updatedBy") or {}).get("source") == "MANUAL" else None
    if onaylayici and durum == "APPROVED" and not t.get("approvedById"):
        if degistiren and (degistiren == onaylayici or degistiren in yetkili_uyeler()):
            yama["approvedById"] = degistiren
        elif degistiren:
            yama["status"] = "PENDING_APPROVAL"
            uyari = " ".join(x for x in ("Bu teklifi yalnız onaylayıcı ya da Super-user onaylayabilir.", uyari) if x)
    if onaylayici and durum == "SENT" and not (t.get("approvedById") or yama.get("approvedById")):
        yama["status"] = "PENDING_APPROVAL"
        uyari = " ".join(x for x in ("Marj kuralı gereği gönderimden önce onay gerekiyor; onaylayıcıya görev açıldı.", uyari) if x)
        _onay_gorevi(t, onaylayici)
    if not onaylayici and t.get("approvedById") and durum in ACIK_DURUMLAR:
        yama["approvedById"] = None   # rakamlar değişti, onay gerekmiyor
    if durum == "PENDING_APPROVAL" and onaylayici and not t.get("approvedById"):
        _onay_gorevi(t, onaylayici)
    yama["systemWarning"] = uyari

    # Gönderim: rakamlar fırsata, önceki sürüm Revize edildi, kur sabitlenir
    if durum == "SENT" and yama.get("status") != "PENDING_APPROVAL" and not t.get("sentAt"):
        yama["sentAt"], yama["fxRateDate"] = _simdi(), _bugun()
        for q in liste("quotes", filtre=f"opportunityId[eq]:{t['opportunityId']}"):
            if q["id"] != tid and q.get("status") in ("SENT", "DRAFT", "APPROVED", "PENDING_APPROVAL"):
                api("PATCH", f"/rest/quotes/{q['id']}", {"status": "REVISED"})
        api("PATCH", f"/rest/opportunities/{t['opportunityId']}", {"currentQuoteId": tid})
        log(f"{t.get('name')}: gönderildi, fırsatın geçerli teklifi oldu")
    yama = {a: v for a, v in yama.items() if not _ayni(ilk.get(a), v)}
    if yama:
        api("PATCH", f"/rest/quotes/{tid}", yama)
        t.update(yama)
    # Geçerli teklifse fırsatın rakamları bu tekliften (kabulde seçilen seçenek değişirse de)
    if firsat and (firsat.get("currentQuoteId") == tid or yama.get("sentAt")) and t.get("status") in ("SENT", "ACCEPTED"):
        firsata_yaz(firsat, t, o, rap)


def firsata_yaz(firsat, t, o, rap):
    yama = {"contractMonths": t.get("contractMonths")}
    for odeme, (gelir_alani, maliyet_alani) in FIRSAT_ALANLARI.items():
        g, m = o["firsat"][odeme]
        yama[gelir_alani] = cur(g, rap) if g else None
        yama[maliyet_alani] = cur(m, rap) if m else None
    yama = {a: v for a, v in yama.items() if not _ayni_para(firsat.get(a), v) and not (firsat.get(a) is None and v is None)}
    if yama:
        api("PATCH", f"/rest/opportunities/{firsat['id']}", yama)
        log(f"{firsat['name']}: rakamlar geçerli tekliften ({', '.join(yama)})")


def firsat_kilidi(anahtar):
    """Fırsatın geçerli teklifi varsa gelir / maliyet / süre alanları tekliften gelir; elle değişiklik geri alınır."""
    oid = anahtar.split(":", 1)[1]
    f = (api("GET", f"/rest/opportunities/{oid}") or {}).get("opportunity")
    if not f or not f.get("currentQuoteId"):
        return
    t = (api("GET", f"/rest/quotes/{f['currentQuoteId']}") or {}).get("quote")
    if t and t.get("status") in ("SENT", "ACCEPTED"):
        teklif_isle(f"teklif:{t['id']}")


def _onay_gorevi(t, onaylayici):
    baslik = f"Teklif onayı: {t.get('name')}"
    if any(g.get("title") == baslik and g.get("status") != "DONE" for g in liste("tasks", filtre=f"assigneeId[eq]:{onaylayici}")):
        return
    g = api("POST", "/rest/tasks", {"title": baslik, "status": "TODO", "assigneeId": onaylayici, "dueAt": _simdi(),
                                    "bodyV2": {"markdown": f"Marj %{t.get('marginPercent')} — marj kuralı eşiğinin altında. "
                                                           "Onaylamak için teklifin durumunu Onaylandı yapın."}})["createTask"]
    api("POST", "/rest/taskTargets", {"taskId": g["id"], "targetQuoteId": t["id"]})
    if t.get("opportunityId"):
        api("POST", "/rest/taskTargets", {"taskId": g["id"], "targetOpportunityId": t["opportunityId"]})
    log(f"{t.get('name')}: onay görevi açıldı")


def gecerlilik_hatirlat(anahtar=None):
    """Gönderilmiş teklifin geçerliliğinin bitmesine N gün kala (CRM Ayarı, varsayılan 3) ve bittiği gün fırsat sahibine görev."""
    gun = Durum.teklif_hatirlatma_gun
    bugun = dt.datetime.now(TR).date()
    for t in liste("quotes", filtre="status[eq]:SENT"):
        bitis = (t.get("validUntil") or "")[:10]
        if not bitis or not t.get("opportunityId"):
            continue
        kalan = (dt.date.fromisoformat(bitis) - bugun).days
        gonderilen = set((t.get("reminderSentFor") or "").split(","))
        for etiket, kosul, baslik in ((f"erken:{bitis}", 0 < kalan <= gun, f"Teklif geçerliliği {kalan} gün sonra bitiyor"),
                                      (f"son:{bitis}", kalan <= 0, "Teklif geçerliliği bugün bitiyor" if kalan == 0 else "Teklif geçerliliği bitti")):
            if not kosul or etiket in gonderilen:
                continue
            f = (api("GET", f"/rest/opportunities/{t['opportunityId']}") or {}).get("opportunity") or {}
            if not f.get("ownerId"):
                continue
            g = api("POST", "/rest/tasks", {"title": f"{baslik}: {t.get('name')}", "status": "TODO", "assigneeId": f["ownerId"],
                                            "dueAt": dt.datetime.combine(bugun, dt.time(9, 0), TR).astimezone(dt.timezone.utc)
                                            .isoformat().replace("+00:00", "Z")})["createTask"]
            api("POST", "/rest/taskTargets", {"taskId": g["id"], "targetQuoteId": t["id"]})
            api("POST", "/rest/taskTargets", {"taskId": g["id"], "targetOpportunityId": t["opportunityId"]})
            gonderilen.add(etiket)
            api("PATCH", f"/rest/quotes/{t['id']}", {"reminderSentFor": ",".join(sorted(x for x in gonderilen if x))})
            log(f"{t.get('name')}: geçerlilik hatırlatması ({etiket})")


def _ayni(a, b):
    if isinstance(a, dict) and isinstance(b, dict) and "amountMicros" in b:
        return _ayni_para(a, b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-9
    return a == b


def _ayni_para(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return a == b
    av, bv = a.get("amountMicros"), b.get("amountMicros")
    av = None if av in (None, "") else round(float(av))
    bv = None if bv in (None, "") else round(float(bv))
    return av == bv and (av is None or a.get("currencyCode") == b.get("currencyCode"))


# ---------------- paket tanımı ----------------
AD = "TEKLIF"
OLAYLAR = [
    (("quote.created", "quote.updated"), lambda ad, kayit: ([f"teklif:{kayit['id']}", "teklif_hatirlat"]
                                                            + ([f"belge:{kayit['id']}"] if kayit.get("documentRequest") else []))
     if kayit.get("id") else []),
    (("quoteLine.",), lambda ad, kayit: [f"teklif:{kayit['quoteId']}"] if kayit.get("quoteId") else []),
    (("marginRule.",), lambda ad, kayit: ["teklif_kural"]),
    (("quoteTemplate.created", "quoteTemplate.updated"), lambda ad, kayit: [f"sablon:{kayit['id']}"] if kayit.get("id") else []),
    (("inflationForecast.",), lambda ad, kayit: ["enflasyon_tablo", "teklif_kural"]),
    (("opportunity.updated",), lambda ad, kayit: [f"teklif_firsat:{kayit['id']}"] if kayit.get("currentQuoteId") and any(
        a in (kayit.get("_degisen") or []) for a in ("oneTimeFee", "monthlyRecurring", "annualRecurring", "oneTimeCost",
                                                     "monthlyCost", "annualCost", "contractMonths")) else []),
]
ISLER = {"teklif": teklif_isle, "sablon": sablon.sablon_isle, "belge": belge.belge_isle,
         "enflasyon_guncelle": enflasyon.guncelle, "enflasyon_tablo": enflasyon.tablo_degisti,
         "teklif_firsat": firsat_kilidi, "teklif_hatirlat": gecerlilik_hatirlat,
         "teklif_kural": lambda anahtar: [teklif_isle(f"teklif:{q['id']}") for q in liste("quotes") if q.get("status") in ACIK_DURUMLAR]}
BIRLESTIRME = {"teklif_hatirlat": 60, "teklif_kural": 30}
PERIYODIK = ["teklif_hatirlat", "enflasyon_guncelle"]
