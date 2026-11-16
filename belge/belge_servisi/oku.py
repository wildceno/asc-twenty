"""Şablon okuma (liste 15a): Word / PowerPoint dosyasından bölümler ve {{yer_tutucu}} işaretleri.

Kurallar (kullanıcı kararı 14 Kas 2026, plan: CRM/kararlar/2026-11-13-teklif-modulu-plan.md):
- Word: her "Başlık 1" (Heading 1) paragrafı yeni bölüm başlatır; ilk başlıktan önceki içerik "Ana kapak".
  Üst bilgi / alt bilgideki yer tutucular "Ana kapak"a değil şablonun geneline yazılır.
- PowerPoint: her slayt bir bölüm (ad = slayt başlığı; ilk slayt "Ana kapak"). Slayt notunda `bölüm: Ad` varsa o ada katılır; aynı adlı
  ardışık slaytlar tek bölümdür.
Saf işlevler: girdi dosya baytları, çıktı sözlük. Dosyaya yazmaz, ağa çıkmaz.
"""
import io
import re
import zipfile

YER_TUTUCU = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
NOT_BOLUM = re.compile(r"^\s*b[öo]l[üu]m\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
BASLIK1_ADLARI = {"heading 1", "başlık 1", "baslik 1"}
BASLIK1_KIMLIKLERI = {"Heading1", "Balk1"}   # Türkçe Word'de Başlık 1 stil kimliği "Balk1"
ONIZLEME = 240


class OkumaHatasi(Exception):
    pass


def bicim_bul(veri):
    try:
        adlar = set(zipfile.ZipFile(io.BytesIO(veri)).namelist())
    except zipfile.BadZipFile:
        raise OkumaHatasi("Dosya .docx ya da .pptx değil (eski .doc / .ppt biçimi desteklenmez; Word / PowerPoint'te "
                          "'Farklı kaydet' ile .docx / .pptx yapın).")
    if "word/document.xml" in adlar:
        return "DOCX"
    if "ppt/presentation.xml" in adlar:
        return "PPTX"
    raise OkumaHatasi("Dosya Word (.docx) ya da PowerPoint (.pptx) değil.")


def yer_tutucular(metin):
    out = []
    for m in YER_TUTUCU.finditer(metin or ""):
        ad = m.group(1).strip()
        if ad and ad not in out:
            out.append(ad)
    return out


def _bolum(ad, sira, kaynak, metinler):
    metin = "\n".join(t for t in metinler if t and t.strip())
    return {"ad": ad, "sira": sira, "kaynak": kaynak, "yer_tutucular": yer_tutucular(metin),
            "onizleme": re.sub(r"\s+", " ", metin).strip()[:ONIZLEME]}


def _baslik1_mi(paragraf):
    stil = paragraf.style
    while stil is not None:
        if (stil.name or "").strip().lower() in BASLIK1_ADLARI or stil.style_id in BASLIK1_KIMLIKLERI:
            return True
        stil = stil.base_style
    return False


def docx_bolumleri(belge):
    """Gövde öğelerini bölümlere ayırır (okuma ve doldurma aynı kuralı kullanır). Boş ana kapak bölüm sayılmaz.
    Döner: [{'ad', 'ogeler': [xml öğesi], 'bas', 'son', 'metinler'}]."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    bolumler, cari, sayac = [], {"ad": "Ana kapak", "ogeler": [], "bas": 1, "metinler": []}, 0

    def kapat(son):
        if cari["ad"] != "Ana kapak" or any(t.strip() for t in cari["metinler"]):
            bolumler.append({**cari, "son": son})

    for oge in belge.element.body.iterchildren():
        etiket = oge.tag.rsplit("}", 1)[-1]
        if etiket == "p":
            sayac += 1
            p = Paragraph(oge, belge)
            if _baslik1_mi(p) and p.text.strip():
                kapat(sayac - 1)
                cari = {"ad": p.text.strip(), "ogeler": [oge], "bas": sayac, "metinler": [p.text]}
                continue
            cari["ogeler"].append(oge)
            cari["metinler"].append(p.text)
        elif etiket == "tbl":
            sayac += 1
            cari["ogeler"].append(oge)
            for satir in Table(oge, belge).rows:
                for hucre in satir.cells:
                    cari["metinler"].append(hucre.text)
    kapat(sayac)
    return bolumler


def docx_ust_alt(belge):
    """Üst / alt bilgi paragrafları (bağlı olmayanlar)."""
    for bolum in belge.sections:
        for parca in (bolum.header, bolum.footer, bolum.first_page_header, bolum.first_page_footer):
            if parca is not None and not parca.is_linked_to_previous:
                yield from parca.paragraphs
                for t in parca.tables:
                    for satir in t.rows:
                        for hucre in satir.cells:
                            yield from hucre.paragraphs


def oku_docx(veri):
    from docx import Document

    belge = Document(io.BytesIO(veri))
    bolumler = [_bolum(b["ad"], n, f"paragraf {b['bas']}–{b['son']}", b["metinler"])
                for n, b in enumerate(docx_bolumleri(belge), 1)]
    genel = [p.text for p in docx_ust_alt(belge)]
    uyarilar = []
    if not any(b["ad"] != "Ana kapak" for b in bolumler):
        uyarilar.append("Dosyada 'Başlık 1' biçiminde başlık yok: tüm içerik tek bölüm ('Ana kapak') olarak okundu. "
                        "Bölüm başlıklarına Word'de 'Başlık 1' stilini verin.")
    return bolumler, yer_tutucular("\n".join(genel)), uyarilar


def _sekil_metinleri(sekiller):
    for s in sekiller:
        if getattr(s, "shape_type", None) == 6 and hasattr(s, "shapes"):   # grup
            yield from _sekil_metinleri(s.shapes)
            continue
        if getattr(s, "has_text_frame", False) and s.has_text_frame:
            yield s.text_frame.text
        if getattr(s, "has_table", False) and s.has_table:
            for satir in s.table.rows:
                for hucre in satir.cells:
                    yield hucre.text


def pptx_bolumleri(sunum):
    """Slaytları bölümlere ayırır (okuma ve doldurma aynı kuralı kullanır).
    Döner: ([{'ad', 'slaytlar': [0'dan indeks], 'metinler'}], uyarılar). Tekrarlayan adlara numara eklenir."""
    bolumler, uyarilar = [], []
    for i, slayt in enumerate(sunum.slides, 1):
        notlar = slayt.notes_slide.notes_text_frame.text if slayt.has_notes_slide and slayt.notes_slide.notes_text_frame else ""
        m = NOT_BOLUM.search(notlar or "")
        baslik = (slayt.shapes.title.text.strip() if slayt.shapes.title is not None and slayt.shapes.title.has_text_frame else "")
        ad = m.group(1) if m else ("Ana kapak" if i == 1 else baslik) or f"Slayt {i}"   # ilk slayt Word'deki gibi kapak
        metinler = list(_sekil_metinleri(slayt.shapes))
        if bolumler and bolumler[-1]["ad"] == ad:
            bolumler[-1]["slaytlar"].append(i - 1)
            bolumler[-1]["metinler"].extend(metinler)
        else:
            bolumler.append({"ad": ad, "slaytlar": [i - 1], "metinler": metinler})
        if not m and not baslik and i > 1:
            uyarilar.append(f"Slayt {i}: başlık yok; bölüm adı 'Slayt {i}' verildi (slayta başlık ya da notuna 'bölüm: Ad' ekleyin).")
    adlar = [b["ad"] for b in bolumler]
    for ad in sorted({a for a in adlar if adlar.count(a) > 1}):
        uyarilar.append(f"'{ad}' adı ardışık olmayan slaytlarda tekrar ediyor: ayrı bölümler olarak okundu (ada numara eklendi).")
        k = 0
        for b in bolumler:
            if b["ad"] == ad:
                k += 1
                b["ad"] = f"{ad} ({k})"
    return bolumler, uyarilar


def oku_pptx(veri):
    from pptx import Presentation

    bolumler, uyarilar = pptx_bolumleri(Presentation(io.BytesIO(veri)))
    sonuc = []
    for n, b in enumerate(bolumler, 1):
        s1, s2 = b["slaytlar"][0] + 1, b["slaytlar"][-1] + 1
        sonuc.append(_bolum(b["ad"], n, f"slayt {s1}" if s1 == s2 else f"slayt {s1}–{s2}", b["metinler"]))
    return sonuc, [], uyarilar


def oku(veri):
    """Dosya baytları → {'bicim', 'bolumler', 'genel_yer_tutucular', 'yer_tutucular', 'uyarilar'}."""
    bicim = bicim_bul(veri)
    bolumler, genel, uyarilar = (oku_docx if bicim == "DOCX" else oku_pptx)(veri)
    hepsi = list(genel)
    for b in bolumler:
        hepsi.extend(y for y in b["yer_tutucular"] if y not in hepsi)
    adlar = [b["ad"] for b in bolumler]
    for ad in sorted({a for a in adlar if adlar.count(a) > 1}):
        uyarilar.append(f"'{ad}' adında birden fazla bölüm var; ad değişirse seçimler eşleşmeyebilir.")
    return {"bicim": bicim, "bolumler": bolumler, "genel_yer_tutucular": genel, "yer_tutucular": hepsi, "uyarilar": uyarilar}
