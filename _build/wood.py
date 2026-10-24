#!/usr/bin/env python3
"""Процедурная текстура тёмного ореха для первого экрана, формы заявки и подвала.

    python3 _build/wood.py   → assets/img/wood.webp и wood.jpg

Своя картинка (не фото из интернета): годовые кольца с изгибом, волокна, поры.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
W, H = 2400, 1000
rng = np.random.default_rng(13)


def noise(gw, gh, w=W, h=H):
    """Гладкий шум: случайная сетка gw×gh, растянутая бикубикой до w×h, значения 0..1."""
    g = (rng.random((gh, gw)) * 255).astype(np.uint8)
    return np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC), dtype=np.float32) / 255


y, x = np.mgrid[0:H, 0:W].astype(np.float32)
# Годовые кольца плоской распиловки: «соборные» дуги со сдвигом центра и неровным шагом
cx = W * 0.58 + 260 * (noise(3, 2) - 0.5)
arch = 0.00016 * (x - cx) ** 2 * (0.6 + 0.8 * noise(4, 2))
warp = 120 * (noise(5, 3) - 0.5) + 35 * (noise(18, 6) - 0.5) + 2.5 * (noise(60, 14) - 0.5)
d = y - arch + warp
t = d / 46.0
t = t + 1.4 * np.sin(t * 0.37) + 2.5 * noise(4, 3)          # кольца то сгущаются, то расходятся
r = t - np.floor(t)
late = np.clip((r - 0.30) / 0.62, 0, 1) ** 1.8                # поздняя древесина: мягкий переход к тёмному
edge = np.clip((r - 0.86) / 0.14, 0, 1) * np.clip((1 - r) / 0.10, 0, 1)  # тонкая граница кольца
# волокна: длинные продольные штрихи
fib = 0.5 * noise(W // 90, H // 1) + 0.3 * noise(W // 40, H // 2) + 0.2 * noise(W // 12, H // 1)
fib = (fib - 0.5) * 2
# цветовые прожилки вдоль доски
streak = noise(4, H // 18)
# поры
pores = (rng.random((H // 1, W // 10)) > 0.988).astype(np.uint8) * 255
pores = np.asarray(Image.fromarray(pores).resize((W, H), Image.NEAREST).filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 255
tone = noise(4, 3)

v = 0.50 + 0.16 * tone + 0.20 * (streak - 0.5) - 0.30 * late - 0.10 * edge + 0.16 * fib - 0.25 * pores
v = np.clip(v, 0, 1)[..., None]
dark = np.array([16, 9, 6], np.float32)      # почти чёрный орех
mid = np.array([50, 30, 18], np.float32)
light = np.array([98, 60, 34], np.float32)    # светлые волокна
img = np.where(v < 0.5, dark + (mid - dark) * (v / 0.5), mid + (light - mid) * ((v - 0.5) / 0.5))
# тёплый подтон в светлых местах
img = img * np.array([1.0, 0.97, 0.92], np.float32)
# лёгкий тёплый блик лака по диагонали
gloss = np.exp(-(((x - W * 0.25) / (W * 0.45)) ** 2 + ((y - H * 0.1) / (H * 0.8)) ** 2))[..., None]
img = img * (0.86 + 0.24 * gloss)
out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
out.save(ROOT / "assets/img/wood.webp", quality=72, method=6)
out.save(ROOT / "assets/img/wood.jpg", quality=78, optimize=True, progressive=True)
print({p: (ROOT / "assets/img" / p).stat().st_size for p in ("wood.webp", "wood.jpg")})
