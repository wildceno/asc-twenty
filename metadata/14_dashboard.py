#!/usr/bin/env python3
"""Ana Dashboard: Ascendia Pano widget'ları (apps/ascendia-pano), eklenip çıkarılabilir ve taşınabilir.

Kullanıcı kararları:
- 11 Kas 2026: metriğin raporlama para birimindeki toplamı (Ascendia: Revenue, USD); dönem/aşama/kişi filtresi;
  kişi bazında aşamalar üst üste + hedef çizgisi; Period > Sales Rep > Stage tablosu. Twenty örnek bileşenleri silinsin.
- 13 Kas 2026: her görselleştirme ayrı widget; Dashboard'a eklenip çıkarılabilir, yeri değiştirilebilir; filtre ayrı
  widget ve sayfadaki tüm widget'ları süzer (adres parametreleri, bkz. apps/ascendia-pano/src/lib/filtre.ts).

Idempotent ve kullanıcıya saygılı:
- Widget, front component kimliğiyle bulunur. Yalnız panoda HİÇ yoksa ve daha önce bu betikle eklenmemişse eklenir;
  kullanıcının taşıdığı, boyutladığı ya da yeniden adlandırdığı widget'a dokunulmaz.
- Kullanıcı bir widget'ı panodan kaldırırsa betik onu geri koymaz (eklenenler ~/twenty/.dashboard-kurulum.json'da).
- Tek seferlik geçiş: Twenty'nin hazır iki grafiği (Hedef Takibi ve Aşama Dağılımı'nın filtresiz kopyaları) silinir;
  eski "Satış Panosu" widget'ı aynı bileşenin yeni adıyla "Fırsat Dökümü" olur.
Önce: apps/ascendia-pano → twenty app apply. Geri dönüş: git geçmişindeki önceki 14_dashboard.py sürümü.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twenty import KEY_FILE, gql  # noqa: E402

# Repo dışında (dagit.sh rsync --delete repo kopyasını siler): API anahtarının yanında
KAYIT = os.path.join(os.path.dirname(os.path.abspath(KEY_FILE)), ".dashboard-kurulum.json")

# (bileşen adı, satır, sütun, satır sayısı, sütun sayısı) — 12 sütunlu ızgara, yalnız ilk eklemede
DIZILIM = [
    ("Pano Filtresi", 0, 0, 3, 12),
    ("Satış Göstergeleri", 3, 0, 4, 12),
    ("Hedef Takibi", 7, 0, 7, 6),
    ("Aşama Dağılımı", 7, 6, 7, 6),
    ("Büyük Fırsatlar", 14, 0, 8, 12),
    ("Fırsat Dökümü", 22, 0, 12, 12),
    ("Forecast", 34, 0, 12, 12),
    ("Kaynak ve Kanal", 46, 0, 14, 12),
]
ESKI_GRAFIKLER = ("Pipeline — Aşamaya Göre", "Kişi Bazında Pipeline")  # başlık başı (metrik eki değişebilir)
ORNEKLER = {"Gelir zaman çizelgesi", "Borsa (Iframe)", "Untitled Rich Text", "Deals by Company",
            "Deals created this month", "Deal value created this month"}

fcs = {f["name"]: f["id"] for f in gql("{ frontComponents { id name } }")["frontComponents"]}
eksik = [ad for ad, *_ in DIZILIM if ad not in fcs]
if eksik:
    sys.exit(f"Ascendia Pano uygulaması kurulu değil ya da eski sürüm (eksik: {', '.join(eksik)}). "
             "Önce: apps/ascendia-pano → twenty app apply")

PQ = ("{ getPageLayouts(pageLayoutType: DASHBOARD) { id name tabs { id widgets { id title type "
      "configuration { ... on FrontComponentConfiguration { frontComponentId } } } } } }")
pls = gql(PQ)["getPageLayouts"]
fc_kimlikleri = set(fcs.values())
ana = next((p for p in pls if any((w.get("configuration") or {}).get("frontComponentId") in fc_kimlikleri
                                  for t in p["tabs"] for w in t["widgets"])), None) or (pls[0] if len(pls) == 1 else None)
if not ana:
    sys.exit(f"Ana Dashboard belirlenemedi ({len(pls)} pano var, hiçbirinde Ascendia widget'ı yok).")
tab = ana["tabs"][0]
widgets = [w for t in ana["tabs"] for w in t["widgets"]]

kayit = json.load(open(KAYIT)) if os.path.exists(KAYIT) else {}
eklenmis = set(kayit.get(ana["id"], []))

# --- tek seferlik temizlik ---
for w in widgets:
    if w["title"] in ORNEKLER or (w["type"] == "GRAPH" and w["title"].startswith(ESKI_GRAFIKLER)):
        gql("mutation($id: String!) { destroyPageLayoutWidget(id: $id) }", {"id": w["id"]})
        print("silindi:", w["title"])
    elif w["title"] == "Satış Panosu" and (w.get("configuration") or {}).get("frontComponentId") == fcs["Fırsat Dökümü"]:
        gql("mutation($id: String!, $i: UpdatePageLayoutWidgetInput!) { updatePageLayoutWidget(id: $id, input: $i) { id } }",
            {"id": w["id"], "i": {"title": "Fırsat Dökümü",
                                  "position": {"layoutMode": "GRID", "row": 22, "column": 0, "rowSpan": 12, "columnSpan": 12}}})
        print("yeniden adlandırıldı: Satış Panosu → Fırsat Dökümü")
        eklenmis.add("Fırsat Dökümü")

# --- widget'lar: yalnız ilk kez ---
var = {(w.get("configuration") or {}).get("frontComponentId") for w in widgets}
for ad, r, c, rs, cs in DIZILIM:
    if fcs[ad] in var:
        eklenmis.add(ad)
        print("var:", ad)
        continue
    if ad in eklenmis:
        print("atlandı (kullanıcı kaldırmış):", ad)
        continue
    gql("mutation($i: CreatePageLayoutWidgetInput!) { createPageLayoutWidget(input: $i) { id } }",
        {"i": {"pageLayoutTabId": tab["id"], "title": ad, "type": "FRONT_COMPONENT",
               "position": {"layoutMode": "GRID", "row": r, "column": c, "rowSpan": rs, "columnSpan": cs},
               "configuration": {"configurationType": "FRONT_COMPONENT", "frontComponentId": fcs[ad]}}})
    eklenmis.add(ad)
    print("eklendi:", ad)

kayit[ana["id"]] = sorted(eklenmis)
json.dump(kayit, open(KAYIT, "w"), ensure_ascii=False, indent=2)

# --- doğrulama: API'den geri oku ---
son = next(p for p in gql(PQ)["getPageLayouts"] if p["id"] == ana["id"])
print("panoda:", ", ".join(w["title"] for t in son["tabs"] for w in t["widgets"]))
