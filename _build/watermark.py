#!/usr/bin/env python3
"""Наш водяной знак «Магазин Урал» на фото объектов.

    python3 _build/watermark.py

Чистые версии (без знака) лежат в semantics/listings-clean/ — локально, в репозиторий не идут.
Если чистой версии ещё нет, текущий файл из assets/listings/ считается чистым и копируется туда.
Знак всегда накладывается на чистую версию, поэтому повторный запуск не задваивает его.
Шаблон _build/watermark.png (1080×720, прозрачный фон) рисует _build/watermark-template.js;
он стоит там же, где стоял знак старого сайта, и закрывает его остатки на фото 1080×720.
"""
import io
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "listings"
CLEAN = ROOT / "semantics" / "listings-clean"
WM = Image.open(ROOT / "_build" / "watermark.png").convert("RGBA")
# горизонтальный вариант для фото 900×600 со знаком по центру (курятники, k*): закрывает остаток старой надписи
WM_H = Image.open(ROOT / "_build" / "watermark-900h.png").convert("RGBA")


def mark(img, name=""):
    w, h = img.size
    if name.startswith("k") and (w, h) == WM_H.size:
        return Image.alpha_composite(img.convert("RGBA"), WM_H).convert("RGB")
    if (w, h) == WM.size:
        wm = WM
    else:  # вписываем шаблон по ширине и центрируем
        k = w / WM.width
        wm = WM.resize((w, round(WM.height * k)), Image.LANCZOS)
        layer = Image.new("RGBA", (w, h))
        layer.paste(wm, (0, (h - wm.height) // 2))
        wm = layer
    return Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB")


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("*.webp")):
        c = CLEAN / f.name
        if not c.exists():
            shutil.copy2(f, c)
        src = Image.open(c)
        for side in (None, 1400, 1200, 1000, 860, 760):  # не влезло в 200 КБ — уменьшаем
            img = src
            if side and max(src.size) > side:
                img = src.copy()
                img.thumbnail((side, side), Image.LANCZOS)
            out = mark(img, f.name)
            for q in (84, 80, 76, 72, 68, 64, 60):
                b = io.BytesIO()
                out.save(b, "WEBP", quality=q, method=6)
                if b.tell() <= 198000:
                    break
            if b.tell() <= 198000:
                break
        f.write_bytes(b.getvalue())
        print(f.name, out.size, q, b.tell() // 1024)


if __name__ == "__main__":
    main()
