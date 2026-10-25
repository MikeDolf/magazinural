#!/usr/bin/env python3
"""Сборка статических страниц magazinural.ru.

    python3 _build/build.py

Шапка, подвал, форма заявки и SEO-обвязка одинаковы на всех страницах, поэтому
лежат здесь, а страницы — производные от данных в _build/data/.

Что скрипт делает намеренно:
  * страница без объявлений и без собственного текста собирается с noindex
    и не попадает в sitemap: пустой каталог не отдаём поиску;
  * не выдумывает объекты: пока владелец не передал фото и паспорта, вместо сетки —
    пустое состояние с образцом паспорта (поля без значений);
  * не размечает цены через schema.org/Offer, пока цены не реальные.
"""

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data.site import SITE, HEADER_SECTIONS, WHEN_OPTIONS, AREA, PAYMENT, DELIVERY, COMPANY, ADVANTAGES, STEPS
from data.sections import SECTIONS
from data.listings import LISTINGS
for _x in LISTINGS:  # путь к фото — от корня сайта, без ведущего «/»
    _x["photos"] = [p.lstrip("/") for p in _x.get("photos") or []]
from data.texts import TEXTS, LEADS, FAQ, UPDATED, GEO
from data.articles import ARTICLES
from data.seo import SEO
from data import norms as N
from data.sizes import SIZES, PRICES as SIZE_PRICES
from data import objects_text as OT
from data.calc import CALC, CALC_RANGE, CALC_PLACES, CALC_NOTE

ROOT = Path(__file__).resolve().parent.parent
VER = "41"  # меняйте при правке css/js

BY_KEY = {s["key"]: s for s in SECTIONS}


def e(t):
    return html.escape(str(t), quote=True)


NO_TURNKEY = {"services", "maf", "garden", "nastil", "fence"}


def cap(t):
    return t[:1].upper() + t[1:]


def rub(n):
    return f"{n:,}".replace(",", " ") + " ₽"


def inline(t):
    """Строка текста: экранирование, **жирный**, [анкор](/url/). Внешние ссылки — в новой вкладке."""
    t = e(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)

    def link(m):
        text, url = m.group(1), m.group(2)
        ext = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
        return f'<a href="{url}"{ext}>{text}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)


def md(text, toc=None):
    """Мини-разметка: ## и ### заголовки, - и 1. списки, абзацы. В toc складываются (id, H2) для оглавления."""
    out, items, kind = [], [], None

    def flush():
        if items:
            tag = "ol" if kind == "ol" else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>")
            items.clear()

    for block in text.strip().split("\n\n"):
        block = block.strip()
        lines = block.split("\n")
        if all(l.startswith("- ") for l in lines):
            if kind != "ul":
                flush()
            kind = "ul"
            items.extend(inline(l[2:]) for l in lines)
            continue
        if all(re.match(r"\d+\. ", l) for l in lines):
            if kind != "ol":
                flush()
            kind = "ol"
            items.extend(inline(re.sub(r"^\d+\. ", "", l)) for l in lines)
            continue
        flush()
        kind = None
        if block.startswith("#") and len(lines) > 1:  # заголовок без пустой строки после него
            block, rest = lines[0], "\n".join(lines[1:])
            out.append(md(block, toc) if toc is not None else md(block))
            out.append(md(rest))
            continue
        if block.startswith("### "):
            out.append(f"<h3>{inline(block[4:])}</h3>")
        elif block.startswith("## "):
            if toc is not None:
                hid = f"r{len(toc) + 1}"
                toc.append((hid, block[3:]))
                out.append(f'<h2 id="{hid}">{inline(block[3:])}</h2>')
            else:
                out.append(f"<h2>{inline(block[3:])}</h2>")
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    flush()
    return "\n".join(out)


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


ORG_ID = f"{SITE['base_url']}/#org"


def org_ld():
    org = {"@context": "https://schema.org", "@type": "HomeAndConstructionBusiness", "@id": ORG_ID, "name": SITE["name"],
           "url": SITE["base_url"] + "/", "logo": SITE["base_url"] + "/assets/img/logo-512.png",
           "areaServed": SITE["region"]}
    if SITE.get("phone"):
        org["telephone"] = SITE["phone"]
    if SITE.get("hours", "").startswith("Круглосуточно"):
        org["openingHoursSpecification"] = {"@type": "OpeningHoursSpecification", "opens": "00:00", "closes": "23:59",
                                            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
    if SITE.get("email"):
        org["email"] = SITE["email"]
    ip = SITE.get("ip")
    if ip:
        org["legalName"] = f"ИП {ip['name']}"
        if ip.get("inn"):
            org["taxID"] = ip["inn"]
        if ip.get("address"):
            org["address"] = {"@type": "PostalAddress", "streetAddress": ip["address"].replace("г. Екатеринбург, ", ""),
                              "addressLocality": "Екатеринбург", "addressCountry": "RU"}
    if COMPANY.get("since"):
        org["foundingDate"] = str(COMPANY["since"])
    if SITE.get("max"):
        org["sameAs"] = [SITE["max"]]
    if SITE.get("author"):
        org["employee"] = {"@id": SITE["base_url"] + SITE["author"]["url"] + "#person"}
    return org


def person_ld():
    """Автор статей: Person с должностью и местом работы (страница автора и разметка статей ссылаются на один @id)."""
    a = SITE["author"]
    p = {"@context": "https://schema.org", "@type": "Person", "@id": SITE["base_url"] + a["url"] + "#person", "name": a["name"],
         "jobTitle": a["job"], "worksFor": {"@id": ORG_ID}, "url": SITE["base_url"] + a["url"],
         "knowsAbout": ["Деревянное домостроение", "Каркасные конструкции", "Расчёт снеговой и ветровой нагрузки", "Бани и беседки из дерева"]}
    if a.get("photo"):
        p["image"] = SITE["base_url"] + "/" + a["photo"]
    return p


def author_pic(cls="author__pic"):
    """Фото автора или, пока фото нет, инициалы в круге."""
    a = SITE["author"]
    if a.get("photo"):
        w, h = img_size(a["photo"])
        return f'<img class="{cls}" src="/{e(a["photo"])}" alt="{e(a["name"])}, {e(a["job"].lower())}" width="{w}" height="{h}" loading="lazy">'
    ini = a["name"].split()[0][0] + a["name"].split()[-1][0]  # «Павел … Никулов» → «ПН»
    return f'<span class="{cls} {cls}--ini" aria-hidden="true">{e(ini)}</span>'


def reviewed():
    a = SITE.get("author")
    return f' · проверил {e(a["job"].lower())} <a href="{a["url"]}">{e(a["short"])}</a>' if a else ""


def author_card(h="Об авторе", tag="h2"):
    """Карточка автора в конце статьи и на странице «О компании»."""
    a = SITE.get("author")
    if not a:
        return ""
    return (f'<aside class="author" aria-label="{e(h)}">{author_pic()}<div class="author__text"><p class="author__h">{e(h)}</p>'
            f'<{tag} class="author__name"><a href="{a["url"]}">{e(a["name"])}</a></{tag}><p class="author__job">{e(a["job"])} «{e(SITE["name"])}»</p>'
            f'<p>{e(AUTHOR_ABOUT)}</p></div></aside>')


AUTHOR_ABOUT = ("Отвечает за конструкцию наших построек: рассчитывает каркас, кровлю и фундамент под снеговую и ветровую нагрузку Урала, "
                "готовит рабочие чертежи и проверяет проекты перед производством. Проверяет статьи сайта, чтобы советы совпадали с тем, как мы строим.")


def crumbs_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE["base_url"] + u} for i, (n, u) in enumerate(items)]}


def faq_ld(items):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a).replace("**", "")}}
        for q, a in items]}


def faq_block(items):
    if not items:
        return ""
    qa = "".join(f'<div class="faq__item"><h3>{e(q)}</h3><p>{inline(a)}</p></div>' for q, a in items)
    return f'<section class="faq" aria-labelledby="faq-h"><h2 id="faq-h">Частые вопросы</h2>{qa}</section>'


def metrika_head():
    mid = SITE.get("metrika")
    if not mid:
        return ""
    return f"""<script>(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();
for(var j=0;j<document.scripts.length;j++){{if(document.scripts[j].src===r){{return;}}}}
k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}})(window,document,'script','https://mc.yandex.ru/metrika/tag.js?id={mid}','ym');
ym({mid},'init',{{ssr:true,webvisor:true,clickmap:true,ecommerce:"dataLayer",referrer:document.referrer,url:location.href,accurateTrackBounce:true,trackLinks:true}});</script>
"""


def metrika_noscript():
    mid = SITE.get("metrika")
    return (f'<noscript><div><img src="https://mc.yandex.ru/watch/{mid}" style="position:absolute;left:-9999px" alt=""></div></noscript>' if mid else "")


def img_size(path):
    """Ширина и высота WebP/JPEG/PNG без сторонних библиотек (для width/height у <img>)."""
    b = (ROOT / path).read_bytes()[:65536]
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        kind = b[12:16]
        if kind == b"VP8 ":
            return int.from_bytes(b[26:28], "little") & 0x3FFF, int.from_bytes(b[28:30], "little") & 0x3FFF
        if kind == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
        if kind == b"VP8X":
            return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    i = 2
    while i < len(b) - 9:  # JPEG: ищем SOF0/SOF2
        if b[i] == 0xFF and b[i + 1] in (0xC0, 0xC2):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        i += 2 + int.from_bytes(b[i + 2:i + 4], "big") if b[i] == 0xFF else 1
    return 1200, 800


def fit_len(base, tails, lo, hi):
    """Добирает к тексту хвосты, пока он не войдёт в диапазон lo–hi знаков."""
    for t in tails:
        if len(base) >= lo:
            break
        if len(base + t) <= hi:
            base += t
    return base


def fit_title(t):
    """Title 50–60 знаков: бренд дописываем, только если влезает (docs/on-page-seo.md)."""
    full = f"{t} | {SITE['name']}"
    return full if len(full) <= 60 else t


# ---------- иконки (одна толщина линии, 24×24) ----------

def icon(name):
    paths = {
        "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
        "phone": '<path d="M6.5 3.5h3l1.5 4-2 1.3a10 10 0 0 0 5.2 5.2l1.3-2 4 1.5v3a2 2 0 0 1-2 2A15.5 15.5 0 0 1 4.5 5.5a2 2 0 0 1 2-2z"/>',
        "photo": '<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="16" cy="9" r="1.6"/>',
    }
    return (f'<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>')


# Знак: дом с двускатной крышей (тот же, что в favicon).
LOGO = ('<svg class="logo__mark" viewBox="0 0 64 64" aria-hidden="true">'
        '<path d="M8 31 32 11l24 20" fill="none" stroke="currentColor" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M15 29v23h34V29L32 15z" fill="currentColor"/>'
        '<rect x="27" y="36" width="10" height="16" rx="1.5" fill="var(--frame)"/>'
        '<rect x="40" y="34" width="5" height="5" rx="1" fill="var(--signal)"/></svg>')


# Знак MAX: пузырь чата на градиенте (градиент — в спрайте MAX_DEFS, один на страницу).
MAX_DEFS = ('<svg class="sprite" aria-hidden="true" focusable="false"><defs><linearGradient id="mxg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#41c7ff"/><stop offset=".5" stop-color="#4b5cff"/><stop offset="1" stop-color="#9a3cf5"/></linearGradient></defs></svg>')
MAX_ICON = ('<svg class="mx" viewBox="0 0 48 48" aria-hidden="true" focusable="false"><rect width="48" height="48" rx="13" fill="url(#mxg)"/>'
            '<path d="M24.5 11.5a12 12 0 1 1-6.8 21.9L12 36l1.9-6.1A12 12 0 0 1 24.5 11.5z" fill="#fff"/>'
            '<circle cx="24.5" cy="23.5" r="6.3" fill="url(#mxg)"/></svg>')


# ---------- каркас страницы ----------

def head(title, desc, path, index, schema=(), og_type="website", og_img=None):
    robots = "" if index else '<meta name="robots" content="noindex, follow">\n'
    url = f"{SITE['base_url']}{path}"
    img = SITE["base_url"] + (og_img or "/assets/img/og.png")
    blocks = "".join(ld(x) for x in (org_ld(), *schema))
    return f"""<!doctype html>
<html lang="ru"{f' data-ym="{SITE["metrika"]}"' if SITE.get("metrika") else ""}>
<head>
<meta charset="utf-8"><script>document.documentElement.classList.add("js")</script>
<meta name="viewport" content="width=device-width, initial-scale=1">{f'<meta name="form-endpoint" content="https://api.web3forms.com/submit"><meta name="form-key" content="{e(SITE["form_key"])}">' if SITE.get("form_key") else (f'<meta name="form-endpoint" content="{e(SITE["form_endpoint"])}">' if SITE.get("form_endpoint") else "")}
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{robots}<link rel="canonical" href="{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{e(SITE['name'])}">
<meta property="og:locale" content="ru_RU">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{img if og_img else SITE['base_url'] + '/assets/img/og-twitter.png'}">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-120.png" sizes="120x120" type="image/png">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/golos-cyrillic.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/site.css?v={VER}">
<meta name="theme-color" content="#2f1d11">
{blocks}
{metrika_head()}</head>
<body>{metrika_noscript()}{MAX_DEFS if SITE.get("max") else ""}
<a class="skip" href="#main">К содержанию</a>
"""


