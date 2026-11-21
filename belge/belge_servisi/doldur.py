"""Şablon doldurma (liste 15b): yer tutucular, bölüm çıkarma, kalem tablosu, ürün açıklamaları; LibreOffice ile PDF.

Girdi (motor hazırlar; plan: CRM/kararlar/2026-11-13-teklif-modulu-plan.md):
  degerler          {yer tutucu adı: metin}  (CRM'den dolanlar ve satışçının yazdıkları; eksik olan boş bırakılır + uyarı)
  haric             [bölüm sırası]           (çıkarılacak bölümler; sıra okumadaki sırayla aynı)
  bolum_sayisi      okumadaki bölüm sayısı   (dosya o günden beri değiştiyse üretim durur)
  kalem_tablosu     {'basliklar': [...], 'satirlar': [[...]], 'toplamlar': [[...]]}
  urun_aciklamalari [{'ad', 'aciklama'}]
Yer tutucu değiştirme biçimi korur: işaret birden fazla parçaya (run) bölünmüşse yalnız o parçalar birleştirilir.
"""
import copy
import io
import os
import subprocess
import tempfile

from belge_servisi import akis
from belge_servisi.oku import YER_TUTUCU, OkumaHatasi, bicim_bul, docx_bolumleri, docx_ust_alt, pptx_bolumleri

OTOMATIK = {"kalem_tablosu", "urun_aciklamalari", "icerik"}
DUZEN = {"bosluk", "sayfa_sonu"}   # düzen işaretleri (16 Kas): akışta akis.py, Word'de doldur_docx işler
CAPA = "/imza/"   # DocuSign imza çapası (motor {{imza}} için yazar); belgede beyaz, görünmez (liste 20)


def capa_gizle(parcalar, renk_yaz):
    """Yalnız çapayı taşıyan parçaları beyaz yapar (imza alanı DocuSign'da çapaya konur)."""
    for r in parcalar:
        if r.text.strip() == CAPA:
            renk_yaz(r)   # icerik: akış şablonunun içerik alanı (akis.py)


def parcalarda_degistir(parcalar, deger, atla=OTOMATIK):
    """parcalar: .text özelliği olan run listesi. Her {{ad}} → deger(ad) (atla'dakiler hariç). Sağdan sola: önceki
    konumlar bozulmaz."""
    metinler = [p.text for p in parcalar]
    tum = "".join(metinler)
    if "{{" not in tum:
        return False
    baslar, k = [], 0
    for m in metinler:
        baslar.append(k)
        k += len(m)
    uzunluk = [len(m) for m in metinler]   # özgün uzunluklar: sağdan sola değişiklik soldaki konumları bozmaz

    def hangi(konum):
        return next(i for i in range(len(parcalar)) if baslar[i] <= konum < baslar[i] + uzunluk[i])

    degisti = False
    for m in reversed(list(YER_TUTUCU.finditer(tum))):
        ad = m.group(1).strip()
        if ad in atla:
            continue   # otomatik bloklar ayrıca işlenir
        yeni = deger(ad)
        s, e = m.span()
        i, j = hangi(s), hangi(e - 1)
        if i == j:
            metinler[i] = metinler[i][:s - baslar[i]] + yeni + metinler[i][e - baslar[i]:]
        else:
            metinler[i] = metinler[i][:s - baslar[i]] + yeni
            for x in range(i + 1, j):
                metinler[x] = ""
            metinler[j] = metinler[j][e - baslar[j]:]
        degisti = True
    if degisti:
        for p, m in zip(parcalar, metinler):
            if p.text != m:
                p.text = m
    return degisti


class Degerler:
    def __init__(self, degerler, cok_satir="\n"):
        self.d = {k: ("" if v is None else str(v)) for k, v in (degerler or {}).items()}
        self.eksik = []
        self.cok_satir = cok_satir

    def __call__(self, ad):
        if ad in self.d:
            return self.d[ad].replace("\n", self.cok_satir)
        if ad in DUZEN:
            return ""
        if ad not in self.eksik:
            self.eksik.append(ad)
        return ""


