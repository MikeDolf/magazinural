"""Картинки типов построек для квиза и калькулятора: assets/img/calc/<key>.webp (360×240).

Берём первое фото нашего объекта раздела (если объектов нет — проекта). Запускать после изменения
объектов или data/calc.py: python3 _build/calc_thumbs.py (нужен Pillow).
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
from data.calc import CALC  # noqa: E402
from data.listings import LISTINGS  # noqa: E402

PHOTO_FROM = {"saray": "hozblok"}
OUT = ROOT / "assets" / "img" / "calc"
OUT.mkdir(parents=True, exist_ok=True)
for t in CALC:
    # сараев-объектов пока нет: берём проект хозблока-сарая
    sec = PHOTO_FROM.get(t["key"], t["key"])
    items = sorted((x for x in LISTINGS if x["section"] == sec and x.get("photos")), key=lambda x: x.get("kind") == "project")
    if sec != t["key"]:
        items = [x for x in items if x.get("kind") == "project"][3:] or items
    if not items:
        print("нет фото:", t["key"])
        continue
    im = ImageOps.fit(Image.open(ROOT / items[0]["photos"][0]).convert("RGB"), (360, 240), Image.LANCZOS)
    im.save(OUT / f'{t["key"]}.webp', "WEBP", quality=72, method=6)
    print(t["key"], items[0]["id"], (OUT / f'{t["key"]}.webp').stat().st_size)