def header(cta="#zayavka"):
    """cta — куда ведёт кнопка заявки: на форму этой страницы или, если формы нет, на форму главной."""
    links = "".join(f'<li><a href="{BY_KEY[k]["url"]}">{e(BY_KEY[k]["name"])}</a></li>' for k in HEADER_SECTIONS if k in BY_KEY)
    return f"""<header class="top">
  <div class="top__in">
    <a class="logo" href="/">{LOGO}<span class="logo__text"><b>{e(SITE['name'])}</b><small>{e(SITE['tagline'])}</small></span></a>
    <button class="menu-btn" type="button" data-menu aria-haspopup="dialog" aria-controls="menu" aria-label="Открыть меню"><span class="menu-btn__bars" aria-hidden="true"><i></i><i></i><i></i></span><span class="menu-btn__t">Меню</span></button>
    <details class="nav">
      <summary class="nav__toggle" aria-label="Разделы">{icon('menu')}<span class="nav__label">Разделы</span></summary>
      <nav aria-label="Разделы каталога"><ul>{links}<li><a href="/#razdely">Все постройки</a></li><li class="nav__extra"><a href="{CALC_PATH}">Калькулятор</a></li><li class="nav__extra"><a href="/o-kompanii/">О компании</a></li></ul></nav>
    </details>
    {f'<button class="top__max" type="button" data-max aria-haspopup="dialog" aria-label="Написать в MAX">{MAX_ICON}<span>Написать в MAX</span></button>' if SITE.get("max") else ""}
    <button class="top__call" type="button" data-callback aria-haspopup="dialog" aria-label="Перезвоните мне">{icon('phone')}<span>Перезвоните мне</span></button>
    <a class="btn btn--enamel top__cta" href="{cta}"><span class="top__cta-long">Оставить заявку</span><span class="top__cta-short">Заявка</span></a>
  </div>
</header>
"""


def footer():
    cols = []
    core = [s for s in SECTIONS if s["core"]]
    ext = [s for s in SECTIONS if not s["core"]]
    half = (len(core) + 1) // 2
    for chunk in (core[:half], core[half:]):
        cols.append("<ul>" + "".join(f'<li><a href="{s["url"]}">{e(s["name"])}</a></li>' for s in chunk) + "</ul>")
    cols.append("<ul>" + "".join(f'<li><a href="{s["url"]}">{e(s["name"])}</a></li>' for s in ext)
                + (f'<li><a href="{CONTACTS_PATH}">Контакты</a></li>' if has_contacts() else "")
                + f'<li><a href="{CALC_PATH}">Калькулятор стоимости</a></li><li><a href="{DELIVERY_PATH}">Доставка и оплата</a></li><li><a href="{WARRANTY_PATH}">Гарантия</a></li><li><a href="{FAQ_PATH}">Вопросы и ответы</a></li><li><a href="/nashi-raboty/">Наши работы</a></li><li><a href="/proekty/">Проекты</a></li><li><a href="/stati/">Статьи</a></li><li><a href="/gde-postavit-postroyku/">Где поставить постройку</a></li><li><a href="/o-kompanii/">О компании</a></li><li><a href="/politika-konfidencialnosti/">Политика конфиденциальности</a></li><li><a href="{MAP_PATH}">Карта сайта</a></li></ul>')
    return f"""<footer class="foot">
  <div class="foot__in">
    <div class="foot__brand"><a class="logo logo--foot" href="/">{LOGO}<span class="logo__text"><b>{e(SITE['name'])}</b><small>{e(SITE['region'])}</small></span></a>
      <p>Строим бани, беседки, навесы, террасы и другие деревянные постройки для участка в Екатеринбурге и области.</p></div>
    <div class="foot__cols">{''.join(cols)}</div>
    {contacts_block()}
  </div>
</footer>
{callback_dialog()}
{drawer()}
{max_dialog()}
{quiz_dialog()}
<script src="/assets/js/calc-data.js?v={VER}" defer></script>
<script src="/assets/js/site.js?v={VER}" defer></script>
</body>
</html>
"""


CONTACTS_PATH = "/kontakty/"


def has_contacts():
    return bool(SITE.get("phone") or SITE.get("ip") or SITE.get("telegram") or SITE.get("whatsapp") or SITE.get("max"))


def contacts_block():
    """Контакты и реквизиты ИП в подвале — только реальные данные из site.py."""
    if not has_contacts():
        return ""
    rows = []
    if SITE.get("phone"):
        rows.append(f'<a class="foot__phone" href="tel:{re.sub(r"[^+0-9]", "", SITE["phone"])}">{e(SITE["phone"])}</a>')
    msg = []
    if SITE.get("telegram"):
        tg = SITE["telegram"]
        msg.append(f'<a href="{e(tg if tg.startswith("http") else "https://t.me/" + tg.lstrip("@"))}" target="_blank" rel="noopener">Telegram</a>')
    if SITE.get("whatsapp"):
        msg.append(f'<a href="https://wa.me/{re.sub(r"[^0-9]", "", SITE["whatsapp"])}" target="_blank" rel="noopener">WhatsApp</a>')
    if SITE.get("max"):
        msg.append(f'<a href="{e(SITE["max"])}" target="_blank" rel="noopener">MAX</a>')
    if msg:
        rows.append(" · ".join(msg))
    if SITE.get("hours"):
        rows.append(f"<span>{e(SITE['hours'])}</span>")
    if SITE.get("email"):
        rows.append(f'<a href="mailto:{e(SITE["email"])}">{e(SITE["email"])}</a>')
    ip = SITE.get("ip") or {}
    req = []
    if ip.get("name"):
        req.append(f"ИП {e(ip['name'])}")
    if ip.get("inn"):
        req.append(f"ИНН {e(ip['inn'])}")
    if ip.get("ogrnip"):
        req.append(f"ОГРНИП {e(ip['ogrnip'])}")
    if ip.get("address"):
        req.append(e(ip["address"]))
    return (f'<div class="foot__contacts"><h2 class="foot__h">Контакты</h2><p>{" · ".join(rows)}</p>'
            + (f'<p class="foot__req">{" · ".join(req)}</p>' if req else "") + "</div>")


def callback_dialog():
    """«Перезвоните мне»: имя и телефон. Отправка — та же, что у формы заявки (SITE["form_endpoint"])."""
    return f"""<dialog class="callback" id="callback" aria-labelledby="callback-h">
  <form class="form callback__form" method="dialog" novalidate data-form data-callback-form>
    <div class="callback__head"><h2 id="callback-h">Перезвоним вам</h2>
      <button class="callback__close" type="button" data-callback-close aria-label="Закрыть">×</button></div>
    <p>Оставьте телефон — перезвоним, ответим на вопросы и договоримся о замере.</p>
    <label class="field"><span>Имя</span><input name="name" autocomplete="name"></label>
    <label class="field"><span>Телефон <i aria-hidden="true">*</i></span><input name="phone" type="tel" autocomplete="tel" required placeholder="+7" inputmode="tel" aria-describedby="cb-phone-err"><em class="field__err" id="cb-phone-err" hidden>Укажите телефон, чтобы мы могли перезвонить</em></label>
    <input type="hidden" name="type" value="Обратный звонок">
    <label class="hp" aria-hidden="true">Не заполняйте <input name="website" tabindex="-1" autocomplete="off"></label>
    <label class="agree"><input type="checkbox" name="agree" required> <span>Согласен на обработку персональных данных по <a href="/politika-konfidencialnosti/">политике</a></span></label>
    <div class="form__actions"><button class="btn btn--frame" type="submit">Перезвоните мне</button>
      <p class="form__status" role="status" aria-live="polite" hidden></p></div>
  </form>
</dialog>"""


def drawer():
    """Меню на телефоне и планшете: панель справа — разделы с фото, все постройки, полезное, компания, кнопки действий."""
    main = [k for k in ["besedka", "banya", "naves", "terrasa", "hozblok", "karkas"] if k in BY_KEY]
    tiles = "".join(
        f'<li style="--i:{n}"><a class="dtile" href="{BY_KEY[k]["url"]}"><img src="/assets/img/calc/{k}.webp" alt="" width="360" height="240" loading="lazy" decoding="async">'
        f'<span>{e(BY_KEY[k]["name"])}</span></a></li>' for n, k in enumerate(main))
    rest = "".join(f'<li><a href="{s["url"]}">{e(s["name"])}</a></li>' for s in SECTIONS if s["key"] not in main)
    def links(items):
        return '<ul class="drawer__links">' + "".join(f'<li><a href="{u}">{e(t)}{icon("arrow")}</a></li>' for u, t in items) + "</ul>"
    useful = [(CALC_PATH, "Калькулятор стоимости"), ("/nashi-raboty/", "Наши работы"), ("/proekty/", "Проекты"), ("/stati/", "Статьи"),
              ("/gde-postavit-postroyku/", "Где поставить постройку")]
    company = [("/o-kompanii/", "О компании"), ("/dostavka-i-oplata/", "Доставка и оплата"), ("/garantiya/", "Гарантия"),
               ("/voprosy-i-otvety/", "Вопросы и ответы")] + ([(CONTACTS_PATH, "Контакты")] if has_contacts() else [])
    return f"""<dialog class="drawer" id="menu" aria-label="Меню сайта">
  <div class="drawer__head"><a class="logo" href="/">{LOGO}<span class="logo__text"><b>{e(SITE['name'])}</b><small>{e(SITE['tagline'])}</small></span></a>
    <button class="drawer__close" type="button" data-dialog-close aria-label="Закрыть меню"><span aria-hidden="true"></span></button></div>
  <div class="drawer__body">
    <p class="drawer__h" style="--i:0">Что строим</p>
    <ul class="drawer__tiles">{tiles}</ul>
    <details class="drawer__all" style="--i:6"><summary>Все постройки <span>{len(SECTIONS)}</span></summary><ul>{rest}</ul></details>
    <p class="drawer__h" style="--i:7">Полезное</p>
    <div style="--i:8">{links(useful)}</div>
    <p class="drawer__h" style="--i:9">Компания</p>
    <div style="--i:10">{links(company)}</div>
    <p class="drawer__meta" style="--i:11">{e(SITE.get("hours") or "")} · Екатеринбург и пригороды</p>
  </div>
  <div class="drawer__foot">
    {quiz_button(label="Рассчитать стоимость", cls="btn btn--enamel drawer__cta")}
    {f'<button class="drawer__ic" type="button" data-max aria-label="Написать в MAX">{MAX_ICON}</button>' if SITE.get("max") else ""}
    <button class="drawer__ic drawer__ic--call" type="button" data-callback aria-label="Перезвоните мне">{icon('phone')}</button>
  </div>
</dialog>"""


def max_dialog():
    """«Написать в MAX»: окно из шапки и плавающей кнопки. На компьютере — QR-код, на телефоне — кнопка в приложение."""
    if not SITE.get("max"):
        return ""
    return f"""<dialog class="callback mxd" id="max" aria-labelledby="max-h">
  <div class="callback__form">
    <div class="callback__head"><h2 id="max-h">{MAX_ICON}Напишите нам в MAX</h2>
      <button class="callback__close" type="button" data-dialog-close aria-label="Закрыть">×</button></div>
    <p>Отвечаем круглосуточно. Пришлите фото участка, эскиз или понравившуюся постройку — подскажем решение и примерную цену.</p>
    <div class="mxd__qr"><img src="/assets/img/max-qr.svg" width="148" height="148" alt="QR-код чата «{e(SITE['name'])}» в MAX" loading="lazy">
      <p>Наведите камеру телефона на код — чат откроется в приложении MAX.</p></div>
    <a class="btn btn--max" href="{e(SITE['max'])}" target="_blank" rel="noopener">{MAX_ICON}Открыть чат в MAX</a>
    <p class="mxd__alt">Удобнее по-другому? <button type="button" data-callback>Перезвоните мне</button><button type="button" data-quiz>Рассчитать стоимость</button></p>
  </div>
</dialog>
<button class="fab" type="button" data-max aria-haspopup="dialog" aria-label="Написать в MAX">{MAX_ICON}</button>"""


# ---------- калькулятор и квиз ----------

CALC_PATH = "/kalkulyator/"
CALC_KEYS = {t["key"] for t in CALC}


def calc_area(t, size):
    if t.get("unit") == "area":
        return float(size)
    w, l = size.replace(",", ".").split("×")
    return float(w) * float(l)


def calc_base(t, area):
    """Цена базовой комплектации по опорным точкам — та же формула, что в site.js (calcPrice)."""
    pts = t["points"]
    if area <= pts[0][0]:
        v = area * pts[0][1] / pts[0][0]
    elif area >= pts[-1][0]:
        (a1, p1), (a2, p2) = pts[-2], pts[-1]
        v = p2 + (area - a2) * (p2 - p1) / (a2 - a1)
    else:
        for (a1, p1), (a2, p2) in zip(pts, pts[1:]):
            if a1 <= area <= a2:
                v = p1 + (area - a1) * (p2 - p1) / (a2 - a1)
                break
    return max(t["min"], v)


def calc_round(v):
    return int(round(v / 5000) * 5000)


def size_label(t, size):
    return f"{size} м²" if t.get("unit") == "area" else f"{size} м"


