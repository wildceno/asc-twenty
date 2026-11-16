# Ascendia hesap motoru

Twenty çekirdeğine dokunmadan çalışan iş kuralları servisi: Twenty değişiklikleri webhook ile bildirir, motor hesaplayıp
REST API ile geri yazar. Tek konteyner (`hesap-motoru`), yalnız Python standart kütüphanesi.

Yapı (7c, kullanıcı kararı 13 Kas 2026: tek servis, ayrı paketler, müşteri bazında aç/kapat; entegrasyonlar ayrı servis):

```
ascendia_motor/
  __main__.py        başlatıcı: işçi, zamanlayıcı, bekçi, webhook sunucusu
  cekirdek/          her zaman açık ortak altyapı
    ayar             ortam değişkenleri, aşama kümeleri, kilitli alanlar
    gunluk           log + hata sayacı, bekçi işaretleri
    twenty           REST / GraphQL, dakikada 100 istek sınırı (80'de tutulur), 429'da yeniden dener
    para, durum, donemler, yukle, kur
    kuyruk           tek işçi, iş birleştirme, "hepsi" toplu işi
    zamanlayici      TCMB kuru, periyodik işler
    webhook          HMAC doğrulama, olayları paketlere dağıtma
    paketler         paket kaydı ve aç/kapat (CRM Ayarı → Açık Paketler; boş = hepsi açık)
  paketler/
    satis_sureci     aşama kuralları, kapanış ve kilit, hesaplar, sözleşme, fırsat açma denetimi
    hedefler         hedef gerçekleşmesi, forecast, dönüşüm oranları
    takip            son temas, temassız gün, takip durumu (görevi Takip iş akışı açar)
    saglik           sağlık turu, Sistem Durumu / Alarmları, Admin görevi, crm-support olayları
```

## Yeni paket eklemek
1. `ascendia_motor/paketler/<ad>.py`: işlevler + paket tanımı (`AD`, `OLAYLAR`, `ISLER`, gerekirse `SONRAKI`,
   `BIRLESTIRME`, `PERIYODIK`, `tumunu_isle`). Ayrıntı: `cekirdek/paketler.py` başındaki açıklama.
2. `cekirdek/paketler.py` → `SIRA` listesine ekle.
3. `metadata/16_paketler.py` → Açık Paketler seçeneğine ekle; dinlediği olaylar `ops/motor-kur.sh` webhook listesinde olmalı.
4. Paketler çekirdeği kullanır, birbirini doğrudan çağırmaz (zincir `SONRAKI` ile kuyruk üzerinden).

## Testler
- Yerel: `cd motor && python3 testler/ad_denetimi.py && python3 -m unittest discover -s testler`
- Sunucuda uçtan uca (deneme ortamı, test kayıtlarını siler): `ops/hesap-testi.py`, `ops/rol-testi.py`,
  `ops/takip-testi.py kur|dogrula|temizle`; davranış karşılaştırma: `ops/anlik-goruntu.py al|karsilastir`.
- Testler motorla aynı API anahtarını kullanır: arka arkaya koşarken aralarında ~1 dk bekle.

## Kurulum
`ops/dagit.sh` → sunucuda `ops/motor-kur.sh` (idempotent: webhook sırrı, Twenty compose eki, derleme, webhook olayları).
