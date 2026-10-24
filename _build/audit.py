#!/usr/bin/env python3
"""Проверка собранных страниц по docs/on-page-seo.md (автоматическая часть).

    python3 _build/build.py && python3 _build/audit.py [--all] [/url/ ...]

Проверяет страницы из sitemap.xml. Печатает только страницы с замечаниями (с --all — все).
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "_build"))

from data.seo import SEO  # noqa: E402

STOP = {"в", "и", "на", "для", "с", "под", "из", "по", "от", "к", "а", "или", "екатеринбурге", "екатеринбург", "ключ"}


def words(t):
    return re.findall(r"[0-9A-Za-zА-Яа-яЁё-]+", t)


def text_of(fragment):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)))


def check(path):
    f = ROOT / (path.strip("/") + "/index.html") if path != "/" else ROOT / "index.html"
    t = f.read_text(encoding="utf-8")
    title = html.unescape(re.search(r"<title>(.*?)</title>", t).group(1))
    desc = html.unescape(re.search(r'name="description" content="(.*?)"', t).group(1))
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", t, re.S)
    is_post = 'class="page post"' in t
    is_section = path in SEO
    # Собственный текст страницы: вступление, статья, FAQ (без формы, шапки, подвала, стенда).
    own = "".join(re.findall(r'<div class="intro[^"]*">.*?</div>|<header class="intro">.*?</header>', t, re.S))
    own += "".join(re.findall(r'<(?:section|div) class="article[^"]*"[^>]*>(.*?)</(?:section|div)>\s*(?=<|$)', t, re.S))
    own += "".join(re.findall(r'<section class="faq".*?</section>', t, re.S))
    body = text_of(own)
    n = len(words(body))
    issues = []
    if not 50 <= len(title) <= 60:
        issues.append(f"title {len(title)} (50–60)")
    if not 150 <= len(desc) <= 160:
        issues.append(f"description {len(desc)} (150–160)")
    if len(h1) != 1:
        issues.append(f"h1: {len(h1)}")
    for need in ('<html lang="ru">', '<meta charset="utf-8">', 'name="viewport"', 'rel="canonical"', "og:description", "og:url",
                 "og:type", "twitter:image", "og:title", "og:image", "twitter:card", 'rel="icon"', "apple-touch-icon", '"BreadcrumbList"', '"HomeAndConstructionBusiness"'):
        if need not in t and not (path == "/" and need == '"BreadcrumbList"'):
            issues.append(f"нет {need}")
    if h1:
        key = [w.lower() for w in words(text_of(h1[0])) if w.lower() not in STOP][:2]
        first = " ".join(words(body)[:100]).lower()
        miss = [k for k in key if k[:max(4, len(k) - 2)] not in first]
        if miss:
            issues.append(f"запрос не в первых 100 словах: {miss}")
    faq_n = len(re.findall(r'class="faq__item"', t))
    if is_section or is_post:
        if not 4 <= faq_n <= 8:
            issues.append(f"FAQ {faq_n} (4–8)")
        if faq_n and '"FAQPage"' not in t:
            issues.append("нет FAQPage")
    # п. 3: иерархия заголовков без пропусков
    prev = 0
    for lvl in (int(x) for x in re.findall(r"<h([1-6])[\s>]", t)):
        if lvl > prev + 1:
            issues.append(f"пропуск заголовка h{prev}→h{lvl}")
            break
        prev = lvl
    # п. 5: ответ FAQ — 2–4 предложения
    for a in re.findall(r'<div class="faq__item"><h3>.*?</h3><p>(.*?)</p>', t, re.S):
        k = len([x for x in re.split(r"(?<=[.!?…])\s+", text_of(a).strip()) if x])
        if not 2 <= k <= 4:
            issues.append(f"ответ FAQ {k} предл. (2–4)")
    # п. 7: ни одного «здесь», «подробнее»
    for a in re.findall(r"<a [^>]*>(.*?)</a>", t, re.S):
        if text_of(a).strip().lower() in {"здесь", "тут", "подробнее", "читать далее", "по ссылке", "ссылка"}:
            issues.append(f"анкор «{text_of(a).strip()}»")
    if is_section:
        art_n = len(words(text_of("".join(re.findall(r'<section class="article"[^>]*>(.*?)</section>', t, re.S)))))
        if art_n < 600:
            issues.append(f"слов в тексте без FAQ {art_n} (600+)")
        if '"Service"' not in t and path != "/":
            issues.append("нет Service")
        art = "".join(re.findall(r'<section class="article"[^>]*>(.*?)</section>', t, re.S))
        body_links = art + "".join(re.findall(r'<section class="faq".*?</section>', t, re.S))
        internal = set(re.findall(r'<a href="(/[^"#]*)"', body_links))
        external = len(re.findall(r'<a href="https?://[^"]+" target="_blank" rel="noopener"', body_links))
        if len(internal) < 3:
            issues.append(f"внутренних ссылок в тексте {len(internal)} (3–5)")
        if not any(u.startswith("/stati/") for u in internal):
            issues.append("нет ссылки на статью")
        if not 2 <= external <= 3:
            issues.append(f"внешних ссылок {external} (2–3)")
        if "<b>" not in art:
            issues.append("нет выделенных ключевых фраз")
        elif art.count("<b>") > 6:
            issues.append(f"жирного {art.count('<b>')} (умеренно, до 6)")
        if "<ul>" not in art and "<ol>" not in art:
            issues.append("нет списков")
        if '<p class="updated">' not in t:
            issues.append("нет даты обновления")
        main_html = t[t.find('<main'):t.find('</main>')]
        if main_html.count('href="#zayavka"') < 2:
            issues.append("меньше 2 призывов к заявке внутри страницы (кроме шапки)")
    if is_post:
        m_body = re.search(r'<div class="article article--post">(.*?)</div>\s*<aside class="hand"', t, re.S)
        body_n = len(words(text_of(m_body.group(1) if m_body else "")))
        if body_n < 1500:
            issues.append(f"слов в статье без лида и FAQ {body_n} (1500+)")
        if '"Article"' not in t:
            issues.append("нет Article")
        # тело статьи — первый блок article--post, до врезки «Не хотите строить сами?» (FAQ идёт после неё)
        m_art = re.search(r'<div class="article article--post">(.*?)</div>\s*<aside class="hand"', t, re.S)
        art = m_art.group(1) if m_art else ""
        internal = len(re.findall(r'<a href="/', art))
        external = len(re.findall(r'<a href="https?://[^"]+" target="_blank" rel="noopener"', art))
        if internal < 3:
            issues.append(f"внутренних ссылок {internal} (3–5)")
        if external < 2:
            issues.append(f"внешних ссылок {external} (2–3)")
        if 'class="toc"' not in t:
            issues.append("нет оглавления")
        img = re.search(r'<img class="post__cover"[^>]*>', t)
        if not img or 'alt="' not in img.group(0) or 'width=' not in img.group(0):
            issues.append("нет обложки с alt и размерами")
        if 'og:image" content="https://magazinural.ru/assets/img/og.png' in t:
            issues.append("og:image общий, нет своей картинки")
        if not re.search(r'<a href="/(?!stati/)[^"#]+/"', art):
            issues.append("нет ссылки в каталог")
        if "<b>" not in art:
            issues.append("нет выделенных ключевых фраз")
        if "<ul>" not in art and "<ol>" not in art:
            issues.append("нет списков")
    if "/obekt-" in path:  # страница объекта
        art = "".join(re.findall(r'<section class="article obj__text"[^>]*>(.*?)</section>', t, re.S))
        if len(words(text_of(art))) < 250:
            issues.append(f"слов в тексте объекта {len(words(text_of(art)))} (250+)")
        if len(set(re.findall(r'<a href="(/[^"#]*)"', art))) < 2:
            issues.append("мало внутренних ссылок в тексте объекта")
        if '"Product"' not in t:
            issues.append("нет Product")
        for img in re.findall(r"<img [^>]*>", t[t.find("<main"):]):
            if 'alt="' not in img or "width=" not in img:
                issues.append("картинка без alt/размеров"); break
    paras = re.findall(r"<p>(.*?)</p>", own, re.S)
    long_p = sum(1 for p in paras if len(re.findall(r"[.!?…](?:\s|$)", text_of(p))) > 4)
    if long_p:
        issues.append(f"длинных абзацев {long_p} (>4 предложений)")
    return title, desc, n, issues


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    sm = re.findall(r"<loc>https?://[^/]+(/[^<]*)</loc>", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))
    paths = args or sm
    bad = 0
    for p in paths:
        title, desc, n, issues = check(p)
        if issues:
            bad += 1
        if issues or show_all:
            print(f"{p}  [{n} слов]  " + ("; ".join(issues) if issues else "ок"))
    print(f"\nпроверено: {len(paths)}, с замечаниями: {bad}")


if __name__ == "__main__":
    main()
