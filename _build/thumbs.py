"""Уменьшенные копии фото для карточек: assets/listings/thumbs/<имя>-640.webp (ширина 640 px).

Карточки показывают фото шириной ~350 px, а оригиналы — ~1400 px и до 200 КБ. Сборка (build.py) добавляет srcset,
если копия есть, — браузер сам берёт маленькую или большую. Запускать после добавления объектов:
python3 _build/thumbs.py (нужен Pillow).
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
from data.listings import LISTINGS  # noqa: E402

OUT = ROOT / "assets" / "listings" / "thumbs"
OUT.mkdir(parents=True, exist_ok=True)
n = size = 0
for it in LISTINGS:
    for ph in (it.get("photos") or [])[:2]:  # первое фото — карточки и обложки, второе — статьи с малым числом объектов
        src = ROOT / ph
        dst = OUT / (src.stem + "-640.webp")
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        im = Image.open(src).convert("RGB")
        if im.width <= 700:
            continue
        im.resize((640, round(im.height * 640 / im.width)), Image.LANCZOS).save(dst, "WEBP", quality=76, method=6)
        n += 1
        size += dst.stat().st_size
print(f"готово: {n} копий, {size // 1024} КБ")
