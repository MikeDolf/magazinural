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
    own = "".join(re.findall(r'<div class="intro">.*?</div>|<header class="intro">.*?</header>', t, re.S))
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
    for need in ("og:title", "og:image", "twitter:card", 'rel="icon"', "apple-touch-icon", '"BreadcrumbList"', '"Organization"'):
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
    if is_section:
        if n < 600:
            issues.append(f"слов {n} (600+)")
        if '"Service"' not in t:
            issues.append("нет Service")
    if is_post:
        if n < 1500:
            issues.append(f"слов {n} (1500+)")
        if '"Article"' not in t:
            issues.append("нет Article")
        art = "".join(re.findall(r'<div class="article article--post">(.*?)</div>', t, re.S))
        internal = len(re.findall(r'<a href="/', art))
        external = len(re.findall(r'<a href="https?://[^"]+" target="_blank" rel="noopener"', art))
        if internal < 3:
            issues.append(f"внутренних ссылок {internal} (3–5)")
        if external < 2:
            issues.append(f"внешних ссылок {external} (2–3)")
        if 'class="toc"' not in t:
            issues.append("нет оглавления")
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
