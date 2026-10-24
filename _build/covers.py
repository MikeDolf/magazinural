#!/usr/bin/env python3
"""Обложки статей: assets/img/stati/<slug>.jpg (для соцсетей) и .webp (на странице).

    python3 _build/covers.py            # только для статей без обложки
    python3 _build/covers.py --all      # перерисовать все

Нужны Node.js с Playwright (Chromium) и Pillow. Обложка — типографская карточка
с заголовком и разделом в стиле сайта, без фото.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))

from data.articles import ARTICLES  # noqa: E402
from data.sections import SECTIONS  # noqa: E402

OUT = ROOT / "assets" / "img" / "stati"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    name = {s["key"]: s["name"] for s in SECTIONS}
    todo = [a for a in ARTICLES if "--all" in sys.argv or not (OUT / f"{a['slug']}.webp").exists()]
    if not todo:
        print("все обложки на месте")
        return
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "covers.json").write_text(json.dumps(
            [{"slug": a["slug"], "h1": a["h1"], "sec": name.get(a["section"], "")} for a in todo], ensure_ascii=False), encoding="utf-8")
        node_path = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
        subprocess.run(["node", str(ROOT / "_build" / "covers.js"), tmp, str(ROOT)], check=True,
                       env={**os.environ, "NODE_PATH": node_path})
    from PIL import Image
    for a in todo:
        jpg = OUT / f"{a['slug']}.jpg"
        Image.open(jpg).save(jpg.with_suffix(".webp"), "WEBP", quality=80, method=6)
    print(f"обложек: {len(todo)}")


if __name__ == "__main__":
    main()
