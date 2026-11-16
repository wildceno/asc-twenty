"""Nötr örnek teklif şablonları (test için; uydurma rakam ya da müşteri bilgisi yok, yalnız yer tutucu ve genel metin).
Kullanım: python3 -m testler.ornek_uret <klasör>  → ornek-sablon.docx, ornek-sablon.pptx"""
import io
import sys


def docx_ornek():
    from docx import Document
    d = Document()
    d.sections[0].header.paragraphs[0].text = "Teklif {{teklif_no}}"
    d.add_paragraph("Teklif", style="Title")
    d.add_paragraph("{{musteri_adi}} için hazırlanmıştır · {{teklif_tarihi}}")
    d.add_heading("Hakkımızda", level=1)
    d.add_paragraph("Şirketimizi tanıtan sabit metin buraya yazılır.")
    d.add_heading("Mevcut durum", level=1)
    d.add_paragraph("{{musteri_durumu}}")
    d.add_heading("Teklif", level=1)
    d.add_paragraph("{{kalem_tablosu}}")
    d.add_paragraph("Toplam: {{toplam}}")
    d.add_heading("Ürün açıklamaları", level=1)
    d.add_paragraph("{{urun_aciklamalari}}")
    d.add_heading("Ticari koşullar", level=1)
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Geçerlilik", "{{gecerlilik}}"
    t.cell(1, 0).text, t.cell(1, 1).text = "Süre", "{{sure_ay}} ay"
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def pptx_ornek():
    from pptx import Presentation
    from pptx.util import Inches
    p = Presentation()
    def slayt(baslik, metin, notu=None, duzen=1):
        s = p.slides.add_slide(p.slide_layouts[duzen])
        if baslik is not None:
            s.shapes.title.text = baslik
        if metin is not None:
            s.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(1)).text_frame.text = metin
        if notu:
            s.notes_slide.notes_text_frame.text = notu
        return s
    slayt("{{musteri_adi}} için teklif", "{{teklif_tarihi}}", duzen=0)
    slayt("Hakkımızda", "Şirketimizi tanıtan sabit metin.")
    slayt("Çözüm yaklaşımı", "{{cozum_ozeti}}", "bölüm: Çözüm")
    slayt("Çözüm adımları", "Adımlar burada anlatılır.", "Bölüm: Çözüm")
    slayt("Teklif", "{{kalem_tablosu}}")
    slayt(None, "Teşekkürler", duzen=6)
    b = io.BytesIO()
    p.save(b)
    return b.getvalue()


if __name__ == "__main__":
    klasor = sys.argv[1] if len(sys.argv) > 1 else "."
    for ad, f in (("ornek-sablon.docx", docx_ornek), ("ornek-sablon.pptx", pptx_ornek)):
        with open(f"{klasor}/{ad}", "wb") as fh:
            fh.write(f())
        print(f"{klasor}/{ad}")


# 1×1 piksel PNG (resimli slaytın kopyalanmasını sınamak için)
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cfc00000030101005b3a4a5f0000000049454e44ae426082")


def pptx_akis_ornek():
    """Akış şablonu örneği: kapak, içerik slaytı ({{icerik}} + resim + alt bilgi), son kapak."""
    from pptx import Presentation
    from pptx.util import Cm
    p = Presentation()
    p.slide_width, p.slide_height = Cm(21), Cm(29.7)
    bos = p.slide_layouts[6]
    s1 = p.slides.add_slide(bos)
    s1.shapes.add_textbox(Cm(2), Cm(20), Cm(15), Cm(1)).text_frame.text = "Hazırlanan: {{musteri_adi}}"
    s1.notes_slide.notes_text_frame.text = "bölüm: Ana kapak"
    s2 = p.slides.add_slide(bos)
    s2.shapes.add_picture(io.BytesIO(PNG), Cm(17), Cm(1), Cm(3), Cm(1))
    s2.shapes.add_textbox(Cm(2), Cm(27), Cm(15), Cm(0.6)).text_frame.text = "Alt bilgi · Teklif {{teklif_no}}"
    s2.shapes.add_textbox(Cm(2), Cm(4), Cm(17), Cm(22)).text_frame.text = "{{icerik}}"
    s2.notes_slide.notes_text_frame.text = "bölüm: İçerik"
    s3 = p.slides.add_slide(bos)
    s3.shapes.add_textbox(Cm(2), Cm(20), Cm(15), Cm(1)).text_frame.text = "Son kapak · {{musteri_adi}}"
    s3.notes_slide.notes_text_frame.text = "bölüm: Son kapak"
    b = io.BytesIO()
    p.save(b)
    return b.getvalue()
