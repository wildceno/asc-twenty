"""HTTP sunucusu. Yalnız Twenty ağı içinden erişilir (dışarıya port açılmaz); sır tutmaz, Twenty'ye bağlanmaz.
POST /oku   gövde: .docx / .pptx baytları → JSON (oku.oku)
POST /uret  gövde JSON {'sablon': base64, ...doldur.uret girdisi} → JSON {'uzanti', 'belge': base64, 'pdf': base64|null, 'uyarilar'}
GET  /saglik → {"ok": true, "surumler": {...}}
"""
import base64
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version

from belge_servisi.doldur import uret
from belge_servisi.oku import OkumaHatasi, oku

PORT = int(os.environ.get("PORT", "8090"))
AZAMI = 30 * 1024 * 1024
AZAMI_JSON = 45 * 1024 * 1024   # base64 şablon + veri


def _libreoffice():
    try:
        return subprocess.run(["soffice", "--version"], capture_output=True, timeout=30).stdout.decode().strip()
    except Exception as e:   # noqa: BLE001
        return f"yok ({e})"


LIBREOFFICE = _libreoffice()


class Isleyici(BaseHTTPRequestHandler):
    def _yanit(self, kod, govde):
        b = json.dumps(govde, ensure_ascii=False).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/saglik":
            return self._yanit(200, {"ok": True, "surumler": {**{p: version(p) for p in ("python-docx", "python-pptx")},
                                                              "libreoffice": LIBREOFFICE}})
        self._yanit(404, {"hata": "yok"})

    def do_POST(self):
        uzunluk = int(self.headers.get("Content-Length") or 0)
        if self.path == "/uret":
            return self._uret(uzunluk)
        if self.path != "/oku":
            return self._yanit(404, {"hata": "yok"})
        if not uzunluk or uzunluk > AZAMI:
            return self._yanit(400, {"hata": f"dosya boş ya da {AZAMI // 1048576} MB'tan büyük"})
        veri = self.rfile.read(uzunluk)
        try:
            self._yanit(200, oku(veri))
        except OkumaHatasi as e:
            self._yanit(422, {"hata": str(e)})
        except Exception as e:   # noqa: BLE001 — bozuk dosya servisi düşürmesin
            self._yanit(422, {"hata": f"Dosya okunamadı: {type(e).__name__}: {str(e)[:300]}"})

    def _uret(self, uzunluk):
        if not uzunluk or uzunluk > AZAMI_JSON:
            return self._yanit(400, {"hata": "istek boş ya da çok büyük"})
        try:
            girdi = json.loads(self.rfile.read(uzunluk))
            s = uret(base64.b64decode(girdi.pop("sablon")), girdi)
            self._yanit(200, {"uzanti": s["uzanti"], "belge": base64.b64encode(s["belge"]).decode(),
                              "pdf": base64.b64encode(s["pdf"]).decode() if s["pdf"] else None, "uyarilar": s["uyarilar"]})
        except OkumaHatasi as e:
            self._yanit(422, {"hata": str(e)})
        except Exception as e:   # noqa: BLE001
            self._yanit(422, {"hata": f"Belge üretilemedi: {type(e).__name__}: {str(e)[:300]}"})

    def log_message(self, *a):
        pass


print(f"belge servisi dinliyor :{PORT}", flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), Isleyici).serve_forever()
