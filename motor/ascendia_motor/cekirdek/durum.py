"""Paylaşılan durum: kurlar, raporlama ayarları, dönemler, açık paketler, kuyruk kilidi."""
import threading


class Durum:
    kurlar = {}          # kod -> (TRY karşılığı, tarih)
    raporlama = None
    mali_ay = 1          # mali yıl başlangıç ayı
    esik = 20            # geçmiş veriye geçiş eşiği (aşama başına kapanmış fırsat)
    ceyrekler = []       # [(başlangıç, bitiş, ad)] çeyrek dönemleri
    donemler = []        # [(tür, başlangıç, bitiş, ad, id, isCurrent)] tüm dönemler
    hedef_tipi = "QUARTER"
    acik_paketler = None
    rakip_gun = 90
    varsayilan_kdv = None       # CRM Ayarı → Varsayılan KDV % (Paraşüt faturası; yoksa kalemde olmalı)
    teklif_hatirlatma_gun = 3   # teklif geçerliliği bitmeden kaç gün önce hatırlatılır (CRM Ayarı)        # rakip sözleşme bitişine kaç gün kala hatırlatılır (CRM Ayarı)  # CRM Ayarı → Açık Paketler (boş = hepsi açık)
    kilit = threading.Lock()
