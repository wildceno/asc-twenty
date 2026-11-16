#!/usr/bin/env python3
"""Son başarılı yedeğin zamanını Twenty'deki Sistem Durumu kaydına yazar (liste 7).
yedek.sh başarıdan sonra çağırır; elle de çalıştırılabilir (yedek.log'daki son "yedek tamam" satırını okur)."""
import datetime as dt
import json
import os
import urllib.request

LOG = os.path.expanduser("~/twenty/backups/gunluk/yedek.log")
KEY = open(os.path.expanduser("~/twenty/.twenty-api-key")).read().strip()
B = "http://localhost:3010"


def istek(m, yol, govde=None):
    r = urllib.request.Request(B + yol, method=m, data=json.dumps(govde).encode() if govde is not None else None,
                               headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=30).read() or b"{}")


son = [l for l in open(LOG, encoding="utf-8") if " yedek tamam:" in l]
if not son:
    raise SystemExit("yedek.log'da başarılı yedek yok")
zaman = dt.datetime.fromisoformat(son[-1].split(" ", 1)[0]).astimezone(dt.timezone.utc)
iso = zaman.isoformat(timespec="seconds").replace("+00:00", "Z")
kayit = istek("GET", "/rest/systemStatuses?limit=1")["data"]["systemStatuses"]
if kayit:
    istek("PATCH", f"/rest/systemStatuses/{kayit[0]['id']}", {"lastBackupAt": iso})
else:
    istek("POST", "/rest/systemStatuses", {"name": "Sistem", "lastBackupAt": iso})
print("Sistem Durumu: son yedek", iso)
