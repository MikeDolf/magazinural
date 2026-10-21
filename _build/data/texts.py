"""Тексты разделов. Ключ — адрес страницы. Раздел без текста и без объявлений
собирается с noindex и не попадает в sitemap.

Разметка: абзацы через пустую строку, `## `/`### ` — подзаголовки, `- ` — пункт списка,
`1. ` — нумерованный список, `**жирный**`, `[анкор](/url/)`. FAQ — список пар (вопрос, ответ).
Требования к текстам — docs/on-page-seo.md.
Цены, сроки и обещания не выдумываем: только реальные данные компании.
"""

LEADS = {}
TEXTS = {}

# Модули data/texts_*.py подключаются автоматически, по алфавиту: более поздний перекрывает ранний.
import importlib  # noqa: E402
import pkgutil  # noqa: E402
from pathlib import Path  # noqa: E402

FAQ = {}
SEO_OVERRIDES = {}
UPDATED = {}  # url → ГГГГ-ММ-ДД, дата последней правки текста (модуль: UPDATED или DEFAULT_UPDATED)

for _i in sorted(pkgutil.iter_modules([str(Path(__file__).parent)]), key=lambda m: m.name):
    if _i.name.startswith("texts_"):
        _m = importlib.import_module(f"data.{_i.name}")
        LEADS.update(getattr(_m, "LEADS", {}))
        TEXTS.update(getattr(_m, "TEXTS", {}))
        FAQ.update(getattr(_m, "FAQ", {}))
        SEO_OVERRIDES.update(getattr(_m, "SEO", {}))
        _d = getattr(_m, "DEFAULT_UPDATED", None)
        UPDATED.update({u: _d for u in getattr(_m, "TEXTS", {}) if _d})
        UPDATED.update(getattr(_m, "UPDATED", {}))
