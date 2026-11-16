"""Ascendia hesap motoru (Twenty için) — başlatıcı. Çalıştırma: python3 -m ascendia_motor

Twenty çekirdeğine dokunmadan webhook + REST API ile çalışır. Çekirdek (cekirdek/) ortak altyapıdır; iş kuralları
paketlerdedir (paketler/: satış süreci, hedefler, takip, sağlık) ve CRM Ayarı → Açık Paketler ile müşteri bazında
açılıp kapatılır (boş = hepsi açık). Kararlar: kararlar/2026-11-11-satis-sureci-ve-hesap-motoru.md,
2026-11-13-takip-kurallari.md, 2026-11-13-crm-support-portali.md. Yalnız Python standart kütüphanesi.
"""
import threading
from http.server import ThreadingHTTPServer

from ascendia_motor.cekirdek.ayar import API, KEY_FILE, PORT, SECRET_FILE
from ascendia_motor.cekirdek.gunluk import log, oku
from ascendia_motor.cekirdek.kuyruk import isci
from ascendia_motor.cekirdek.webhook import Webhook
from ascendia_motor.cekirdek.zamanlayici import zamanlayici
from ascendia_motor.paketler.saglik import bekci

if __name__ == "__main__":
    oku(KEY_FILE), oku(SECRET_FILE)  # sırlar yoksa hemen dur
    threading.Thread(target=isci, daemon=True).start()
    threading.Thread(target=zamanlayici, daemon=True).start()
    threading.Thread(target=bekci, daemon=True).start()   # takılma bekçisi her zaman; sağlık turu SAGLIK paketiyle
    log(f"hesap motoru dinliyor :{PORT}, API {API}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Webhook).serve_forever()
