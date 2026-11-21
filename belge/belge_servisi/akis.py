"""Akış şablonu (liste 15c): PowerPoint'te {{icerik}} kutusu olan slayt içerik sayfasıdır. CRM'de tanımlanan bölümler
(başlık + metin, kalem tablosu, ürün açıklamaları) bu kutunun alanına yazılır; sığmayınca slayt (logo, alt bilgi,
resimlerle) kopyalanır. Kapak ve son kapak slaytları yerinde kalır.

Sayfalama tahminidir (python-pptx yazı ölçemez): satır başına karakter ≈ alan genişliği / (0,5 × yazı boyutu),
satır yüksekliği ≈ 1,25 × yazı boyutu. Tahmin bilinçli olarak temkinlidir (taşma yerine erken sayfa geçişi).
Uzun tablo sayfalar arasında bölünür, başlık satırı her sayfada tekrarlanır.
"""
import copy
import re

from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

ISARET = "{{icerik}}"
KARAKTER_ORANI = 0.47      # ortalama karakter genişliği / yazı boyutu (LibreOffice çıktısıyla ölçüldü, 14 Kas)
SATIR = 1.25               # satır yüksekliği / yazı boyutu
TABLO_YAZI = 9
TABLO_DOLGU = 9           # hücre üst + alt iç boşluğu (pt); satır yüksekliği tabloya açıkça yazılır
BOLUM_ARASI = 24          # bölüm başlığından önceki boşluk (pt; sayfanın ilk bölümünde uygulanmaz) — kullanıcı 16 Kas
BASLIK_SONRASI = 8        # başlık ile içeriği arasındaki boşluk (pt)
BOSLUK, SAYFA_SONU = "{{bosluk}}", "{{sayfa_sonu}}"   # bölüm metninde: bir satır boşluk / yeni sayfadan devam


def akis_slayti(sunum):
    """{{icerik}} kutusu olan ilk slaytın sırası (0'dan) ve kutu; yoksa (None, None)."""
    for i, s in enumerate(sunum.slides):
        for sh in s.shapes:
            if sh.has_text_frame and ISARET in sh.text_frame.text.replace(" ", ""):
                return i, sh
    return None, None


def _yazi(sekil):
    """Kutudaki ilk yazının biçimi (ad, boyut pt, renk)."""
    for p in sekil.text_frame.paragraphs:
        for r in p.runs:
            renk = None
            try:
                renk = str(r.font.color.rgb) if r.font.color and r.font.color.type is not None else None
            except AttributeError:
                pass
            return r.font.name, (r.font.size.pt if r.font.size else 11.0), renk
    return None, 11.0, None


def _satirlar(metin, karakter):
    """Kelime kaydırmalı satırlara böler (tahmin için)."""
    out = []
    for parca in (metin or "").split("\n"):
        kelimeler, satir = parca.split(" "), ""
        for k in kelimeler:
            aday = (satir + " " + k).strip()
            if len(aday) <= karakter or not satir:
                satir = aday
            else:
                out.append(satir)
                satir = k
        out.append(satir)
    return out