def calc_data_js():
    """assets/js/calc-data.js: типы, размеры и опции для квиза и калькулятора (site.js)."""
    types = []
    for t in CALC:
        sec = BY_KEY[t["key"]]
        types.append({"key": t["key"], "name": t["name"], "section": sec["name"], "url": sec["url"], "unit": t.get("unit", "dim"),
                      "sizes": t["sizes"], "custom": t.get("custom", False), "points": t["points"], "min": t["min"],
                      "img": f'/assets/img/calc/{t["key"]}.webp',
                      "from": calc_round(calc_base(t, calc_area(t, t["sizes"][0])) * CALC_RANGE[0]),
                      "options": [{"name": g, "items": [{"name": n, **v} for n, v in items]} for g, items in t["options"]]})
    data = {"types": types, "range": CALC_RANGE, "places": CALC_PLACES, "when": WHEN_OPTIONS, "note": CALC_NOTE}
    (ROOT / "assets" / "js" / "calc-data.js").write_text(
        "// Собирается из _build/data/calc.py (python3 _build/build.py) — не править руками.\nwindow.CALC = "
        + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def quiz_dialog():
    """Квиз «Рассчитать стоимость»: шаги рисует site.js из calc-data.js, форма в конце — общая отправка заявок."""
    return f"""<dialog class="callback quiz" id="quiz" aria-labelledby="quiz-h">
  <div class="quiz__in">
    <div class="callback__head"><h2 id="quiz-h">Рассчитать стоимость</h2>
      <button class="callback__close" type="button" data-dialog-close aria-label="Закрыть">×</button></div>
    <div class="quiz__bar" aria-hidden="true"><span></span></div>
    <div data-calc="quiz"></div>
    <form class="form quiz__form" novalidate data-form hidden>
      <p class="quiz__lead">Оставьте телефон — пришлём точный расчёт и перезвоним, если появятся вопросы.</p>
      <input type="hidden" name="type"><input type="hidden" name="size"><input type="hidden" name="place"><input type="hidden" name="when">
      <input type="hidden" name="note"><input type="hidden" name="estimate">
      <label class="field"><span>Имя</span><input name="name" autocomplete="name"></label>
      <label class="field"><span>Телефон <i aria-hidden="true">*</i></span><input name="phone" type="tel" autocomplete="tel" required placeholder="+7" inputmode="tel" aria-describedby="qz-phone-err"><em class="field__err" id="qz-phone-err" hidden>Укажите телефон, чтобы мы могли прислать расчёт</em></label>
      <label class="hp" aria-hidden="true">Не заполняйте <input name="website" tabindex="-1" autocomplete="off"></label>
      <label class="agree"><input type="checkbox" name="agree" required> <span>Согласен на обработку персональных данных по <a href="/politika-konfidencialnosti/">политике</a></span></label>
      <div class="form__actions"><button class="btn btn--ghost" type="button" data-calc-back>Назад</button><button class="btn btn--frame" type="submit">Получить точный расчёт</button>
        <p class="form__status" role="status" aria-live="polite" hidden></p></div>
    </form>
  </div>
</dialog>"""


def quiz_button(key=None, label="Рассчитать стоимость", cls="btn btn--ghost"):
    """Кнопка квиза; key — сразу выбрать постройку (если она есть в калькуляторе)."""
    k = f' data-quiz="{key}"' if key in CALC_KEYS else " data-quiz"
    return f'<button class="{cls}" type="button"{k} aria-haspopup="dialog">{label}</button>'


def howto_block():
    """«Как оплатить» и «Как получить» — тексты из data/site.py."""
    def card(h, items):
        return f'<div class="howto__card"><h2>{e(h)}</h2><ul>' + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul></div>"
    return f'<section class="howto" aria-label="Оплата и порядок работ">{card("Как оплатить", PAYMENT)}{card("Как получить постройку", DELIVERY)}</section>'


def is_project(item):
    return item.get("kind") == "project"


def object_url(item):
    return f'{BY_KEY[item["section"]]["url"]}{"proekt" if is_project(item) else "obekt"}-{item["id"]}/'


def crumbs(items):
    li = []
    for i, (name, url) in enumerate(items):
        last = i == len(items) - 1
        li.append(f'<li><span aria-current="page">{e(name)}</span></li>' if last else f'<li><a href="{url}">{e(name)}</a></li>')
    return f'<nav class="crumbs" aria-label="Навигация"><ol>{"".join(li)}</ol></nav>'


# ---------- паспорт объекта ----------

PASSPORT_ROWS = [
    ("Сдан", "built"), ("Где", "place"), ("Размер", "size"),
    ("Материал", "material"), ("Крыша", "roof"), ("Фундамент", "foundation"), ("Срок работ", "duration"),
    ("Договор", "contract"), ("Гарантия", "warranty"),
]


def passport(item=None):
    sample = item is None
    item = item or {}
    rows = []
    for label, k in PASSPORT_ROWS:
        v = item.get(k)
        if k == "contract" and v is not None:
            v = "да" if v else "нет"
        if v or sample:  # у реального объекта пустые строки не показываем
            rows.append(f'<tr><th scope="row">{label}</th><td>{e(v) if v else "<span class=blank></span>"}</td></tr>')
    price = item.get("price_from")
    price_html = (f'<span class="passport__price-label">Цена от</span> <b>{rub(price)}</b>' if price
                  else '<span class="passport__price-label">Цена</span> <span class="passport__ask">по запросу</span>')
    num = f'№ {e(item["id"])}' if not sample else "№ — · образец"
    if sample:
        figure = f'<div class="passport__photo passport__photo--empty">{icon("photo")}<span>Фото сданного объекта</span></div>'
        title = "Название объекта"
        action = '<a class="btn btn--ghost" href="#zayavka">Хочу такую постройку</a>'
    else:
        src = item["photos"][0] if item.get("photos") else ""
        figure = f'<img class="passport__photo" src="/{e(src)}" alt="{e(item["title"])} — фото объекта" loading="lazy" width="{img_size(src)[0]}" height="{img_size(src)[1]}">'
        title = obj_name(item) if is_project(item) else item["title"]
        action = f'<a class="btn btn--frame" href="#zayavka" data-object="{e(item["title"])}">{"Рассчитать по проекту" if is_project(item) else "Хочу такую же"}</a>'
        if item.get("photos"):
            action = f'<a class="btn btn--ghost" href="{object_url(item)}">{"Смотреть проект" if is_project(item) else "Фото и паспорт объекта"}</a>' + action
    return f"""<article class="passport{' passport--sample' if sample else ''}">
  <header class="passport__bar"><span>{item.get("badge", "3D-проект") if is_project(item) else "Паспорт объекта"}</span><span class="passport__num">{num}</span></header>
  {figure}
  <div class="passport__body">
    <h3 class="passport__title">{e(title)}</h3>
    <table class="passport__table"><tbody>{''.join(rows)}</tbody></table>
    <div class="passport__foot"><p class="passport__price">{price_html}</p>{action}</div>
  </div>
</article>"""


# ---------- форма заявки ----------

def lead_form(selected_key=None):
    opts = "".join(f'<option value="{e(s["name"])}"{" selected" if s["key"] == selected_key else ""}>{e(s["name"])}</option>' for s in SECTIONS)
    when = "".join(f"<option>{e(w)}</option>" for w in WHEN_OPTIONS)
    return f"""<section class="lead" id="zayavka" aria-labelledby="zayavka-h">
  <div class="lead__in">
    <div class="lead__text">
      <h2 id="zayavka-h">Рассчитаем смету на вашу постройку</h2>
      <p>Опишите, что хотите построить. Перезвоним, уточним детали и рассчитаем смету. Если нужно — приедем на замер.</p>
      <ul class="ticks">
        <li>{icon('check')}Перезвоним и уточним задачу</li>
        <li>{icon('check')}Смета по вашим размерам и материалам</li>
      </ul>
      <p class="lead__area">Работаем в Екатеринбурге и пригородах: {e(", ".join(AREA[1:]))}.</p>
    </div>
    <form class="form" novalidate data-form>
      <div class="form__grid">
        <label class="field"><span>Что строим</span><select name="type">{opts}</select></label>
        <label class="field"><span>Размер, если знаете</span><input name="size" placeholder="например, 3×4 м" autocomplete="off"></label>
        <label class="field"><span>Где участок</span><input name="place" placeholder="город, посёлок или СНТ"></label>
        <label class="field"><span>Когда</span><select name="when">{when}</select></label>
        <label class="field field--wide"><span>Что важно</span><textarea name="note" rows="3" placeholder="мангал, остекление, материал, бюджет"></textarea></label>
        <label class="field"><span>Имя</span><input name="name" autocomplete="name"></label>
        <label class="field"><span>Телефон <i aria-hidden="true">*</i></span><input name="phone" type="tel" autocomplete="tel" required placeholder="+7" inputmode="tel" aria-describedby="phone-err"><em class="field__err" id="phone-err" hidden>Укажите телефон, чтобы мы могли перезвонить</em></label>
      </div>
      <label class="hp" aria-hidden="true">Не заполняйте <input name="website" tabindex="-1" autocomplete="off"></label>
      <label class="agree"><input type="checkbox" name="agree" required> <span>Согласен на обработку персональных данных по <a href="/politika-konfidencialnosti/">политике</a></span></label>
      <div class="form__actions"><button class="btn btn--frame" type="submit">Отправить заявку {icon('arrow')}</button>
        <p class="form__status" role="status" aria-live="polite" hidden></p></div>
    </form>
  </div>
</section>
"""


# ---------- страницы ----------

def write(path, content):
    out = ROOT / path.strip("/") / "index.html" if path != "/" else ROOT / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def listings_for(section, sub_url=None):
    items = [l for l in LISTINGS if l["section"] == section["key"]]
    if sub_url:
        items = [l for l in items if sub_url in l.get("subs", [])]
    return items


def geo_block(section, path):
    """Ссылки на гео-страницы раздела: «Где строим»."""
    geo = [(u, c) for u, (k, c) in GEO.items() if k == section["key"] and u != path]
    if not geo:
        return ""
    return ('<section class="related" aria-labelledby="geo-h"><h2 id="geo-h">' + e(cap(section["name"])) + ' в пригородах Екатеринбурга</h2><ul>'
            + "".join(f'<li><a href="{u}">{e(SEO.get(u, (c,))[0])}{icon("arrow")}</a></li>' for u, c in geo) + "</ul></section>")


def advantages_block():
    """Полоса преимуществ под первым экраном: только факты, подтверждённые владельцем (site.ADVANTAGES)."""
    if not ADVANTAGES:
        return ""
    return ('<ul class="adv" aria-label="Почему с нами спокойно">' + "".join(
        f'<li><b>{e(t)}</b><span>{e(d)}</span></li>' for t, d in ADVANTAGES) + "</ul>")


def steps_block(hid="steps-h"):
    """Этапы работы вкладками 01–04 (без JS видны все этапы подряд)."""
    tabs = "".join(
        f'<button class="steps__tab" type="button" role="tab" id="{hid}-t{n}" aria-controls="{hid}-p{n}" aria-selected="{"true" if n == 1 else "false"}"'
        f'{"" if n == 1 else " tabindex=-1"}><span>{n:02d}.</span> {e(t)}</button>' for n, (t, _, _) in enumerate(STEPS, 1))
    panels = "".join(
        f'<div class="steps__panel" role="tabpanel" id="{hid}-p{n}" aria-labelledby="{hid}-t{n}">'
        f'<p class="steps__num" aria-hidden="true">{n:02d}</p><div class="steps__body"><h3>{n:02d}. {e(t)}</h3>'
        + "".join(f"<p>{e(x)}</p>" for x in paras)
        + f'<p class="steps__result"><b>Итог:</b> {e(res)}</p></div></div>' for n, (t, paras, res) in enumerate(STEPS, 1))
    return (f'<section class="steps" aria-labelledby="{hid}" data-steps><h2 id="{hid}">Этапы работы</h2>'
            f'<div class="steps__tabs" role="tablist" aria-label="Этапы работы">{tabs}</div>{panels}'
            f'<p class="steps__cta"><a class="btn btn--frame" href="#zayavka">Оставить заявку на консультацию</a></p></section>')


def sizes_block(section):
    """Популярные размеры под H1 раздела: карточка ведёт в заявку с подставленным размером (без цен)."""
    sizes = SIZES.get(section["key"])
    if not sizes:
        return ""
    prices = SIZE_PRICES.get(section["key"], {})
    note = ("Цены «от» — за базовую комплектацию, точную смету считаем после замера. Строим и по вашим размерам." if prices
            else "Строим и по вашим размерам. Выберите ближайший — подставим его в заявку и рассчитаем смету.")
    cards = "".join(
        f'<li class="size"><p class="size__dim">{e(dim)}</p><h3 class="size__t">{e(t)}</h3><p class="size__fit">{e(fit)}</p>'
        + (f'<p class="size__price">от <b>{rub(prices[dim])}</b></p>' if dim in prices else "")
        + f'<a class="btn btn--ghost" href="#zayavka" data-size="{e(dim)}">Рассчитать {e(dim.split(" м")[0])}</a></li>' for dim, t, fit in sizes)
    return (f'<section class="sizes" aria-labelledby="sizes-h"><h2 id="sizes-h">Популярные размеры</h2>'
            f'<p class="sizes__note">{note}' + (f' Другой размер или комплектация — <a href="{CALC_PATH}?type={section["key"]}">посчитайте в калькуляторе</a>.' if section["key"] in CALC_KEYS else "")
            + f'</p><ul class="sizes__list">{cards}</ul></section>')


def section_page(section, sub=None, city=None):
    """Раздел, подкатегория или гео-страница раздела (city — город из data/texts_geo_*.py)."""
    path = sub["url"] if sub else section["url"]
    name = sub["name"] if sub else section["name"]
    items = listings_for(section, None if city else (sub["url"] if sub else None))
    text = TEXTS.get(path)
    index = bool(text) if city else (bool(items) or bool(text))
    h1 = f"{name} под ключ в Екатеринбурге" if not sub and section["key"] not in NO_TURNKEY else f"{name} в Екатеринбурге"
    seo = SEO.get(path)
    if seo:
        h1 = seo[0]
    lead = LEADS.get(path) or (f"{h1}: строим по вашим размерам, с фундаментом и кровлей. "
                               f"Оставьте заявку — перезвоним, уточним задачу и рассчитаем смету.")
    tabs = [("Все", section["url"], len(listings_for(section)))] + [
        (cap(s["name"].replace(section["name"], "").strip(" ,-") or s["name"]), s["url"], len(listings_for(section, s["url"])))
        for s in section["subs"]]
    tabs_html = ""
    if section["subs"]:
        tabs_html = '<nav class="tabs" aria-label="Подкатегории"><ul>' + "".join(
            f'<li><a href="{u}"{" aria-current=page" if u == path else ""}>{e(t)}{f' <span class="tabs__n">{n}</span>' if n else ""}</a></li>'
            for t, u, n in tabs) + "</ul></nav>"
    if items:
        items = sorted(items, key=is_project)
        SHOW = 9  # остальные карточки в HTML (для поиска), на экране — по кнопке
        grid = ('<div class="grid" data-more>' + "".join(passport(i).replace('<article class="passport', '<article class="passport is-more', 1) if n >= SHOW else passport(i)
                                                       for n, i in enumerate(items)) + "</div>"
                + (f'<p class="more"><button class="btn btn--ghost" type="button" data-more-btn>Показать все — {len(items)}</button></p>' if len(items) > SHOW else ""))
        n_obj = sum(1 for i in items if not is_project(i))
        count = (f'<h2 class="board__h">{"Наши объекты и проекты" if n_obj and n_obj < len(items) else ("Проекты" if not n_obj else "Наши объекты")}</h2>'
                 f'<p class="board__count">На стенде: {len(items)}</p>')
    else:
        grid = f"""<div class="empty">
  <div class="empty__text">
    <h2>Стенд пока пуст</h2>
    <p>Скоро здесь появятся наши сданные объекты. У каждого будет паспорт: когда сдан, где, размер, материал, крыша, фундамент, договор, гарантия и цена «от».</p>
    <p>Пока раздел наполняется, оставьте заявку: расскажем о похожих постройках и рассчитаем смету под ваш участок.</p>
    <p class="empty__actions"><a class="btn btn--frame" href="#zayavka">Рассчитать смету</a> <a class="btn btn--ghost" href="/o-kompanii/">Как мы работаем</a></p>
  </div>
  {passport()}
</div>"""
        count = ""
    others = [s for s in SECTIONS if s["key"] != section["key"] and s["core"]][:8]
    related = '<section class="related" aria-labelledby="rel-h"><h2 id="rel-h">Другие постройки из дерева</h2><ul>' + "".join(
        f'<li><a href="{s["url"]}">{e(s["name"])}{icon("arrow")}</a></li>' for s in others) + "</ul></section>"
    article = f'<section class="article" aria-label="Как выбрать">{md(text)}</section>' if text else ""
    faq = FAQ.get(path, [])
    arts = [a for a in ARTICLES if a["section"] == section["key"]][:6]
    read = ('<section class="related" aria-labelledby="art-h"><h2 id="art-h">Статьи по теме</h2><ul>' + "".join(
        f'<li><a href="{a["url"]}">{e(a["h1"])}{icon("arrow")}</a></li>' for a in arts) + "</ul></section>") if arts else ""
    trail = [("Главная", "/"), (section["name"], section["url"])] + ([(name, path)] if sub else [])
    priced = any(i.get("price_from") for i in items)
    if seo:
        with_price = seo[1].replace("{цены}", ", цены")
        title = fit_title(with_price if priced and len(with_price) <= 60 else seo[1].replace("{цены}", ""))
        desc = seo[2]
    else:
        title = fit_title(f"{h1} — цены и проекты")
        desc = lead
    schema = [crumbs_ld(trail), {"@context": "https://schema.org", "@type": "Service", "name": h1, "serviceType": name,
              "url": SITE["base_url"] + path, "provider": {"@id": ORG_ID},
              "areaServed": [{"@type": "City", "name": c} for c in ([city] if city else AREA)]}]
    if faq:
        schema.append(faq_ld(faq))
    photo_items = [i for i in items if i.get("photos")]
    if photo_items:
        schema.append({"@context": "https://schema.org", "@type": "ItemList", "name": f"{h1}: наши объекты",
                       "itemListElement": [{"@type": "ListItem", "position": n + 1, "url": SITE["base_url"] + object_url(i), "name": obj_name(i)}
                                           for n, i in enumerate(photo_items)]})
    upd = UPDATED.get(path)
    if upd:
        schema.append({"@context": "https://schema.org", "@type": "WebPage", "url": SITE["base_url"] + path,
                       "name": h1, "dateModified": upd, "inLanguage": "ru", "publisher": {"@id": ORG_ID}})
    updated_html = f'<p class="updated">Текст обновлён <time datetime="{upd}">{ru_date(upd)}</time>{reviewed()}</p>' if upd and text else ""
    pic_items = [i for i in sorted(items, key=is_project) if i.get("photos")][:3]
    pics = ('<div class="intro__pics" aria-hidden="true">' + "".join(
        f'<img src="/{e(i["photos"][0])}" alt="" width="{img_size(i["photos"][0])[0]}" height="{img_size(i["photos"][0])[1]}"{" fetchpriority=high" if n == 0 else ""} decoding="async">'
        for n, i in enumerate(pic_items)) + "</div>") if len(pic_items) == 3 else ""
    body = f"""{head(title, desc, path, index, schema)}{header()}
<main id="main">
  <div class="page">
    {crumbs(trail)}
    <div class="intro{" intro--pics" if pics else ""}">
      <div class="intro__text"><h1>{e(h1)}</h1>
      <p class="intro__lead">{e(lead)}</p>
      <p class="intro__cta"><a class="btn btn--frame" href="#zayavka">Оставить заявку</a> {quiz_button(section["key"]) if section["key"] in CALC_KEYS else '<button class="btn btn--ghost" type="button" data-callback aria-haspopup="dialog">Перезвоните мне</button>'}</p></div>
      {pics}
    </div>
    {advantages_block()}
    {tabs_html}
    {sizes_block(section) if not sub and not city else ""}
    <section class="board" aria-label="Объявления">{count}{grid}</section>
    {steps_block()}
  </div>
  {lead_form(section['key'])}
  <div class="page">
    {article}
    {updated_html}
    {howto_block() if text else ""}
    {faq_block(faq)}
    <p class="cta-line">Не нашли ответ или хотите смету? <a href="#zayavka">Оставьте заявку</a> — перезвоним и рассчитаем.</p>
    {geo_block(section, path)}
    {read}
    {related}
  </div>
</main>
{footer()}"""
    write(path, body)
    return path, index


def home_page():
    dirs = []
    for s in SECTIONS:
        subs = "".join(f'<li><a href="{x["url"]}">{e(x["name"])}</a></li>' for x in s["subs"][:4])
        dirs.append(f'<li class="dir__item"><a class="dir__head" href="{s["url"]}">{e(s["name"])}</a>{f"<ul>{subs}</ul>" if subs else ""}</li>')
    core = "".join(d for d, s in zip(dirs, SECTIONS) if s["core"])
    ext = "".join(d for d, s in zip(dirs, SECTIONS) if not s["core"])
    home_lead = (f"«{e(SITE['name'])}» строит бани, беседки, навесы, террасы, хозблоки и каркасные дома для участка в Екатеринбурге "
                 "и пригородах. Приедем на замер, подготовим проект и смету, построим под ключ.")
    seo = SEO.get("/")
    title = seo[1] if seo else "Деревянные постройки под ключ в Екатеринбурге | Магазин Урал"
    desc = seo[2] if seo else ("Строим бани, беседки, навесы, террасы и хозблоки под ключ в Екатеринбурге и области: "
                               "замер, проект, смета, договор. Оставьте заявку — рассчитаем смету.")
    text, faq, upd = TEXTS.get("/"), FAQ.get("/", []), UPDATED.get("/")
    home_text = f'<section class="article" aria-label="О деревянных постройках">{md(text)}</section>' if text else ""
    if upd and text:
        home_text += f'<p class="updated">Текст обновлён <time datetime="{upd}">{ru_date(upd)}</time>{reviewed()}</p>'
    home_text += faq_block(faq)
    schema = [faq_ld(faq)] if faq else []
    body = f"""{head(fit_title(title) if seo else title, desc, "/", True, schema)}{header()}
<main id="main">
  <div class="page">
    <div class="intro intro--home">
      <h1>{e(seo[0]) if seo else "Деревянные постройки под ключ в Екатеринбурге"}</h1>
      <p class="intro__lead">{home_lead}</p>
      <p><a class="btn btn--frame" href="#zayavka">Оставить заявку</a> {quiz_button()} <a class="btn btn--ghost" href="#razdely">Что строим</a></p>
    </div>
    {advantages_block()}
    {steps_block()}
    {('<section class="related related--cards" aria-labelledby="hw-h"><h2 id="hw-h">Наши работы</h2><ul class="ocards">' + "".join(obj_card(x) for x in [x for x in LISTINGS if x.get("photos") and not is_project(x)][:8]) + f'</ul><p class="cta-line">Все объекты с фото и паспортом — на странице «<a href="{WORKS_PATH}">Наши работы</a>».</p></section>') if any(x.get("photos") for x in LISTINGS) else ""}
    <section class="dir" id="razdely" aria-labelledby="dir-h">
      <h2 id="dir-h">Что строим</h2>
      <ul class="dir__list">{core}</ul>
      <h3 class="dir__sub">Дома и большие постройки</h3>
      <ul class="dir__list">{ext}</ul>
    </section>
    {home_text}
    <section class="related useful" aria-labelledby="use-h">
      <h2 id="use-h">Перед стройкой</h2>
      <ul>
        <li><a href="/gde-postavit-postroyku/">Где поставить баню, хозблок и туалет: расстояния{icon("arrow")}</a></li>
        <li><a href="/stati/">Статьи: как выбрать и построить{icon("arrow")}</a></li>
        <li><a href="/o-kompanii/">Как мы работаем{icon("arrow")}</a></li>
      </ul>
    </section>
  </div>
  {lead_form()}
</main>
{footer()}"""
    write("/", body)


def simple_page(path, title, h1, html_body, index=True, desc=None, form=True):
    body = f"""{head(fit_title(title), desc or title, path, index, [crumbs_ld([("Главная", "/"), (h1, path)])])}{header("#zayavka" if form else "/#zayavka")}
<main id="main"><div class="page">{crumbs([("Главная", "/"), (h1, path)])}
<div class="intro"><h1>{e(h1)}</h1></div>
<section class="article">{html_body}</section></div>
{lead_form() if form else ""}
</main>
{footer()}"""
    write(path, body)


NORMS_PATH = "/gde-postavit-postroyku/"


def norms_page():
    """Справочник расстояний: выбор постройки показывает её паспорт места, таблица — всё сразу (и без JS)."""
    picks = "".join(
        f'<label class="pick"><input type="radio" name="norm" value="{n["key"]}"{" checked" if i == 0 else ""}><span>{e(n["name"])}</span></label>'
        for i, n in enumerate(N.NORMS))
    cards = []
    for i, n in enumerate(N.NORMS):
        rows = "".join(f'<tr><th scope="row">{e(t)}</th><td>{e(n[k])}</td></tr>' for k, t in N.COLUMNS)
        link = (f'<a class="btn btn--ghost" href="{n["url"]}">Наши объекты</a>' if n["url"] else "")
        cards.append(f"""<article class="passport spot" data-norm="{n['key']}"{"" if i == 0 else " hidden"}>
  <header class="passport__bar"><span>Паспорт места</span><span class="passport__num">{e(N.SOURCE)}</span></header>
  <div class="passport__body">
    <h2 class="passport__title">{e(n['name'])}</h2>
    <table class="passport__table"><tbody>{rows}</tbody></table>
    <p class="spot__note">{e(n['note'])}</p>
    <div class="passport__foot"><a class="btn btn--frame" href="#zayavka" data-object="{e(n['name'])}">Хочу такую же</a>{link}</div>
  </div>
</article>""")
    head_cells = "".join(f'<th scope="col">{e(t)}</th>' for _, t in N.COLUMNS)
    def name_cell(n):
        return f'<a href="{n["url"]}">{e(n["name"])}</a>' if n["url"] else e(n["name"])

    trs = "".join(f'<tr><th scope="row">{name_cell(n)}</th>' + "".join(f"<td>{e(n[k])}</td>" for k, _ in N.COLUMNS) + "</tr>"
                  for n in N.NORMS)
    title = "Расстояния от бани, туалета и хозблока до забора и дома"
    desc = ("Сколько метров от границы соседа и от дома до бани, хозблока, туалета, душа, беседки и гаража. "
            "Нормы СП 53.13330.2019 для садовых участков и СНТ в таблице.")
    trail = [("Главная", "/"), ("Где поставить постройку", NORMS_PATH)]
    body = f"""{head(fit_title(title), desc, NORMS_PATH, True, [crumbs_ld(trail), faq_ld(N.FAQ)])}{header()}
<main id="main">
  <div class="page">
    {crumbs([("Главная", "/"), ("Где поставить постройку", NORMS_PATH)])}
    <div class="intro">
      <h1>Где поставить постройку на участке</h1>
      <p class="intro__lead">Выберите, что строите, — покажем минимальные расстояния до границы соседа, дома и колодца по СП 53.13330.2019 для садовых участков.</p>
    </div>
    <section class="norms" aria-label="Подбор расстояний">
      <fieldset class="norms__pick"><legend>Что ставите</legend>{picks}</fieldset>
      <div class="norms__card">{"".join(cards)}</div>
    </section>
    <section class="article">
      <h2>Все расстояния одной таблицей</h2>
      <div class="norms__scroll"><table class="norms__table"><thead><tr><th scope="col">Постройка</th>{head_cells}</tr></thead><tbody>{trs}</tbody></table></div>
      <h2>Как считать расстояние</h2>
      <p>{e(N.HOW_TO_MEASURE)}</p>
      <h2>Что проверить кроме СП</h2>
      <ul>
        <li>Тип участка. Свод правил 53.13330 написан для садовых участков и СНТ. Для ИЖС и ЛПХ действуют правила землепользования и застройки вашего муниципалитета — посмотрите их на сайте администрации.</li>
        <li>Устав и решения СНТ: они бывают строже общих норм.</li>
        <li>Охранные зоны: газ, линии электропередачи, водоохранная зона у реки или озера.</li>
        <li>Договорённость с соседом. Если постройку ставят ближе нормы, согласие соседа лучше оформить письменно.</li>
      </ul>
      {faq_block(N.FAQ).replace('<section class="faq"', '<div class="faq"').replace('</section>', '</div>')}
      <p>Таблица — справка, а не юридическое заключение. Если сомневаетесь, уточните в администрации или правлении СНТ до начала работ. На замере мы тоже подскажем, где постройка встанет без споров с соседями.</p>
    </section>
  </div>
  {lead_form()}
</main>
{footer()}"""
    write(NORMS_PATH, body)


MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def ru_date(d):
    y, m, dd = d.split("-")
    return f"{int(dd)} {MONTHS[int(m) - 1]} {y}"


def article_page(a):
    section = BY_KEY[a["section"]]
    toc = []
    body_html = md(a["body"], toc)
    trail = [("Главная", "/"), ("Статьи", "/stati/"), (a["h1"], a["url"])]
    author = SITE.get("author")
    by = (f'{author_pic("byline__pic")}<span>Автор: <a href="{author["url"]}">{e(author["name"])}</a>, {e(author["job"].lower())}</span>'
          if author else f"Редакция «{e(SITE['name'])}»")
    dates = f'Опубликовано <time datetime="{a["published"]}">{ru_date(a["published"])}</time>'
    if a.get("updated") and a["updated"] != a["published"]:
        dates += f' · обновлено <time datetime="{a["updated"]}">{ru_date(a["updated"])}</time>'
    toc_html = ('<nav class="toc" aria-labelledby="toc-h"><h2 id="toc-h">Содержание</h2><ol>' + "".join(
        f'<li><a href="#{i}">{e(t.replace("**", ""))}</a></li>' for i, t in toc) + "</ol></nav>") if len(toc) > 2 else ""
    cover = f"/assets/img/stati/{a['slug']}"
    has_cover = (ROOT / cover.lstrip("/")).with_suffix(".webp").exists()
    cover_html = (f'<img class="post__cover" src="{cover}.webp" alt="Обложка статьи «{e(a["h1"])}»" width="1200" height="630" '
                  f'decoding="async" fetchpriority="high">') if has_cover else ""
    more = [x for x in ARTICLES if x["section"] == a["section"] and x is not a][:4]
    more_html = ('<section class="related" aria-labelledby="more-h"><h2 id="more-h">Ещё по теме</h2><ul>' + "".join(
        f'<li><a href="{x["url"]}">{e(x["h1"])}{icon("arrow")}</a></li>' for x in more) + "</ul></section>") if more else ""
    art_ld = {"@context": "https://schema.org", "@type": "Article", "headline": a["h1"], "description": a["desc"],
              "datePublished": a["published"], "dateModified": a.get("updated") or a["published"],
              "author": {"@type": "Person", "@id": SITE["base_url"] + author["url"] + "#person", "name": author["name"], "jobTitle": author["job"],
                         "url": SITE["base_url"] + author["url"]} if author else {"@id": ORG_ID},
              "publisher": {"@id": ORG_ID}, "image": SITE["base_url"] + (cover + ".jpg" if has_cover else "/assets/img/og.png"),
              "mainEntityOfPage": SITE["base_url"] + a["url"], "inLanguage": "ru"}
    schema = [crumbs_ld(trail), art_ld] + ([faq_ld(a["faq"])] if a.get("faq") else [])
    body = f"""{head(fit_title(a["title"]), a["desc"], a["url"], True, schema, "article", cover + ".jpg" if has_cover else None)}{header()}
<main id="main">
  <article class="page post">
    {crumbs(trail)}
    <header class="intro">
      <h1>{e(a["h1"])}</h1>
      <p class="intro__lead">{inline(a["lead"])}</p>
      <p class="byline">{by}<span>{dates}</span></p>
      {cover_html}
    </header>
    {toc_html}
    <div class="article article--post">{body_html}</div>
    <aside class="hand" aria-label="Заказать строительство">
      <h2>Не хотите строить сами? Построим</h2>
      <p>В разделе «<a href="{section["url"]}">{e(section["name"])}</a>» — что мы строим и как. Оставьте заявку: перезвоним, приедем на замер и рассчитаем смету.</p>
      <p><a class="btn btn--frame" href="#zayavka">Оставить заявку</a></p>
    </aside>
    <div class="article article--post">{faq_block(a.get("faq"))}</div>
    {author_card()}
    <p class="totop"><a href="#main">Наверх ↑</a></p>
    {more_html}
  </article>
  {lead_form(a["section"])}
</main>
{footer()}"""
    write(a["url"], body)


def articles_hub():
    groups = []
    for s in SECTIONS:
        arts = [a for a in ARTICLES if a["section"] == s["key"]]
        if arts:
            groups.append(f'<h2>{e(s["name"])}</h2><ul class="hub">' + "".join(
                f'<li><a href="{a["url"]}">{e(a["h1"])}</a><span>{e(a["desc"])}</span></li>' for a in arts) + "</ul>")
    trail = [("Главная", "/"), ("Статьи", "/stati/")]
    title = "Статьи о деревянных постройках на даче: бани, беседки"
    desc = ("Как выбрать и построить баню, беседку, навес, веранду, каркасный дом и сарай: размеры, фундамент, крыша, "
            "проекты и нормы. Справочник для дачи в Екатеринбурге.")
    body = f"""{head(fit_title(title), desc, "/stati/", True, [crumbs_ld(trail)])}{header()}
<main id="main"><div class="page">{crumbs(trail)}
<div class="intro"><h1>Статьи о деревянных постройках</h1>
<p class="intro__lead">Как выбрать, спроектировать и построить постройку для участка. Если строить самим не хочется — в каждой статье есть ссылка на раздел, где можно заказать постройку.</p></div>
<section class="article">{"".join(groups)}</section></div>
{lead_form()}
</main>
{footer()}"""
    write("/stati/", body)


def obj_name(x):
    """Полное имя объекта для H1, title и alt: запрос из Вордстата + название («Беседка с печью «Огневушка»»)."""
    q = re.search(r"«[^»]+»", x["title"])
    name = f'{x["kw"]} {q.group(0)}' if x.get("kw") and q else x["title"]
    if is_project(x) and x.get("size"):
        name += f' {x["size"]}'
    return name


def obj_card(x):
    """Карточка объекта с фото — для «Похожих объектов» и «Наших работ»."""
    ph = x["photos"][0]
    w, h = img_size(ph)
    return (f'<li class="ocard"><a href="{object_url(x)}"><img src="/{e(ph)}" alt="{e(obj_name(x))} — фото" width="{w}" height="{h}" loading="lazy" decoding="async">'
            f'<span class="ocard__t">{e(obj_name(x))}</span><span class="ocard__d">{e(cap(x.get("lead") or ""))}</span></a></li>')


def object_page(item):
    """Страница объекта: фото, паспорт, описание, состав работ, цена, похожие объекты, заявка."""
    section = BY_KEY[item["section"]]
    key = section["key"]
    path = object_url(item)
    photos = item.get("photos") or []
    full = obj_name(item)
    proj = is_project(item)
    gallery = "".join(
        f'<img src="/{e(ph)}" alt="{e(full)} — {item.get("alt_kind", "3D-визуализация") if proj else ("общий вид" if n == 0 else f"фото {n + 1}")}" width="{img_size(ph)[0]}" height="{img_size(ph)[1]}" '
        f'{"fetchpriority=high" if n == 0 else "loading=lazy"} decoding="async">' for n, ph in enumerate(photos))
    rows = []
    for label, k in PASSPORT_ROWS:
        v = item.get(k)
        if k == "contract" and v is not None:
            v = "да" if v else "нет"
        if v:
            rows.append(f'<tr><th scope="row">{label}</th><td>{e(v)}</td></tr>')
    price = item.get("price_from")
    price_html = f'<p class="obj__price">Цена такой постройки — от <b>{rub(price)}</b></p>' if price else ""
    same = [x for x in LISTINGS if x["section"] == key and x is not item and x.get("photos") and is_project(x) == proj]
    sub_set = set(item.get("subs", []))
    same.sort(key=lambda x: -len(sub_set & set(x.get("subs", []))))
    others = same[:3]
    subs = [s for s in section["subs"] if s["url"] in sub_set]
    trail = [("Главная", "/"), (section["name"], section["url"])] + ([(subs[0]["name"], subs[0]["url"])] if subs else []) + [(full, path)]
    prod = {"@context": "https://schema.org", "@type": "Product", "name": full, "sku": item["id"],
            "image": [SITE["base_url"] + "/" + ph for ph in photos], "brand": {"@type": "Brand", "name": SITE["name"]},
            "description": re.sub(r"\s+", " ", item.get("description") or item["title"])[:300]}
    if price:
        days = int(re.search(r"\d+", item.get("duration") or "14").group())
        prod["offers"] = {"@type": "Offer", "priceCurrency": "RUB", "price": price, "url": SITE["base_url"] + path,
                          "seller": {"@id": ORG_ID}, "availability": "https://schema.org/InStock",
                          # доставка и монтаж по Екатеринбургу — в цене (site.DELIVERY); индексы 620xxx
                          "shippingDetails": {"@type": "OfferShippingDetails",
                                              "shippingRate": {"@type": "MonetaryAmount", "value": 0, "currency": "RUB"},
                                              "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "RU",
                                                                      "postalCodeRange": {"@type": "PostalCodeRangeSpecification", "postalCodeBegin": "620000", "postalCodeEnd": "620999"}},
                                              "deliveryTime": {"@type": "ShippingDeliveryTime",
                                                               "handlingTime": {"@type": "QuantitativeValue", "minValue": days, "maxValue": days * 2, "unitCode": "DAY"},
                                                               "transitTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "DAY"}}},
                          # изготовление по индивидуальному заказу — возврата нет (ЗоЗПП ст. 26.1), недостатки — по гарантии
                          "hasMerchantReturnPolicy": {"@type": "MerchantReturnPolicy", "applicableCountry": "RU",
                                                      "returnPolicyCategory": "https://schema.org/MerchantReturnNotPermitted"}}
    title = fit_title(fit_len(full, ([" — проект и цена"] if proj and item.get("price_from") else [" — проект"] if proj else []) + [f', {item["place"]}' if item.get("place") else " в Екатеринбурге", " — фото и паспорт", " — фото объекта", ", фото", " — наш объект"] + ([", цена «от»"] if item.get("price_from") else []), 50, 60))
    facts = ", ".join(x for x in (item.get("size"), item.get("material"), item.get("place"), item.get("built") and f'сдан {item["built"]}') if x)
    lead_txt = item.get("lead") or ""
    desc = fit_len(f'{full}' + (f" — {lead_txt}" if lead_txt else (f': {facts}.' if facts else ".")),
                   [(" 3D-проект" if proj else " Фото и паспорт объекта") + (" с ценой «от»." if item.get("price_from") else "."), " Построим такую же по вашим размерам.", " Ответим на вопросы о замере и сроках.", " Оставьте заявку — перезвоним.", " Гарантия 3 года.", " Работаем по договору.", " Екатеринбург.", " Под ключ.", " 3D-проект.", " Замер."], 150, 160)
    name_l = section["name"].lower()
    art = next((a for a in ARTICLES if a["slug"] == OT.ARTICLE.get(key)), None)
    sub_links = ", ".join(f'[{s["name"].lower()}]({s["url"]})' for s in subs)
    text = f"""{item.get("description", "")}

## Что входит в работы

{"Строим по этому проекту" if proj else "Строим"} «{item["title"].split("«")[-1].rstrip("»")}» и похожие постройки под ключ — от замера до уборки участка:

""" + "\n".join(f"- {x}" for x in OT.WORKS.get(key, [])) + f"""

## Сколько стоит такая постройка

""" + (f"Постройка такого типа у нас — от {rub(price)} за базовую комплектацию. " if price else "") + f"""{OT.PRICE.get(key, "Цену считаем по вашим размерам и материалам.")} Смету по позициям присылаем после замера, итог фиксируем в договоре, гарантия — {COMPANY["warranty"]}.
""" + (f"\nКак выбрать размер и что учесть заранее — в статье [«{art['h1']}»]({art['url']}).\n" if art else "") + f"""
## Как ухаживать за постройкой

Дерево служит долго, если за ним следить. Несколько простых правил:

""" + "\n".join(f"- {x}" for x in OT.CARE.get(key, [])) + f"""

""" + ("""## Что можно изменить в проекте

Проект — это отправная точка, а не жёсткий шаблон. Под ваш участок меняем длину и ширину, число отсеков и перегородок, положение дверей и окон, форму и материал крыши, отделку и цвет. Если нужен утеплённый вариант для зимы, добавим утепление и внутреннюю обшивку. Все изменения показываем в 3D до договора.

""" if proj else "") + f"""## {"Как заказать по проекту" if proj else "Как построить такую же"}

Оставьте заявку и напишите, что понравилось в этом {"проекте" if proj else "объекте"}. Перезвоним, уточним размеры и участок, приедем на замер, подготовим 3D-проект и смету. Можно повторить постройку один в один или изменить размер, крышу и отделку.
""" + (f"\nПохожие постройки собраны в разделах: {sub_links}. " if sub_links else "\n") + f"Все {name_l} — в каталоге «[{section['name']}]({section['url']})»."
    body = f"""{head(title, desc[:160], path, True, [crumbs_ld(trail), prod], "website", "/" + photos[0])}{header()}
<main id="main">
  <div class="page">
    {crumbs(trail)}
    <div class="intro"><h1>{e(full)}</h1><p class="intro__lead">{e(full)} — {e(lead_txt)}</p>{price_html}
      <p class="intro__cta"><a class="btn btn--frame" href="#zayavka" data-object="{e(item["title"])}">{"Рассчитать по проекту" if proj else "Хочу такую же"}</a> <button class="btn btn--ghost" type="button" data-callback aria-haspopup="dialog">Перезвоните мне</button></p></div>
    <div class="obj">
      <div class="obj__gallery">{gallery}</div>
      <article class="passport obj__passport"><header class="passport__bar"><span>{item.get("badge", "3D-проект") if proj else "Паспорт объекта"}</span><span class="passport__num">№ {e(item["id"])}</span></header>
        <div class="passport__body"><table class="passport__table"><tbody>{''.join(rows)}</tbody></table>
        <p class="passport__note">{f'Цена от <b>{rub(price)}</b> — точную смету считаем после замера' if price else 'Цену рассчитаем по вашим размерам'}</p><a class="btn btn--frame" href="#zayavka" data-object="{e(item["title"])}">{"Рассчитать по проекту" if proj else "Рассчитать такую же"}</a></div></article>
    </div>
    <section class="article obj__text">{md(text)}</section>
    {howto_block()}
    {('<section class="related related--cards" aria-labelledby="oth-h"><h2 id="oth-h">{"Похожие проекты" if proj else "Похожие объекты"}</h2><ul class="ocards">' + "".join(obj_card(x) for x in others) + "</ul></section>") if others else ""}
    <p class="cta-line">{f'Все проекты — на странице «<a href="{PROJECTS_PATH}">Проекты построек</a>».' if proj else f'Все наши объекты с фото — на странице «<a href="{WORKS_PATH}">Наши работы</a>».'}</p>
  </div>
  {lead_form(key)}
</main>
{footer()}"""
    write(path, body)


WORKS_PATH = "/nashi-raboty/"
PROJECTS_PATH = "/proekty/"


def projects_page():
    """«Проекты построек»: 3D-проекты по разделам — не сданные объекты, а готовые решения для заказа."""
    items = [x for x in LISTINGS if is_project(x) and x.get("photos")]
    if not items:
        return False
    groups = []
    for s in SECTIONS:
        xs = [x for x in items if x["section"] == s["key"]]
        if xs:
            groups.append(f'<h2 id="p-{s["key"]}">{e(s["name"])} <span class="tabs__n">{len(xs)}</span></h2><ul class="ocards">'
                          + "".join(obj_card(x) for x in xs) + f'</ul><p class="cta-line">Как выбрать и что влияет на цену — в разделе «<a href="{s["url"]}">{e(s["name"])}</a>».</p>')
    intro = md(f"""Здесь собраны готовые проекты построек: каркасные бани с верандой и террасой, хозблоки с туалетом, душем и дровником, дачные туалеты, бытовки, мангальные зоны, летние кухни и курятники с вольером. Всего {len(items)} проектов с размерами.

Каждый проект можно построить как есть или изменить: размер, планировку, крышу, окна и отделку. Нажмите «Рассчитать по проекту» — уточним участок и пришлём смету.

Сданные объекты с фото с участков — на странице «[Наши работы]({WORKS_PATH})».""")
    body = f"""{head(fit_title("Проекты бань, хозблоков, туалетов и бытовок с ценами"), "Проекты каркасных бань, хозблоков с туалетом и душем, дачных туалетов и бытовок с ценой «от». Построим по проекту или изменим под ваш участок в Екатеринбурге.", PROJECTS_PATH, True, [crumbs_ld([("Главная", "/"), ("Проекты", PROJECTS_PATH)]), {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Проекты построек", "url": SITE["base_url"] + PROJECTS_PATH, "publisher": {"@id": ORG_ID}}])}{header()}
<main id="main"><div class="page">{crumbs([("Главная", "/"), ("Проекты", PROJECTS_PATH)])}
<div class="intro"><h1>Проекты бань, хозблоков, туалетов и бытовок</h1><p class="intro__cta"><a class="btn btn--frame" href="#zayavka">Рассчитать по проекту</a></p></div>
<section class="article">{intro}</section>
<section class="works">{"".join(groups)}</section></div>
{lead_form()}
</main>
{footer()}"""
    write(PROJECTS_PATH, body)
    return True


def works_page():
    """«Наши работы»: все объекты с фото по разделам."""
    items = [x for x in LISTINGS if x.get("photos") and not is_project(x)]
    groups = []
    for s in SECTIONS:
        xs = [x for x in items if x["section"] == s["key"]]
        if xs:
            groups.append(f'<h2 id="w-{s["key"]}">{e(s["name"])} <span class="tabs__n">{len(xs)}</span></h2>'
                          f'<ul class="ocards">' + "".join(obj_card(x) for x in xs) + "</ul>"
                          f'<p class="cta-line">Цены, размеры и как выбрать — в разделе «<a href="{s["url"]}">{e(s["name"])}</a>».</p>')
    n = len(items)
    intro = md(f"""Здесь собраны наши работы — беседки, павильоны, террасы, веранды, крыльца и дачные домики, которые мы построили на участках в Екатеринбурге и пригородах. Всего {n} объектов с фото.

У каждой постройки есть своя страница: фото, паспорт с материалом, крышей и гарантией, описание и состав работ. Понравился объект — нажмите «Хочу такую же», и мы рассчитаем его под ваш участок: можно повторить один в один или изменить размер, крышу и отделку.

Фото сделаны нашими бригадами на объектах; на снимках стоит наш знак «{SITE['name']}».""")
    body = f"""{head(fit_title("Наши работы: беседки, террасы и постройки из дерева"), "Наши работы в Екатеринбурге и пригородах: беседки, павильоны, террасы, веранды и дачные домики с фото и паспортом объекта. Построим такую же по вашим размерам.", WORKS_PATH, True, [crumbs_ld([("Главная", "/"), ("Наши работы", WORKS_PATH)]), {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Наши работы", "url": SITE["base_url"] + WORKS_PATH, "publisher": {"@id": ORG_ID}}])}{header()}
<main id="main"><div class="page">{crumbs([("Главная", "/"), ("Наши работы", WORKS_PATH)])}
<div class="intro"><h1>Наши работы: постройки из дерева</h1><p class="intro__cta"><a class="btn btn--frame" href="#zayavka">Рассчитать свою постройку</a></p></div>
<section class="article">{intro}</section>
<section class="works">{"".join(groups)}</section></div>
{lead_form()}
</main>
{footer()}"""
    write(WORKS_PATH, body)
    return bool(items)

CALC_FAQ = [
    ("Насколько точна цена из калькулятора?",
     "Калькулятор считает по средним ценам рынка Екатеринбурга для базовой комплектации, поэтому цена примерная. "
     "Точную стоимость называем после замера и сметы: на неё влияют грунт, подъезд к участку, материалы и отделка."),
    ("Что входит в базовую комплектацию?",
     "Фундамент на винтовых сваях, каркас, кровля, пол и антисептическая обработка дерева. "
     "Доставка и монтаж в Екатеринбурге входят в цену, доставку в пригороды и область считаем в смете."),
    ("Можно построить по своему размеру?",
     "Да, в калькуляторе можно указать свою ширину и длину. Размеры, материалы и планировку подгоняем под ваш участок, "
     "а по готовому эскизу проектный отдел сделает 3D-проект."),
    ("Как получить точную смету?",
     "Нажмите «Получить точный расчёт» и оставьте телефон. Мы перезвоним, уточним детали и, если нужно, приедем на замер, "
     "а смету по позициям закрепим в договоре."),
]


def calc_page():
    """Калькулятор стоимости: виджет (site.js), цены «от» по размерам, текст, FAQ, форма заявки."""
    path = CALC_PATH
    h1 = "Калькулятор стоимости беседки, бани и других построек"
    title = "Калькулятор стоимости беседки, бани, навеса онлайн"
    desc = ("Калькулятор стоимости беседки, бани, террасы, навеса и хозблока онлайн: выберите размер и комплектацию — "
            "покажем примерную цену по рынку Екатеринбурга.")
    rows = []
    for t in CALC:
        cells = "".join(f"<li>{e(size_label(t, sz))} — от {rub(calc_round(calc_base(t, calc_area(t, sz)) * CALC_RANGE[0]))}</li>" for sz in t["sizes"])
        rows.append(f'<tr><th scope="row"><a href="{BY_KEY[t["key"]]["url"]}">{e(t["name"])}</a></th><td><ul class="calc-t__sizes">{cells}</ul></td></tr>')
    table = ('<div class="table-wrap"><table class="calc-t"><caption>Примерные цены «от» по размерам, базовая комплектация</caption>'
             '<thead><tr><th scope="col">Постройка</th><th scope="col">Размер и цена</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
    text = f"""<h2>Как работает калькулятор</h2>
<p>Калькулятор стоимости показывает примерную цену деревянной постройки за минуту: выберите, что строим, размер и комплектацию — цена пересчитается сразу.
Расчёт сделан по <b>средним ценам рынка Екатеринбурга</b> на сайтах строительных компаний и сверен с ценами наших объектов в <a href="{WORKS_PATH}">«Наших работах»</a>.</p>
<p>Цена в калькуляторе — вилка «от и до», а не точная смета. Точную стоимость назовём после замера: смету расписываем по позициям и закрепляем в договоре, а гарантия на работы — {e(COMPANY["warranty"])}.</p>
<h2>Что влияет на стоимость</h2>
<ul>
<li><b>Размер и форма</b> — чем больше площадь, тем ниже цена квадратного метра, но выше итог.</li>
<li><b>Тип постройки</b> — закрытая беседка с остеклением дороже открытой примерно в полтора раза, тёплая — почти вдвое.</li>
<li>Материал — клеёный брус и бревно дороже строганого бруса, лиственница дороже хвойной доски.</li>
<li>Кровля и фундамент — мягкая черепица дороже профлиста, на сложном грунте нужны дополнительные сваи.</li>
<li>Печь и мангал — печной комплекс добавляет к цене беседки или летней кухни заметную сумму.</li>
<li>Участок — уклон, подъезд для машины и расстояние от Екатеринбурга.</li>
</ul>
<p>Размеры удобно подобрать по нашим статьям: <a href="/stati/chertezh-besedki/">чертёж беседки с размерами</a>, <a href="/stati/kakoy-saray/">какой сарай построить на даче</a> и <a href="/stati/karkasnyy-dom-razmery/">размеры каркасного дома</a>.
Все типы построек и наши объекты с фото — в разделах <a href="{BY_KEY["besedka"]["url"]}">беседки</a>, <a href="{BY_KEY["banya"]["url"]}">бани</a>, <a href="{BY_KEY["naves"]["url"]}">навесы</a> и <a href="/#razdely">в каталоге</a>.</p>
<h2>Цены по размерам</h2>
<p>Ниже — нижняя граница вилки для популярных размеров в базовой комплектации. Цена примерная и зависит от участка и отделки.</p>
{table}"""
    schema = [crumbs_ld([("Главная", "/"), ("Калькулятор стоимости", path)]), faq_ld(CALC_FAQ),
              {"@context": "https://schema.org", "@type": "WebApplication", "name": "Калькулятор стоимости деревянных построек",
               "url": SITE["base_url"] + path, "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any",
               "inLanguage": "ru", "isAccessibleForFree": True, "provider": {"@id": ORG_ID}}]
    body = f"""{head(fit_title(title), desc, path, True, schema)}{header()}
<main id="main"><div class="page">{crumbs([("Главная", "/"), ("Калькулятор стоимости", path)])}
<div class="intro"><h1>{e(h1)}</h1>
<p class="intro__lead">Калькулятор стоимости беседки, бани, террасы, навеса, хозблока и каркасного дома: выберите постройку, размер и комплектацию — покажем примерную цену. Точный расчёт пришлём после заявки.</p></div>
<section class="calc" aria-label="Калькулятор" data-calc="page"><noscript><p>Калькулятору нужен JavaScript. <a href="#zayavka">Оставьте заявку</a> — рассчитаем стоимость вручную.</p></noscript></section>
<section class="article">{text}</section>
{faq_block(CALC_FAQ)}
<p class="cta-line">Хотите точную смету? <a href="#zayavka">Оставьте заявку</a> — перезвоним и рассчитаем по вашему участку.</p>
</div>
{lead_form()}
</main>
{footer()}"""
    write(path, body)


def contacts_page():
    """Контакты: создаётся, только когда в site.py есть телефон или реквизиты ИП."""
    ip = SITE.get("ip") or {}
    parts = []
    if SITE.get("phone"):
        parts.append(f'<p>Телефон: <a href="tel:{re.sub(r"[^+0-9]", "", SITE["phone"])}">{e(SITE["phone"])}</a></p>')
    if SITE.get("hours"):
        parts.append(f"<p>Часы работы: {e(SITE['hours'])}</p>")
    if SITE.get("email"):
        parts.append(f'<p>Почта: <a href="mailto:{e(SITE["email"])}">{e(SITE["email"])}</a></p>')
    if ip:
        parts.append("<h2>Реквизиты</h2>" + "".join(f"<p>{x}</p>" for x in [
            f"ИП {e(ip['name'])}" if ip.get("name") else "", f"ИНН {e(ip['inn'])}" if ip.get("inn") else "",
            f"ОГРНИП {e(ip['ogrnip'])}" if ip.get("ogrnip") else "", e(ip["address"]) if ip.get("address") else ""] if x))
    parts.append(f"<h2>Где работаем</h2><p>{e(', '.join(AREA))}.</p>")
    simple_page(CONTACTS_PATH, "Контакты «Магазин Урал»: телефон и реквизиты", "Контакты", "".join(parts), index=True,
                desc="Контакты компании «Магазин Урал»: телефон, часы работы и реквизиты ИП. Строим деревянные постройки в Екатеринбурге и пригородах — оставьте заявку на замер.")


POLICY = """
Настоящая политика определяет порядок обработки персональных данных посетителей сайта {domain} (далее — сайт) и меры по их защите в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных».

## 1. Оператор

Оператор персональных данных — индивидуальный предприниматель {name}, ИНН {inn}{ogrnip}{address}.

Связаться с оператором можно по телефону {phone}{email}.

## 2. Какие данные мы обрабатываем

- имя;
- номер телефона;
- адрес электронной почты, если вы его указали;
- сведения о постройке и участке, которые вы сообщили в заявке (тип постройки, размер, населённый пункт, сроки, пожелания);
- технические данные: IP-адрес, сведения о браузере и устройстве, файлы cookie, данные сервисов веб-аналитики.

## 3. Цели обработки

- связаться с вами по заявке или запросу обратного звонка;
- подготовить смету, договориться о замере и заключить договор;
- улучшать работу сайта по обезличенной статистике посещений.

## 4. Правовые основания

Данные обрабатываются на основании вашего согласия, которое вы даёте, отмечая согласие в форме на сайте, а также для подготовки и исполнения договора, стороной которого вы являетесь.

## 5. Как мы обрабатываем данные

Обработка включает сбор, запись, систематизацию, хранение, уточнение, использование, удаление и уничтожение данных. Мы не продаём данные и не передаём их третьим лицам, кроме случаев, прямо предусмотренных законом. Данные хранятся на территории Российской Федерации.

## 6. Сроки хранения

Данные хранятся не дольше, чем этого требуют цели обработки, или до отзыва согласия. После этого данные удаляются, если закон не требует хранить их дольше.

## 7. Ваши права

Вы вправе получить сведения об обработке ваших данных, потребовать их уточнения, блокирования или удаления, а также отозвать согласие, направив обращение оператору по контактам из раздела 1. Ответ дадим в сроки, установленные законом.

## 8. Защита данных

Оператор принимает правовые, организационные и технические меры для защиты персональных данных от неправомерного доступа, изменения, распространения и уничтожения.

## 9. Изменение политики

Оператор вправе изменять политику; новая редакция действует с момента публикации на этой странице.
"""


TEAM = [
    ("Проектный отдел", "Превращает идею в 3D-проект и рабочие чертежи, считает конструкцию и объём материалов."),
    ("Отдел продаж", "Помогает выбрать постройку, размер и материалы под участок и бюджет, готовит смету."),
    ("Своё производство", "Заготавливает и обрабатывает дерево, наносит огне- и биозащиту, изготавливает детали по проекту."),
    ("Монтажные бригады", f"Бригады со стажем {COMPANY['crews']} собирают постройку на участке и убирают за собой."),
]
QUALITY = [
    ("Считаем под Урал", "Каркас, кровлю и фундамент рассчитываем под снеговую и ветровую нагрузку Екатеринбурга и области."),
    ("Готовим дерево заранее", "Детали обрабатываем на производстве: огне- и биозащита, пропитка, покраска в выбранный цвет."),
    ("Фиксируем всё в договоре", "Материалы, сроки, порядок оплаты и гарантию прописываем в договоре, к нему прикладываем смету и проект."),
    ("Показываем до стройки", "Делаем 3D-визуализацию: размеры, крышу и отделку можно поменять до начала работ."),
]


def about_page():
    """О компании: факты со слов владельца (site.COMPANY, ADVANTAGES, STEPS, автор) — без превосходных степеней (38-ФЗ ст. 5)."""
    path = "/o-kompanii/"
    objs = [x for x in LISTINGS if x.get("photos") and not is_project(x)]
    projs = [x for x in LISTINGS if x.get("photos") and is_project(x)]
    facts = [(f"с {COMPANY['since']}", "года проектируем и строим из дерева"), (COMPANY["warranty"], "гарантия на постройку по договору"),
             (COMPANY["crews"].replace("более ", "15+ ").split()[0] + " лет" if "15" in COMPANY["crews"] else COMPANY["crews"], "стаж монтажных бригад"),
             (str(len(objs) + len(projs)), "объектов и проектов с фото на сайте")]
    facts_html = '<ul class="facts">' + "".join(f"<li><b>{e(a)}</b><span>{e(b)}</span></li>" for a, b in facts) + "</ul>"
    a = SITE.get("author")
    team = "".join(f'<li><h3>{e(t)}</h3><p>{e(d)}</p></li>' for t, d in TEAM)
    quality = "".join(f'<li><h3>{e(t)}</h3><p>{e(d)}</p></li>' for t, d in QUALITY)
    works = ('<section class="related related--cards" aria-labelledby="ab-w"><h2 id="ab-w">Наши работы</h2><ul class="ocards">'
             + "".join(obj_card(x) for x in objs[::max(1, len(objs) // 8)][:8])
             + f'</ul><p class="cta-line">Все объекты с фото и паспортом — в разделе «<a href="{WORKS_PATH}">Наши работы</a>», 3D-проекты — в разделе «<a href="{PROJECTS_PATH}">Проекты</a>».</p></section>') if objs else ""
    ip = SITE.get("ip") or {}
    req = " · ".join(x for x in [f"ИП {ip['name']}" if ip.get("name") else "", f"ИНН {ip['inn']}" if ip.get("inn") else "",
                                 f"ОГРНИП {ip['ogrnip']}" if ip.get("ogrnip") else "", ip.get("address", "")] if x)
    lead = (f"«{SITE['name']}» — строительная компания из Екатеринбурга. С {COMPANY['since']} года проектируем и строим деревянные постройки "
            "для загородного участка: бани, беседки, террасы и веранды, навесы, хозблоки и каркасные дома.")
    title = f"О компании «{SITE['name']}»: строим из дерева с {COMPANY['since']} года"
    desc = (f"О компании «{SITE['name']}»: с {COMPANY['since']} года строим бани, беседки, террасы и хозблоки в Екатеринбурге. "
            f"Инженер-конструктор, свой цех, договор и гарантия {COMPANY['warranty']}.")
    schema = [crumbs_ld([("Главная", "/"), ("О компании", path)]),
              {"@context": "https://schema.org", "@type": "AboutPage", "url": SITE["base_url"] + path, "name": title,
               "inLanguage": "ru", "mainEntity": {"@id": ORG_ID}}] + ([person_ld()] if a else [])
    body = f"""{head(fit_title(title), desc, path, True, schema)}{header()}
<main id="main"><div class="page">{crumbs([("Главная", "/"), ("О компании", path)])}
<div class="intro"><div class="intro__text"><h1>О компании «{e(SITE['name'])}»</h1>
<p class="intro__lead">{e(lead)}</p>
<p class="intro__cta"><a class="btn btn--frame" href="#zayavka">Оставить заявку</a> {quiz_button()}</p></div></div>
{facts_html}
<section class="article about" aria-labelledby="ab-who">
<h2 id="ab-who">Кто мы</h2>
<p>Мы строим то, что делает участок удобным для жизни: <a href="/bani/">бани</a>, <a href="/besedki/">беседки</a> с мангалом и без, <a href="/terrasy/">террасы</a> и <a href="/verandy/">веранды</a>, <a href="/navesy/">навесы и карпорты</a>, <a href="/hozbloki/">хозблоки</a> и <a href="/karkasnye-doma/">каркасные дома</a>.
Проект, производство деталей и монтаж ведём сами, без посредников, поэтому отвечаем за постройку целиком — от чертежа до уборки участка после сдачи.</p>
<p>Работаем по официальному договору с ИП, смету расписываем по позициям, гарантию {e(COMPANY['warranty'])} прописываем в договоре. Предварительную цену можно узнать сразу — в <a href="{CALC_PATH}">калькуляторе стоимости</a>, точную назовём после замера.</p>
</section>
<section class="team" aria-labelledby="ab-team"><h2 id="ab-team">Кто работает над вашей постройкой</h2>
{author_card("Главный инженер-конструктор", "h3") if a else ""}
<ul class="cards4">{team}</ul></section>
<section class="team" aria-labelledby="ab-q"><h2 id="ab-q">Как мы строим</h2><ul class="cards4">{quality}</ul></section>
{works}
{steps_block("about-steps-h")}
{howto_block()}
<section class="article about" aria-labelledby="ab-where">
<h2 id="ab-where">Где работаем</h2>
<p>{e(", ".join(AREA))}. Если вашего посёлка нет в списке — напишите в заявке или <button class="linkbtn" type="button" data-max>в MAX</button>, обсудим выезд.</p>
<p>Перед стройкой проверьте, где постройка встанет по нормам: расстояния до забора, дома и колодца собраны в справочнике «<a href="/gde-postavit-postroyku/">Где поставить постройку</a>», а советы инженера — в <a href="/stati/">статьях</a>.</p>
{('<h2>Реквизиты</h2><ul>' + "".join(f"<li>{e(x)}</li>" for x in req.split(" · ")) + "</ul><p>Работаем круглосуточно, без выходных.</p>") if req else ""}
</section>
</div>
{lead_form()}
</main>
{footer()}"""
    write(path, body)


def author_page():
    """Страница автора статей: кто он, за что отвечает, какие статьи проверил (ProfilePage + Person)."""
    a = SITE["author"]
    path = a["url"]
    trail = [("Главная", "/"), ("О компании", "/o-kompanii/"), (a["name"], path)]
    h1 = f"{a['name']} — {a['job'].lower()}"
    groups = []
    for sec in SECTIONS:
        arts = [x for x in ARTICLES if x["section"] == sec["key"]]
        if arts:
            groups.append(f'<h3>{e(sec["name"])}</h3><ul>' + "".join(f'<li><a href="{x["url"]}">{e(x["h1"])}</a></li>' for x in arts) + "</ul>")
    text = f"""<p>{e(a['name'])} — {e(a['job'].lower())} компании «{e(SITE['name'])}». {e(AUTHOR_ABOUT)}</p>
<h2>За что отвечает</h2>
<ul>
<li><b>Расчёт конструкции</b> — сечения бруса, шаг стропил и лаг, нагрузка на фундамент под снег и ветер Урала.</li>
<li><b>Рабочие чертежи</b> — по ним производство готовит детали, а бригада собирает постройку на участке.</li>
<li>Проверка проектов перед производством — размеры, узлы, кровля, вентиляция бани и пароизоляция.</li>
<li>Изменения по просьбе заказчика — если нужно поменять размер, крышу или добавить печь, пересчитывает конструкцию.</li>
</ul>
<h2>Статьи</h2>
<p>Все статьи раздела «<a href="/stati/">Статьи</a>» написаны или проверены {e(a['short'])}: советы в них совпадают с тем, как мы строим на самом деле. Если хотите задать вопрос по своей постройке — <a href="#zayavka">оставьте заявку</a>.</p>
{''.join(groups)}"""
    title = f"{a['name'].split()[0]} {a['name'].split()[-1]} — {a['job'].lower()} «{SITE['name']}»"
    desc = (f"{a['name']} — {a['job'].lower()} «{SITE['name']}»: расчёт конструкций бань, беседок и домов под снег Урала, "
            "чертежи и проверка статей.")
    schema = [crumbs_ld(trail), {"@context": "https://schema.org", "@type": "ProfilePage", "url": SITE["base_url"] + path,
                                 "name": title, "inLanguage": "ru", "mainEntity": person_ld()}]
    body = f"""{head(fit_title(title), desc, path, True, schema)}{header()}
<main id="main"><div class="page">{crumbs(trail)}
<div class="intro intro--person">{author_pic("person__pic")}<div class="intro__text"><h1>{e(h1)}</h1>
<p class="intro__lead">Инженер «{e(SITE['name'])}»: рассчитывает конструкции наших построек и проверяет статьи сайта.</p></div></div>
<section class="article">{text}</section></div>
{lead_form()}
</main>
{footer()}"""
    write(path, body)


# ---------- служебные страницы, как у конкурентов из топа (разбор карт сайтов 25.10.2026) ----------

def info_page(path, title, desc, h1, lead, html, faq=None, extra_schema=()):
    """Страница с первым экраном, текстом, FAQ и формой заявки."""
    trail = [("Главная", "/"), (h1, path)]
    schema = [crumbs_ld(trail), *extra_schema] + ([faq_ld(faq)] if faq else [])
    body = f"""{head(fit_title(title), desc, path, True, schema)}{header()}
<main id="main"><div class="page">{crumbs(trail)}
<div class="intro"><div class="intro__text"><h1>{e(h1)}</h1><p class="intro__lead">{lead}</p>
<p class="intro__cta"><a class="btn btn--frame" href="#zayavka">Оставить заявку</a> {quiz_button()}</p></div></div>
<section class="article">{html}</section>
{faq_block(faq) if faq else ""}
</div>
{lead_form()}
</main>
{footer()}"""
    write(path, body)


DELIVERY_PATH, WARRANTY_PATH, FAQ_PATH, MAP_PATH = "/dostavka-i-oplata/", "/garantiya/", "/voprosy-i-otvety/", "/karta-sayta/"


def delivery_page():
    ul = lambda xs: "<ul>" + "".join(f"<li>{e(x)}</li>" for x in xs) + "</ul>"
    html = f"""<h2>Доставка и монтаж</h2>
<p><b>Доставка и монтаж в Екатеринбурге входят в стоимость</b> постройки. В пригороды и по Свердловской области доставку считаем в смете: цена зависит от расстояния и подъезда к участку.
Работаем в городах: {e(", ".join(AREA))}.</p>
{ul(DELIVERY)}
<p>Беседки, террасы, навесы и каркасные дома собираем на вашем участке из деталей, подготовленных на нашем производстве. Готовые бани, бытовки и хозблоки привозим целиком и ставим на подготовленное основание — для этого нужен подъезд для манипулятора.</p>
<h2>Оплата</h2>
{ul(PAYMENT)}
<p>Оплатить можно по безналичному расчёту на счёт ИП по договору. Порядок и этапы оплаты фиксируем до начала работ, без доплат «по ходу».</p>
<h2>Возврат</h2>
<p>Постройку делаем по индивидуальному заказу под ваш участок, поэтому возврат готовой постройки не предусмотрен. Если найдёте недостатки, устраним их бесплатно по <a href="{WARRANTY_PATH}">гарантии {e(COMPANY["warranty"])}</a>.</p>
<h2>Сколько стоит</h2>
<p>Примерную стоимость можно узнать за минуту в <a href="{CALC_PATH}">калькуляторе</a>, цены «от» по размерам — в разделах <a href="/besedki/">беседки</a>, <a href="/bani/">бани</a> и <a href="/verandy/">веранды</a>. Точную смету считаем после замера.</p>"""
    faq = [("Сколько стоит доставка за город?", "Доставку в пригороды и область считаем в смете отдельной строкой. Цена зависит от расстояния от Екатеринбурга и подъезда к участку, точную сумму назовём до подписания договора."),
           ("Нужна ли предоплата?", "Порядок оплаты прописываем в договоре и привязываем к этапам работ. Условия обсуждаем при подписании, без скрытых доплат."),
           ("Что нужно подготовить на участке?", "Свободную площадку под постройку и подъезд для машины с материалами. Если участок с уклоном или сложным грунтом, решение по фундаменту предложим на замере."),
           ("Кто убирает мусор после монтажа?", "Бригада убирает за собой строительный мусор и обрезки. Участок после сдачи остаётся чистым.")]
    info_page(DELIVERY_PATH, "Доставка и оплата деревянных построек в Екатеринбурге",
              "Доставка и монтаж бань, беседок и хозблоков в Екатеринбурге входят в цену, в пригороды — по смете. Оплата по договору этапами, возврат и гарантия 3 года.",
              "Доставка и оплата", "Доставка и монтаж по Екатеринбургу — в цене постройки, в пригороды и область — по смете. Оплата по договору, этапами.", html, faq)


def warranty_page():
    html = f"""<h2>Гарантия {e(COMPANY["warranty"])} по договору</h2>
<p>На каждую постройку даём <b>гарантию {e(COMPANY["warranty"])}</b>. Срок и условия прописываем в договоре, который заключаем с ИП до начала работ, — гарантия действует с даты подписания акта сдачи.</p>
<h2>Что входит в гарантию</h2>
<ul>
<li>Несущая конструкция — каркас, стропила, лаги и обвязка: прогибы, трещины в узлах, перекосы.</li>
<li>Кровля — протечки из-за монтажа кровли и примыканий.</li>
<li>Фундамент на винтовых сваях — просадка и перекос свай, установленных нами.</li>
<li>Двери и окна, которые устанавливали мы, — перекосы и неплотное закрывание из-за монтажа.</li>
</ul>
<p>Недостатки устраняем бесплатно: приезжаем, смотрим, согласуем срок и чиним.</p>
<h2>Что не входит</h2>
<ul>
<li>Естественные свойства дерева: небольшие усадочные трещины, изменение цвета на солнце, смолистость.</li>
<li>Повреждения из-за неправильной эксплуатации, перестройки своими силами или стихийных бедствий.</li>
<li>Обновление покрытия: защитный состав дерево требует раз в несколько лет — <a href="/stati/">в статьях</a> рассказываем, как ухаживать за постройкой.</li>
</ul>
<h2>Как обратиться по гарантии</h2>
<ol>
<li>Напишите нам в MAX или оставьте заявку на сайте, приложите фото проблемы.</li>
<li>Согласуем выезд мастера и посмотрим постройку на месте.</li>
<li>Устраним недостаток бесплатно в согласованный срок.</li>
</ol>
<p>Чтобы постройка служила дольше, проектный отдел рассчитывает её под снег и ветер Урала, а дерево мы заранее обрабатываем огне- и биозащитой. Подробнее о том, как работаем, — на странице «<a href="/o-kompanii/">О компании</a>», условия оплаты — в разделе «<a href="{DELIVERY_PATH}">Доставка и оплата</a>».</p>"""
    faq = [("С какого момента действует гарантия?", "С даты подписания акта сдачи постройки. Срок — 3 года, он прописан в договоре."),
           ("Сколько ждать ремонта по гарантии?", "После обращения согласуем выезд и посмотрим постройку на месте. Срок устранения зависит от недостатка и согласуется с вами."),
           ("Сохранится ли гарантия, если я перекрашу постройку?", "Да, покраска и обновление защитного покрытия гарантию не отменяют. Не сохраняется гарантия на узлы, которые перестраивали без нас."),
           ("Есть ли гарантия на постройки за городом?", "Да, гарантия одинаковая в Екатеринбурге, пригородах и области. Выезд мастера по гарантии бесплатный.")]
    info_page(WARRANTY_PATH, "Гарантия 3 года на деревянные постройки «Магазин Урал»",
              "Гарантия 3 года на бани, беседки, навесы и хозблоки по договору: что входит, что не входит и как обратиться. Недостатки устраняем бесплатно, выезд за наш счёт.",
              "Гарантия на постройки", f"Гарантия {e(COMPANY['warranty'])} на каждую постройку — по договору. Рассказываем, что входит в гарантию и как обратиться.", html, faq)


GENERAL_FAQ = [
    ("Заказ и договор", [
        ("Как заказать постройку?", "Оставьте заявку на сайте, напишите в MAX или посчитайте цену в калькуляторе. Мы перезвоним, уточним задачу, при необходимости приедем на замер и подготовим смету и 3D-проект."),
        ("Заключаете ли вы договор?", "Да, работаем только по официальному договору с ИП. В нём прописываем материалы, сроки, порядок оплаты и гарантию, к договору прикладываем смету и проект."),
        ("Можно построить по своему эскизу?", "Можно. Проектный отдел доработает эскиз, рассчитает конструкцию под нагрузки Урала и сделает 3D-проект, который вы согласуете до начала работ."),
    ]),
    ("Цены и сроки", [
        ("Сколько стоит беседка или баня?", "Цены «от» указаны в разделах и в калькуляторе, они средние по рынку Екатеринбурга. Точную стоимость называем после замера: она зависит от размера, материалов, отделки и участка."),
        ("Почему цена в калькуляторе примерная?", "Калькулятор считает базовую комплектацию по средним ценам рынка. Грунт, подъезд к участку и выбранные материалы могут изменить смету, поэтому точную цену называем после замера."),
        ("Сколько времени занимает строительство?", "Навес и терраса — от 5–7 дней, беседка — от 7–14 дней, баня — от 14 дней, каркасный дом — от 60 дней. Точные сроки фиксируем в договоре."),
    ]),
    ("Доставка, монтаж и участок", [
        ("Работаете ли вы за городом?", "Да, строим в Екатеринбурге, пригородах и по Свердловской области. Доставка и монтаж по Екатеринбургу входят в цену, в пригороды и область — по смете."),
        ("Нужен ли фундамент?", "Под большинство построек ставим винтовые сваи — они подходят для уральских грунтов и монтируются за день. Если грунт сложный, предложим другой фундамент на замере."),
        ("Нужно ли разрешение на постройку?", "На беседку, баню или хозблок на своём участке разрешение обычно не нужно, но важно соблюсти расстояния до забора и соседних построек. Их мы собрали в справочнике «Где поставить постройку»."),
    ]),
    ("Гарантия и уход", [
        ("Какая гарантия?", "Гарантия 3 года, она прописана в договоре. Недостатки по гарантии устраняем бесплатно, выезд мастера — за наш счёт."),
        ("Как ухаживать за деревянной постройкой?", "Раз в несколько лет обновлять защитное покрытие, весной и осенью осматривать кровлю и водостоки. Зимой — счищать с крыши большой снег, особенно после оттепели."),
        ("Обрабатываете ли вы дерево?", "Да, детали обрабатываем на своём производстве: огне- и биозащита, пропитка и покраска в выбранный цвет. Так дерево дольше не темнеет и не гниёт."),
    ]),
]


def faq_page():
    flat = [qa for _, items in GENERAL_FAQ for qa in items]
    html = "".join(f'<h2>{e(g)}</h2>' + "".join(f'<h3>{e(q)}</h3><p>{inline(a)}</p>' for q, a in items) for g, items in GENERAL_FAQ)
    html += (f'<h2>Не нашли ответ?</h2><p>Посмотрите <a href="{DELIVERY_PATH}">доставку и оплату</a>, условия <a href="{WARRANTY_PATH}">гарантии</a>, '
             f'нормы в справочнике «<a href="/gde-postavit-postroyku/">Где поставить постройку</a>» и советы инженера в <a href="/stati/">статьях</a>. '
             f'Или задайте вопрос в заявке — ответим и подскажем.</p>')
    info_page(FAQ_PATH, "Вопросы и ответы о строительстве бань, беседок и навесов",
              "Частые вопросы о строительстве бань, беседок, навесов и хозблоков в Екатеринбурге: договор, цены и сроки, доставка, фундамент, разрешения, гарантия и уход.",
              "Вопросы и ответы", "Собрали частые вопросы о заказе, ценах, сроках, доставке и гарантии на деревянные постройки.", html,
              extra_schema=[faq_ld(flat)])


def sitemap_page(indexable):
    """HTML-карта сайта: все страницы в индексе, сгруппированные по разделам."""
    titles = {}
    for s in SECTIONS:
        titles[s["url"]] = s["name"]
        for sub in s["subs"]:
            titles[sub["url"]] = sub["name"]
    for a in ARTICLES:
        titles[a["url"]] = a["h1"]
    for u, (k, c) in GEO.items():
        titles[u] = f'{BY_KEY[k]["name"]} — {c}'
    blocks = []
    service = [("/", "Главная"), (CALC_PATH, "Калькулятор стоимости"), (WORKS_PATH, "Наши работы"), (PROJECTS_PATH, "Проекты"),
               ("/o-kompanii/", "О компании"), (DELIVERY_PATH, "Доставка и оплата"), (WARRANTY_PATH, "Гарантия"), (FAQ_PATH, "Вопросы и ответы"),
               ("/gde-postavit-postroyku/", "Где поставить постройку"), ("/stati/", "Статьи")] + ([(CONTACTS_PATH, "Контакты")] if has_contacts() else [])
    blocks.append("<h2>Компания</h2><ul>" + "".join(f'<li><a href="{u}">{e(t)}</a></li>' for u, t in service) + "</ul>")
    for s in SECTIONS:
        links = [(u, titles[u]) for u in [s["url"]] + [x["url"] for x in s["subs"]] + [u for u, (k, _) in GEO.items() if k == s["key"]] if u in indexable]
        if links:
            blocks.append(f'<h2>{e(s["name"])}</h2><ul>' + "".join(f'<li><a href="{u}">{e(t)}</a></li>' for u, t in links) + "</ul>")
    blocks.append("<h2>Статьи</h2><ul>" + "".join(f'<li><a href="{a["url"]}">{e(a["h1"])}</a></li>' for a in ARTICLES) + "</ul>")
    simple_page(MAP_PATH, "Карта сайта «Магазин Урал»: разделы, услуги и статьи", "Карта сайта", "".join(blocks), index=True, form=False,
                desc="Карта сайта «Магазин Урал»: все разделы каталога деревянных построек, услуги, гео-страницы по пригородам Екатеринбурга и статьи о строительстве из дерева.")


def policy_page():
    ip = SITE.get("ip")
    if ip and ip.get("name") and ip.get("inn") and SITE.get("phone"):
        text = POLICY.format(domain=SITE["domain"], name=ip["name"], inn=ip["inn"], ogrnip=f", ОГРНИП {ip['ogrnip']}" if ip.get("ogrnip") else "",
                             address=f", адрес: {ip['address']}" if ip.get("address") else "", phone=SITE["phone"],
                             email=f" или по почте {SITE['email']}" if SITE.get("email") else "")
        simple_page("/politika-konfidencialnosti/", "Политика обработки персональных данных", "Политика конфиденциальности",
                    md(text), index=True, form=False,
                    desc=f"Политика обработки персональных данных сайта {SITE['domain']}: какие данные собираем по заявкам, зачем, как храним и как отозвать своё согласие по закону 152-ФЗ.")
        return True
    else:
        simple_page("/politika-konfidencialnosti/", "Политика конфиденциальности", "Политика конфиденциальности",
                    "<p>Политика обработки персональных данных будет опубликована здесь до запуска приёма заявок, вместе с реквизитами оператора.</p>",
                    index=False, form=False)
        return False


def not_found():
    body = f"""{head(f"Страница не найдена | {SITE['name']}", "Страница не найдена", "/404.html", False)}{header("/#zayavka")}
<main id="main"><div class="page"><div class="intro"><h1>Такой страницы нет</h1>
<p class="intro__lead">Возможно, она переехала. Выберите постройку в каталоге.</p>
<p><a class="btn btn--frame" href="/#razdely">Все постройки</a></p></div></div></main>
{footer()}"""
    (ROOT / "404.html").write_text(body, encoding="utf-8")


def main():
    indexable = ["/"]
    home_page()
    for s in SECTIONS:
        p, ok = section_page(s)
        if ok:
            indexable.append(p)
        for sub in s["subs"]:
            p, ok = section_page(s, sub)
            if ok:
                indexable.append(p)
    for url, (key, city) in GEO.items():
        p, ok = section_page(BY_KEY[key], {"name": f'{BY_KEY[key]["name"]} — {city}', "url": url}, city)
        if ok:
            indexable.append(p)
    for item in LISTINGS:
        if item.get("photos"):
            object_page(item)
            indexable.append(object_url(item))
    if works_page():
        indexable.append(WORKS_PATH)
    if projects_page():
        indexable.append(PROJECTS_PATH)
    if has_contacts():
        contacts_page()
        indexable.append(CONTACTS_PATH)
    norms_page()
    indexable.append(NORMS_PATH)
    calc_data_js()
    calc_page()
    indexable.append(CALC_PATH)
    delivery_page(); warranty_page(); faq_page()
    indexable += [DELIVERY_PATH, WARRANTY_PATH, FAQ_PATH]
    if ARTICLES:
        articles_hub()
        indexable.append("/stati/")
        for a in ARTICLES:
            article_page(a)
            indexable.append(a["url"])
    about_page()
    indexable.append("/o-kompanii/")
    if SITE.get("author"):
        author_page()
        indexable.append(SITE["author"]["url"])
    if policy_page():
        indexable.append("/politika-konfidencialnosti/")
    not_found()
    sitemap_page(set(indexable))
    indexable.append(MAP_PATH)
    urls = "".join(f"<url><loc>{SITE['base_url']}{p}</loc></url>" for p in indexable)
    (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (ROOT / "CNAME").write_text(SITE["domain"] + "\n", encoding="utf-8")  # свой домен для GitHub Pages
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")  # отдавать файлы как есть, без Jekyll
    (ROOT / "robots.txt").write_text(f"User-agent: *\nDisallow: /_build/\nDisallow: /docs/\nDisallow: /workers/\nSitemap: {SITE['base_url']}/sitemap.xml\n", encoding="utf-8")
    total = 1 + len(SECTIONS) + sum(len(s["subs"]) for s in SECTIONS) + 4 + (len(ARTICLES) + 1 if ARTICLES else 0) + len(GEO) + sum(1 for x in LISTINGS if x.get("photos")) + 5 + bool(SITE.get("author")) + has_contacts() + any(x.get("photos") for x in LISTINGS) + any(is_project(x) for x in LISTINGS)
    print(f"страниц: {total}, в индексе: {len(indexable)}")


if __name__ == "__main__":
    main()
