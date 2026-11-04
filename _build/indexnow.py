"""Отправить все страницы из sitemap.xml в IndexNow (Яндекс и Bing узнают о них сразу, без ручного переобхода).

Запускать после публикации изменений (файл ключа /<ключ>.txt уже должен открываться на сайте):
python3 _build/indexnow.py            — все страницы
python3 _build/indexnow.py /besedki/  — только указанные адреса
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
from data.site import SITE  # noqa: E402

key = SITE["indexnow_key"]
base = SITE["base_url"]
urls = [base + u if u.startswith("/") else u for u in sys.argv[1:]] or re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text())
body = json.dumps({"host": SITE["domain"], "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls}).encode()
for endpoint in ("https://yandex.com/indexnow", "https://api.indexnow.org/indexnow"):
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(endpoint, r.status, len(urls), "адресов")
    except urllib.error.HTTPError as err:
        print(endpoint, err.code, err.read()[:300].decode("utf-8", "replace"))