class Duzen:
    """Blokları sayfalara yerleştirir. Sayfa = [(tür, veri, yükseklik_pt)]; tür 'metin' (paragraflar) ya da 'tablo'."""

    def __init__(self, genislik_pt, yukseklik_pt, boyut):
        self.g, self.h, self.b = genislik_pt, yukseklik_pt, boyut
        self.sayfalar, self.sayfa, self.y = [], [], 0.0

    def _yeni(self):
        self.sayfalar.append(self.sayfa)
        self.sayfa, self.y = [], 0.0

    def _kalan(self):
        return self.h - self.y

    def paragraf(self, metin, boyut, kalin=False, once=0.0, sonra=4.0, baslik=False):
        karakter = max(10, int(self.g / (KARAKTER_ORANI * boyut)))
        satir_h = SATIR * boyut
        satirlar = _satirlar(metin, karakter)
        while satirlar:
            bas = once if self.sayfa else 0.0
            sigan = int((self._kalan() - bas - sonra) // satir_h)
            if baslik and sigan < 3 and self.sayfa:     # başlık sayfa sonunda yalnız kalmasın
                self._yeni()
                continue
            if sigan <= 0:
                self._yeni()
                continue
            parca, satirlar = satirlar[:sigan], satirlar[sigan:]
            yuk = bas + len(parca) * satir_h + sonra
            self.sayfa.append(("metin", {"satirlar": parca, "boyut": boyut, "kalin": kalin, "once": bas}, yuk))
            self.y += yuk
            if satirlar:
                self._yeni()

    def bosluk(self, satir=1):
        """Bir satır yüksekliğinde boşluk; sayfa başında yok sayılır, sığmazsa sayfa geçer."""
        h = SATIR * self.b * satir
        if not self.sayfa:
            return
        if self._kalan() < h:
            self._yeni()
            return
        self.sayfa.append(("metin", {"satirlar": [""], "boyut": self.b, "kalin": False, "once": 0.0}, h))
        self.y += h

    def sayfa_sonu(self):
        if self.sayfa:
            self._yeni()

    def tablo(self, tablo):
        sutun = len(tablo["basliklar"])
        karakter = max(4, int(self.g / sutun / (KARAKTER_ORANI * TABLO_YAZI)))

        def yuk(satir):
            return max(len(_satirlar(str(h), karakter)) for h in satir) * SATIR * TABLO_YAZI + TABLO_DOLGU

        govde = [(s, False) for s in tablo["satirlar"]] + [(s, True) for s in tablo.get("toplamlar", [])]
        bas_h = yuk(tablo["basliklar"])
        while govde:
            if self._kalan() < bas_h + yuk(govde[0][0]) + 6:
                self._yeni()
            satirlar, h, yukler = [], bas_h, [bas_h]
            while govde and (h + yuk(govde[0][0])) * 1.1 + 6 <= self._kalan():
                yukler.append(yuk(govde[0][0]))
                h += yukler[-1]
                satirlar.append(govde.pop(0))
            if not satirlar:            # tek satır bile sığmıyor (çok uzun hücre): yine de yerleştir
                yukler.append(yuk(govde[0][0]))
                h += yukler[-1]
                satirlar.append(govde.pop(0))
            pay = 6 + 0.1 * h   # LibreOffice / PowerPoint satırları yazıya göre biraz büyütebilir: tablo altına pay
            self.sayfa.append(("tablo", {"basliklar": tablo["basliklar"], "satirlar": satirlar, "yukler": yukler}, h + pay))
            self.y += h + pay
            if govde:
                self._yeni()

    def bitir(self):
        if self.sayfa:
            self.sayfalar.append(self.sayfa)
        return self.sayfalar or [[]]


def sayfala(bloklar, genislik_pt, yukseklik_pt, boyut):
    """bloklar: [{'baslik', 'tur': 'metin'|'tablo'|'aciklamalar', 'metin'|'tablo'|'ogeler'}] → sayfa listesi."""
    d = Duzen(genislik_pt, yukseklik_pt, boyut)
    for b in bloklar:
        if b.get("baslik"):
            d.paragraf(b["baslik"], boyut + 4, kalin=True, once=BOLUM_ARASI, sonra=BASLIK_SONRASI, baslik=True)
        if b["tur"] == "metin":
            metin = re.sub(r"\{\{\s*(bosluk|sayfa_sonu)\s*\}\}", lambda m: "\n{{" + m.group(1) + "}}\n", b.get("metin") or "")
            satirlar = metin.split("\n")
            onceki_bos = False
            for satir in satirlar:   # her satır sonu ayrı paragraf
                satir = satir.strip()
                if satir == BOSLUK:
                    d.bosluk()
                elif satir == SAYFA_SONU:
                    d.sayfa_sonu()
                elif satir:
                    d.paragraf(satir, boyut, once=6 if onceki_bos else 0, sonra=3)
                onceki_bos = not satir
        elif b["tur"] == "tablo" and b.get("tablo"):
            d.tablo(b["tablo"])
        elif b["tur"] == "aciklamalar":
            for o in b.get("ogeler") or []:
                d.paragraf(o["ad"], boyut, kalin=True, once=4, sonra=2, baslik=True)
                onceki_bos = False
                for satir in (o.get("aciklama") or "").split("\n"):   # açıklamanın her satırı ayrı paragraf
                    if satir.strip():
                        d.paragraf(satir.strip(), boyut, once=6 if onceki_bos else 0, sonra=3)
                    onceki_bos = not satir.strip()
    return d.bitir()


R_ATTR = ("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed",
          "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
          "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link")


def slayt_kopyala(sunum, kaynak, sonra_indeks):
    """Slaytı (şekiller, resimler, bağlantılar) kopyalar ve sonra_indeks'ten hemen sonraya koyar."""
    yeni = sunum.slides.add_slide(kaynak.slide_layout)
    for sh in list(yeni.shapes):
        sh._element.getparent().remove(sh._element)
    esle = {}
    for rid, rel in kaynak.part.rels.items():
        if rel.reltype.endswith("/notesSlide") or rel.reltype.endswith("/slideLayout"):
            continue
        esle[rid] = (yeni.part.rels.get_or_add_ext_rel(rel.reltype, rel.target_ref) if rel.is_external
                     else yeni.part.relate_to(rel.target_part, rel.reltype))
    for el in kaynak.shapes._spTree.iterchildren():
        if el.tag.rsplit("}", 1)[-1] in ("nvGrpSpPr", "grpSpPr"):
            continue
        k = copy.deepcopy(el)
        for e in k.iter():
            for a in R_ATTR:
                if e.get(a) in esle:
                    e.set(a, esle[e.get(a)])
        yeni.shapes._spTree.append(k)
    arka = kaynak._element.find("{*}cSld/{*}bg")
    if arka is not None:
        yeni._element.cSld.insert(0, copy.deepcopy(arka))
    liste = sunum.slides._sldIdLst
    sld = list(liste)[-1]
    liste.remove(sld)
    liste.insert(sonra_indeks + 1, sld)
    return yeni


def _metin_kutusu(slayt, x, y, g, h, satir_listesi, yazi):
    ad, _, renk = yazi
    tb = slayt.shapes.add_textbox(x, y, g, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for a in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, a, 0)
    ilk = True
    for satirlar, boyut, kalin, once in satir_listesi:
        p = tf.paragraphs[0] if ilk else tf.add_paragraph()
        ilk = False
        p.space_before = Pt(once)
        r = p.add_run()
        r.text = " ".join(satirlar)
        r.font.size, r.font.bold = Pt(boyut), kalin
        if ad:
            r.font.name = ad
        if renk:
            r.font.color.rgb = RGBColor.from_string(renk)
    return tb


def _tablo(slayt, x, y, g, veri, yazi):
    ad, _, renk = yazi
    satirlar = [(veri["basliklar"], True)] + veri["satirlar"]
    sutun = len(veri["basliklar"])
    t = slayt.shapes.add_table(len(satirlar), sutun, x, y, g, Emu(Pt(sum(veri["yukler"])))).table
    for r, h in enumerate(veri["yukler"]):
        t.rows[r].height = Emu(Pt(h))
    for r, (satir, kalin) in enumerate(satirlar):
        for c in range(sutun):
            hucre = t.cell(r, c)
            hucre.margin_top = hucre.margin_bottom = Pt(TABLO_DOLGU / 2)
            tf = hucre.text_frame
            tf.text = str(satir[c]) if c < len(satir) else ""
            for p in tf.paragraphs:
                for run in p.runs:
                    run.font.size, run.font.bold = Pt(TABLO_YAZI), (r == 0 or kalin)
                    if ad:
                        run.font.name = ad


def uygula(sunum, bloklar):
    """Akış slaytını bloklarla doldurur, gerekirse çoğaltır. Döner: üretilen içerik sayfası sayısı (0 = akış yok)."""
    indeks, kutu = akis_slayti(sunum)
    if indeks is None:
        return 0
    kaynak = sunum.slides[indeks]
    yazi = _yazi(kutu)
    x, y, g, h = kutu.left, kutu.top, kutu.width, kutu.height
    kutu._element.getparent().remove(kutu._element)
    if not bloklar:
        liste = sunum.slides._sldIdLst
        sld = list(liste)[indeks]
        sunum.part.drop_rel(sld.rId)
        liste.remove(sld)
        return 0
    sayfalar = sayfala(bloklar, Emu(g).pt, Emu(h).pt, yazi[1])
    slaytlar = [kaynak] + [None] * (len(sayfalar) - 1)
    for k in range(1, len(sayfalar)):
        slaytlar[k] = slayt_kopyala(sunum, kaynak, indeks + k - 1)
    for slayt, sayfa in zip(slaytlar, sayfalar):
        cy = y
        metinler, metin_h = [], 0.0

        def bosalt():
            nonlocal cy, metinler, metin_h
            if metinler:
                # Yeni kutunun ilk paragrafındaki üst boşluğu PowerPoint / LibreOffice uygulamıyor (16 Kas, tablodan
                # sonra başlık yapışıktı): boşluk kutunun konumuna eklenir
                if cy > y and metinler[0][3]:
                    cy += Emu(Pt(metinler[0][3]))
                    metin_h -= metinler[0][3]
                    metinler[0] = metinler[0][:3] + (0.0,)
                _metin_kutusu(slayt, x, cy, g, Emu(Pt(metin_h)), metinler, yazi)
                cy += Emu(Pt(metin_h))
                metinler, metin_h = [], 0.0

        for tur, veri, yuk in sayfa:
            if tur == "metin":
                metinler.append((veri["satirlar"], veri["boyut"], veri["kalin"], veri["once"]))
                metin_h += yuk
            else:
                bosalt()
                _tablo(slayt, x, cy, g, veri, yazi)
                cy += Emu(Pt(yuk))
        bosalt()
    return len(sayfalar)

