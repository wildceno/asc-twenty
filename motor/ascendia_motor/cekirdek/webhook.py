"""Webhook: Twenty olaylarını HMAC imzasıyla doğrular, açık paketlerin işlerine çevirip kuyruğa ekler."""
from http.server import BaseHTTPRequestHandler
import hashlib
import hmac
import json

from ascendia_motor.cekirdek.ayar import SECRET_FILE
from ascendia_motor.cekirdek.gunluk import log, oku
from ascendia_motor.paketler.saglik import olay
from ascendia_motor.cekirdek import paketler
from ascendia_motor.cekirdek.kuyruk import ekle


class Webhook(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def yanit(self, kod, govde=b"ok"):
        self.send_response(kod)
        self.end_headers()
        self.wfile.write(govde)

    def do_GET(self):
        self.yanit(200 if self.path == "/saglik" else 404)

    def do_POST(self):
        govde = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        zaman, imza = self.headers.get("X-Twenty-Webhook-Timestamp", ""), self.headers.get("X-Twenty-Webhook-Signature", "")
        beklenen = hmac.new(oku(SECRET_FILE).encode(), zaman.encode() + b":" + govde, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(beklenen, imza):
            log("imza geçersiz, reddedildi")
            return self.yanit(401, b"imza")
        try:
            olay = json.loads(govde)
        except ValueError:
            return self.yanit(400, b"json")
        ad = olay.get("eventName") or olay.get("event") or ""
        kayit = dict(olay.get("record") or olay.get("data") or {})
        kayit["_degisen"] = olay.get("updatedFields") or []   # Twenty yalnız değişen alan adlarını gönderir
        for anahtar in paketler.olay_isleri(ad, kayit):   # hangi paket hangi olayı dinliyor: paketlerin OLAYLAR'ı
            ekle(anahtar)
        self.yanit(200)
