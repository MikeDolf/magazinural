"""Статьи. Каждая лежит в модуле data/articles_*.py в списке ARTICLES.

Поля статьи:
    slug       — адрес /stati/<slug>/ (латиница, дефисы, до 60 знаков)
    section    — ключ раздела каталога, куда ведёт статья (data/sections.py)
    h1, title, desc, lead
    published, updated — даты ГГГГ-ММ-ДД
    body       — мини-разметка (см. data/texts.py), от 1500 слов, 3–5 ссылок в каталог, 2–3 внешних источника
    faq        — 4–8 пар (вопрос, ответ)
Требования — docs/on-page-seo.md.
"""

import importlib
import pkgutil
from pathlib import Path

ARTICLES = []
for _m in sorted(pkgutil.iter_modules([str(Path(__file__).parent)]), key=lambda m: m.name):
    if _m.name.startswith("articles_"):
        ARTICLES.extend(importlib.import_module(f"data.{_m.name}").ARTICLES)
for _a in ARTICLES:
    _a["url"] = f"/stati/{_a['slug']}/"