# ---------------- Word ----------------

def _docx_paragraflar(kap):
    """Gövde / hücre / üst bilgi içindeki tüm paragraflar (tablolar dahil, iç içe)."""
    for p in kap.paragraphs:
        yield p
    for t in getattr(kap, "tables", []):
        for satir in t.rows:
            for hucre in satir.cells:
                yield from _docx_paragraflar(hucre)


def _docx_tablo(belge, sonra, tablo):
    from docx.shared import Pt
    sutun = len(tablo["basliklar"])
    satirlar = [tablo["basliklar"]] + tablo["satirlar"] + tablo.get("toplamlar", [])
    t = belge.add_table(rows=len(satirlar), cols=sutun)
    try:
        t.style = "Table Grid"
    except (KeyError, ValueError):
        pass   # şablonda bu stil yoksa varsayılan tablo
    toplam_bas = 1 + len(tablo["satirlar"])
    for r, satir in enumerate(satirlar):
        for c in range(sutun):
            hucre = t.cell(r, c)
            hucre.text = ""
            run = hucre.paragraphs[0].add_run(str(satir[c]) if c < len(satir) else "")
            run.font.size = Pt(9)
            run.bold = r == 0 or r >= toplam_bas
            if c > 0:
                hucre.paragraphs[0].alignment = 2   # sağa (sayılar)
    sonra.addnext(t._tbl)
    return t._tbl


def _docx_aciklamalar(paragraf, ogeler):
    """İşaret paragrafının ardına her kalem için kalın ad + açıklama paragrafları (işaret paragrafının biçimiyle)."""
    from docx.text.paragraph import Paragraph
    son = paragraf._p
    for o in ogeler:
        for metin, kalin in ((o["ad"], True), (o.get("aciklama") or "", False)):
            if not metin:
                continue
            yeni = copy.deepcopy(paragraf._p)
            for cocuk in list(yeni):
                if cocuk.tag.rsplit("}", 1)[-1] != "pPr":
                    yeni.remove(cocuk)
            son.addnext(yeni)
            son = yeni
            p = Paragraph(yeni, paragraf._parent)
            satirlar = metin.split("\n")
            for i, satir in enumerate(satirlar):
                r = p.add_run(satir)
                r.bold = kalin
                if i < len(satirlar) - 1:
                    r.add_break()


def _isaret_sil(parcalar, ad):
    parcalarda_degistir(parcalar, lambda x: "" if x == ad else "{{" + x + "}}", atla=set())


