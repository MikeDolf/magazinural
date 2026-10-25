"""QR-код чата в MAX для всплывающего окна на компьютере: assets/img/max-qr.svg.

Запускать после смены ссылки SITE["max"]: python3 _build/qr.py (нужен segno: pip install segno).
"""
import sys
from pathlib import Path

import segno

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))
from data.site import SITE  # noqa: E402

out = ROOT / "assets" / "img" / "max-qr.svg"
segno.make(SITE["max"], error="m").save(out, scale=4, border=2, dark="#2f1d11", light="#ffffff", xmldecl=False, svgns=True)
svg = out.read_text()
size = svg.split('width="', 1)[1].split('"', 1)[0]
out.write_text(svg.replace(f'width="{size}"', f'viewBox="0 0 {size} {size}" width="{size}"', 1))
print("ok")