def doldur_docx(veri, girdi):
    from docx import Document

    belge = Document(io.BytesIO(veri))
    bolumler = docx_bolumleri(belge)
    if len(bolumler) != girdi.get("bolum_sayisi", len(bolumler)):
        raise OkumaHatasi("Şablon dosyasının bölüm sayısı okunduğundan farklı: şablonu yeniden yükleyin.")
    uyarilar = []
    for sira in sorted(set(girdi.get("haric") or []), reverse=True):
        if 1 <= sira <= len(bolumler):
            for oge in bolumler[sira - 1]["ogeler"]:
                if oge.find(".//{*}sectPr") is not None:   # bölüm sonu (sayfa düzeni) taşıyan paragraf: içi boşaltılır
                    for cocuk in list(oge):
                        if cocuk.tag.rsplit("}", 1)[-1] != "pPr":
                            oge.remove(cocuk)
                    continue
                oge.getparent().remove(oge)
    from docx.shared import RGBColor as DocxRGB
    from docx.enum.text import WD_BREAK
    for p in list(_docx_paragraflar(belge)):   # düzen işaretleri: {{sayfa_sonu}} → sayfa sonu, {{bosluk}} → boş satır
        if "{{sayfa_sonu}}" in p.text.replace(" ", ""):
            _isaret_sil(p.runs, "sayfa_sonu")
            p.add_run().add_break(WD_BREAK.PAGE)
        if "{{bosluk}}" in p.text.replace(" ", ""):
            _isaret_sil(p.runs, "bosluk")
            p.add_run().add_break()
    deger = Degerler(girdi.get("degerler"))
    for p in list(_docx_paragraflar(belge)) + list(docx_ust_alt(belge)):
        parcalarda_degistir(p.runs, deger)
        capa_gizle(p.runs, lambda r: setattr(r.font.color, "rgb", DocxRGB(0xFF, 0xFF, 0xFF)))
    # otomatik bloklar: yalnız işareti taşıyan paragraf yerine tablo / açıklamalar
    for p in list(_docx_paragraflar(belge)):
        metin = p.text
        for ad in OTOMATIK:
            isaret = "{{" + ad + "}}"
            if isaret not in metin.replace(" ", ""):
                continue
            if ad == "kalem_tablosu":
                if girdi.get("kalem_tablosu"):
                    _docx_tablo(belge, p._p, girdi["kalem_tablosu"])
            elif girdi.get("urun_aciklamalari"):
                _docx_aciklamalar(p, girdi["urun_aciklamalari"])
            kalan = YER_TUTUCU.sub(lambda m: "" if m.group(1).strip() == ad else m.group(0), metin).strip()
            if not kalan and p._p.getparent() is not None and p._p.find(".//{*}sectPr") is None:
                p._p.getparent().remove(p._p)   # yalnız işaret vardı: paragraf yerini tabloya / açıklamalara bırakır
            else:
                _isaret_sil(p.runs, ad)
            metin = p.text
    if deger.eksik:
        uyarilar.append("Değeri olmayan yer tutucular boş bırakıldı: " + ", ".join(deger.eksik))
    cikti = io.BytesIO()
    belge.save(cikti)
    return cikti.getvalue(), uyarilar


# ---------------- PowerPoint ----------------

def _pptx_sekiller(sekiller):
    for s in sekiller:
        if getattr(s, "shape_type", None) == 6 and hasattr(s, "shapes"):
            yield from _pptx_sekiller(s.shapes)
        else:
            yield s


def _pptx_paragraflar(sekil):
    if getattr(sekil, "has_text_frame", False) and sekil.has_text_frame:
        yield from sekil.text_frame.paragraphs
    if getattr(sekil, "has_table", False) and sekil.has_table:
        for satir in sekil.table.rows:
            for hucre in satir.cells:
                yield from hucre.text_frame.paragraphs


def _beyaz_pptx(r):
    from pptx.dml.color import RGBColor
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _pptx_slayt_sil(sunum, indeks):
    liste = sunum.slides._sldIdLst
    sld = list(liste)[indeks]
    sunum.part.drop_rel(sld.rId)
    liste.remove(sld)


def _pptx_tablo(slayt, sekil, tablo):
    from pptx.util import Pt
    satirlar = [tablo["basliklar"]] + tablo["satirlar"] + tablo.get("toplamlar", [])
    sutun = len(tablo["basliklar"])
    g = slayt.shapes.add_table(len(satirlar), sutun, sekil.left, sekil.top, sekil.width,
                               min(sekil.height, Pt(18) * len(satirlar)) if sekil.height else Pt(18) * len(satirlar))
    toplam_bas = 1 + len(tablo["satirlar"])
    for r, satir in enumerate(satirlar):
        for c in range(sutun):
            tf = g.table.cell(r, c).text_frame
            tf.text = str(satir[c]) if c < len(satir) else ""
            for p in tf.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)
                    run.font.bold = r == 0 or r >= toplam_bas
    return g


def doldur_pptx(veri, girdi):
    from pptx import Presentation

    sunum = Presentation(io.BytesIO(veri))
    bolumler, _ = pptx_bolumleri(sunum)
    if len(bolumler) != girdi.get("bolum_sayisi", len(bolumler)):
        raise OkumaHatasi("Şablon dosyasının bölüm sayısı okunduğundan farklı: şablonu yeniden yükleyin.")
    sil = sorted({i for sira in set(girdi.get("haric") or []) if 1 <= sira <= len(bolumler) for i in bolumler[sira - 1]["slaytlar"]},
                 reverse=True)
    for i in sil:
        _pptx_slayt_sil(sunum, i)
    uyarilar = []
    akis.uygula(sunum, girdi.get("akis") or [])   # içerik slaytı: bloklar yazılır, gerektikçe çoğaltılır
    deger = Degerler(girdi.get("degerler"), cok_satir="\v")
    for slayt in sunum.slides:
        for sekil in list(_pptx_sekiller(slayt.shapes)):
            metin = sekil.text_frame.text if getattr(sekil, "has_text_frame", False) and sekil.has_text_frame else ""
            oto = next((ad for ad in ("kalem_tablosu", "urun_aciklamalari") if "{{" + ad + "}}" in metin.replace(" ", "")), None)
            if oto == "kalem_tablosu" and girdi.get("kalem_tablosu"):
                _pptx_tablo(slayt, sekil, girdi["kalem_tablosu"])
                if len(girdi["kalem_tablosu"]["satirlar"]) > 12:
                    uyarilar.append("Kalem tablosu 12 satırdan uzun: slayta sığmayabilir.")
                if not YER_TUTUCU.sub("", metin).strip():
                    sekil._element.getparent().remove(sekil._element)
                    continue
            if oto == "urun_aciklamalari":
                tf = sekil.text_frame
                ogeler = girdi.get("urun_aciklamalari") or []
                tf.clear()
                ilk = True
                for o in ogeler:
                    for satir, kalin in ((o["ad"], True), (o.get("aciklama") or "", False)):
                        if not satir:
                            continue
                        p = tf.paragraphs[0] if ilk else tf.add_paragraph()
                        ilk = False
                        r = p.add_run()
                        r.text = satir.replace("\n", "\v")
                        r.font.bold = kalin
                continue
            for p in _pptx_paragraflar(sekil):
                parcalarda_degistir(p.runs, deger)
                capa_gizle(p.runs, _beyaz_pptx)
                for ad in OTOMATIK:   # tablo eklenmiş şekilde kalan blok işareti temizlenir
                    _isaret_sil(p.runs, ad)
    if deger.eksik:
        uyarilar.append("Değeri olmayan yer tutucular boş bırakıldı: " + ", ".join(deger.eksik))
    cikti = io.BytesIO()
    sunum.save(cikti)
    return cikti.getvalue(), uyarilar


def pdf_yap(veri, uzanti):
    """LibreOffice (headless) ile PDF. Geçici klasörde çalışır; profil /tmp'de (salt okunur konteyner)."""
    with tempfile.TemporaryDirectory(dir="/tmp") as k:
        kaynak = os.path.join(k, "teklif" + uzanti)
        with open(kaynak, "wb") as f:
            f.write(veri)
        ortam = {**os.environ, "HOME": k}
        r = subprocess.run(["soffice", "--headless", "--norestore", f"-env:UserInstallation=file://{k}/profil",
                            "--convert-to", "pdf", "--outdir", k, kaynak], capture_output=True, timeout=180, env=ortam)
        hedef = os.path.join(k, "teklif.pdf")
        if r.returncode != 0 or not os.path.exists(hedef):
            raise RuntimeError(f"PDF üretilemedi: {r.stderr.decode(errors='replace')[:300]}")
        with open(hedef, "rb") as f:
            return f.read()


def uret(veri, girdi):
    """Döner: {'uzanti', 'belge': bayt, 'pdf': bayt ya da None, 'uyarilar'}."""
    bicim = bicim_bul(veri)
    belge, uyarilar = (doldur_docx if bicim == "DOCX" else doldur_pptx)(veri, girdi)
    uzanti = ".docx" if bicim == "DOCX" else ".pptx"
    pdf = pdf_yap(belge, uzanti) if girdi.get("pdf") else None
    return {"uzanti": uzanti, "belge": belge, "pdf": pdf, "uyarilar": uyarilar}
