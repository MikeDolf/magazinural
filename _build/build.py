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

ROOT = Path(__file__).resolve().parent.parent
VER = "31"  # меняйте при правке css/js

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
    return org


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


# ---------- каркас страницы ----------

def head(title, desc, path, index, schema=(), og_type="website", og_img=None):
    robots = "" if index else '<meta name="robots" content="noindex, follow">\n'
    url = f"{SITE['base_url']}{path}"
    img = SITE["base_url"] + (og_img or "/assets/img/og.png")
    blocks = "".join(ld(x) for x in (org_ld(), *schema))
    return f"""<!doctype html>
<html lang="ru"{f' data-ym="{SITE["metrika"]}"' if SITE.get("metrika") else ""}>
<head>
<meta charset="utf-8">
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
<body>{metrika_noscript()}
<a class="skip" href="#main">К содержанию</a>
"""


def header(cta="#zayavka"):
    """cta — куда ведёт кнопка заявки: на форму этой страницы или, если формы нет, на форму главной."""
    links = "".join(f'<li><a href="{BY_KEY[k]["url"]}">{e(BY_KEY[k]["name"])}</a></li>' for k in HEADER_SECTIONS if k in BY_KEY)
    return f"""<header class="top">
  <div class="top__in">
    <a class="logo" href="/">{LOGO}<span class="logo__text"><b>{e(SITE['name'])}</b><small>{e(SITE['tagline'])}</small></span></a>
    <details class="nav">
      <summary class="nav__toggle" aria-label="Разделы">{icon('menu')}<span class="nav__label">Разделы</span></summary>
      <nav aria-label="Разделы каталога"><ul>{links}<li><a href="/#razdely">Все постройки</a></li></ul></nav>
    </details>
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
                + '<li><a href="/nashi-raboty/">Наши работы</a></li><li><a href="/stati/">Статьи</a></li><li><a href="/gde-postavit-postroyku/">Где поставить постройку</a></li><li><a href="/o-kompanii/">О компании</a></li><li><a href="/politika-konfidencialnosti/">Политика конфиденциальности</a></li></ul>')
    return f"""<footer class="foot">
  <div class="foot__in">
    <div class="foot__brand"><a class="logo logo--foot" href="/">{LOGO}<span class="logo__text"><b>{e(SITE['name'])}</b><small>{e(SITE['region'])}</small></span></a>
      <p>Строим бани, беседки, навесы, террасы и другие деревянные постройки для участка в Екатеринбурге и области.</p></div>
    <div class="foot__cols">{''.join(cols)}</div>
    {contacts_block()}
  </div>
</footer>
{callback_dialog()}
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


def howto_block():
    """«Как оплатить» и «Как получить» — тексты из data/site.py."""
    def card(h, items):
        return f'<div class="howto__card"><h2>{e(h)}</h2><ul>' + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul></div>"
    return f'<section class="howto" aria-label="Оплата и порядок работ">{card("Как оплатить", PAYMENT)}{card("Как получить постройку", DELIVERY)}</section>'


def object_url(item):
    return f'{BY_KEY[item["section"]]["url"]}obekt-{item["id"]}/'


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
        title = item["title"]
        action = f'<a class="btn btn--frame" href="#zayavka" data-object="{e(item["title"])}">Хочу такую же</a>'
        if item.get("photos"):
            action = f'<a class="btn btn--ghost" href="{object_url(item)}">Фото и паспорт объекта</a>' + action
    return f"""<article class="passport{' passport--sample' if sample else ''}">
  <header class="passport__bar"><span>Паспорт объекта</span><span class="passport__num">{num}</span></header>
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
            f'<p class="sizes__note">{note}</p><ul class="sizes__list">{cards}</ul></section>')


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
        grid = '<div class="grid">' + "".join(passport(i) for i in items) + "</div>"
        count = f'<h2 class="board__h">Наши объекты</h2><p class="board__count">На стенде {len(items)} объект(ов)</p>'
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
    updated_html = f'<p class="updated">Текст обновлён <time datetime="{upd}">{ru_date(upd)}</time></p>' if upd and text else ""
    body = f"""{head(title, desc, path, index, schema)}{header()}
<main id="main">
  <div class="page">
    {crumbs(trail)}
    <div class="intro">
      <h1>{e(h1)}</h1>
      <p class="intro__lead">{e(lead)}</p>
      <p class="intro__cta"><a class="btn btn--frame" href="#zayavka">Оставить заявку</a> <button class="btn btn--ghost" type="button" data-callback aria-haspopup="dialog">Перезвоните мне</button></p>
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
        home_text += f'<p class="updated">Текст обновлён <time datetime="{upd}">{ru_date(upd)}</time></p>'
    home_text += faq_block(faq)
    schema = [faq_ld(faq)] if faq else []
    body = f"""{head(fit_title(title) if seo else title, desc, "/", True, schema)}{header()}
<main id="main">
  <div class="page">
    <div class="intro intro--home">
      <h1>{e(seo[0]) if seo else "Деревянные постройки под ключ в Екатеринбурге"}</h1>
      <p class="intro__lead">{home_lead}</p>
      <p><a class="btn btn--frame" href="#zayavka">Рассчитать смету</a> <a class="btn btn--ghost" href="#razdely">Что строим</a></p>
    </div>
    {advantages_block()}
    {steps_block()}
    {('<section class="related related--cards" aria-labelledby="hw-h"><h2 id="hw-h">Наши работы</h2><ul class="ocards">' + "".join(obj_card(x) for x in [x for x in LISTINGS if x.get("photos")][:8]) + f'</ul><p class="cta-line">Все объекты с фото и паспортом — на странице «<a href="{WORKS_PATH}">Наши работы</a>».</p></section>') if any(x.get("photos") for x in LISTINGS) else ""}
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
    by = e(author["name"]) if author else f"Редакция «{e(SITE['name'])}»"
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
              "author": {"@type": "Person", "name": author["name"]} if author else {"@id": ORG_ID},
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
      <p class="byline">{by} · {dates}</p>
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
    return f'{x["kw"]} {q.group(0)}' if x.get("kw") and q else x["title"]


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
    gallery = "".join(
        f'<img src="/{e(ph)}" alt="{e(full)} — {"общий вид" if n == 0 else f"фото {n + 1}"}" width="{img_size(ph)[0]}" height="{img_size(ph)[1]}" '
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
    same = [x for x in LISTINGS if x["section"] == key and x is not item and x.get("photos")]
    sub_set = set(item.get("subs", []))
    same.sort(key=lambda x: -len(sub_set & set(x.get("subs", []))))
    others = same[:3]
    subs = [s for s in section["subs"] if s["url"] in sub_set]
    trail = [("Главная", "/"), (section["name"], section["url"])] + ([(subs[0]["name"], subs[0]["url"])] if subs else []) + [(full, path)]
    prod = {"@context": "https://schema.org", "@type": "Product", "name": full, "sku": item["id"],
            "image": [SITE["base_url"] + "/" + ph for ph in photos], "brand": {"@id": ORG_ID},
            "category": section["name"], "description": re.sub(r"\s+", " ", item.get("description") or item["title"])[:300]}
    if price:
        prod["offers"] = {"@type": "Offer", "priceCurrency": "RUB", "price": price, "url": SITE["base_url"] + path,
                          "seller": {"@id": ORG_ID}, "availability": "https://schema.org/InStock"}
    title = fit_title(fit_len(full, [f', {item["place"]}' if item.get("place") else " в Екатеринбурге", " — фото и паспорт", " — фото объекта", ", фото", " — наш объект"] + ([", цена «от»"] if item.get("price_from") else []), 50, 60))
    facts = ", ".join(x for x in (item.get("size"), item.get("material"), item.get("place"), item.get("built") and f'сдан {item["built"]}') if x)
    lead_txt = item.get("lead") or ""
    desc = fit_len(f'{full}' + (f" — {lead_txt}" if lead_txt else (f': {facts}.' if facts else ".")),
                   [" Фото и паспорт объекта" + (" с ценой «от»." if item.get("price_from") else "."), " Построим такую же по вашим размерам.", " Ответим на вопросы о замере и сроках.", " Оставьте заявку — перезвоним.", " Гарантия 3 года.", " Работаем по договору.", " Екатеринбург.", " Под ключ.", " 3D-проект.", " Замер."], 150, 160)
    name_l = section["name"].lower()
    art = next((a for a in ARTICLES if a["slug"] == OT.ARTICLE.get(key)), None)
    sub_links = ", ".join(f'[{s["name"].lower()}]({s["url"]})' for s in subs)
    text = f"""{item.get("description", "")}

## Что входит в работы

Строим «{item["title"].split("«")[-1].rstrip("»")}» и похожие постройки под ключ — от замера до уборки участка:

""" + "\n".join(f"- {x}" for x in OT.WORKS.get(key, [])) + f"""

## Сколько стоит такая постройка

""" + (f"Постройка такого типа у нас — от {rub(price)} за базовую комплектацию. " if price else "") + f"""{OT.PRICE.get(key, "Цену считаем по вашим размерам и материалам.")} Смету по позициям присылаем после замера, итог фиксируем в договоре, гарантия — {COMPANY["warranty"]}.
""" + (f"\nКак выбрать размер и что учесть заранее — в статье [«{art['h1']}»]({art['url']}).\n" if art else "") + f"""
## Как ухаживать за постройкой

Дерево служит долго, если за ним следить. Несколько простых правил:

""" + "\n".join(f"- {x}" for x in OT.CARE.get(key, [])) + f"""

## Как построить такую же

Оставьте заявку и напишите, что понравилось в этом объекте. Перезвоним, уточним размеры и участок, приедем на замер, подготовим 3D-проект и смету. Можно повторить постройку один в один или изменить размер, крышу и отделку.
""" + (f"\nПохожие постройки собраны в разделах: {sub_links}. " if sub_links else "\n") + f"Все {name_l} — в каталоге «[{section['name']}]({section['url']})»."
    body = f"""{head(title, desc[:160], path, True, [crumbs_ld(trail), prod], "website", "/" + photos[0])}{header()}
<main id="main">
  <div class="page">
    {crumbs(trail)}
    <div class="intro"><h1>{e(full)}</h1><p class="intro__lead">{e(full)} — {e(lead_txt)}</p>{price_html}
      <p class="intro__cta"><a class="btn btn--frame" href="#zayavka" data-object="{e(item["title"])}">Хочу такую же</a> <button class="btn btn--ghost" type="button" data-callback aria-haspopup="dialog">Перезвоните мне</button></p></div>
    <div class="obj">
      <div class="obj__gallery">{gallery}</div>
      <article class="passport obj__passport"><header class="passport__bar"><span>Паспорт объекта</span><span class="passport__num">№ {e(item["id"])}</span></header>
        <div class="passport__body"><table class="passport__table"><tbody>{''.join(rows)}</tbody></table>
        <p class="passport__note">{f'Цена от <b>{rub(price)}</b> — точную смету считаем после замера' if price else 'Цену рассчитаем по вашим размерам'}</p><a class="btn btn--frame" href="#zayavka" data-object="{e(item["title"])}">Рассчитать такую же</a></div></article>
    </div>
    <section class="article obj__text">{md(text)}</section>
    {howto_block()}
    {('<section class="related related--cards" aria-labelledby="oth-h"><h2 id="oth-h">Похожие объекты</h2><ul class="ocards">' + "".join(obj_card(x) for x in others) + "</ul></section>") if others else ""}
    <p class="cta-line">Все наши объекты с фото — на странице «<a href="{WORKS_PATH}">Наши работы</a>».</p>
  </div>
  {lead_form(key)}
</main>
{footer()}"""
    write(path, body)


WORKS_PATH = "/nashi-raboty/"


def works_page():
    """«Наши работы»: все объекты с фото по разделам."""
    items = [x for x in LISTINGS if x.get("photos")]
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


def about_page():
    """О компании: факты со слов владельца (site.COMPANY, ADVANTAGES, STEPS) — без превосходных степеней."""
    path = "/o-kompanii/"
    area = ", ".join(AREA)
    text = md(f"""
«{SITE['name']}» проектирует и строит деревянные постройки для загородного участка с {COMPANY['since']} года: беседки, террасы и веранды, навесы, хозблоки, каркасные дома и бани, зимние деревянные горки, песочницы и детские домики. Работаем в Екатеринбурге и пригородах.

## Кто работает над вашей постройкой

- **Проектный отдел** превращает идею в 3D-проект и рабочие чертежи, считает конструкцию и материалы.
- **Отдел продаж** помогает выбрать постройку, размер и материалы под участок и бюджет.
- **Своё производство** заготавливает и обрабатывает дерево, изготавливает детали по проекту.
- **Монтажные бригады** со стажем {COMPANY['crews']} собирают постройку на вашем участке.

## Наши условия

- Официальный договор с ИП и смета по позициям — видно, за что вы платите.
- Гарантия на постройку — {COMPANY['warranty']}, она прописана в договоре.
- Предварительный расчёт по заявке на сайте и каталог построек онлайн.

## Что строим

- [Бани](/bani/) — каркасные, из бруса и бревна, бочки и модульные.
- [Беседки](/besedki/) — открытые, закрытые, с мангалом и печью.
- [Навесы и карпорты](/navesy/), [террасы](/terrasy/) и [веранды](/verandy/).
- [Хозблоки](/hozbloki/), [сараи](/sarai/), [дровники](/drovniki/).
- [Каркасные дома](/karkasnye-doma/), [горки](/gorki/), [песочницы](/pesochnicy/) и [детские домики](/detskie-domiki/).

## Где работаем

{area}. Если вашего посёлка нет в списке — напишите в заявке, обсудим выезд.

## Перед стройкой

Проверьте, где постройка встанет по нормам: расстояния до забора, дома и колодца собраны в справочнике [«Где поставить постройку»](/gde-postavit-postroyku/).
""") + steps_block("about-steps-h")
    simple_page(path, f"О компании «Магазин Урал»: строим из дерева с {COMPANY['since']} года", "О компании", text, index=True,
                desc=f"«Магазин Урал» с {COMPANY['since']} года строит беседки, бани, террасы и хозблоки в Екатеринбурге и области: свой проектный отдел, производство, договор и гарантия 3 года.")

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
    if has_contacts():
        contacts_page()
        indexable.append(CONTACTS_PATH)
    norms_page()
    indexable.append(NORMS_PATH)
    if ARTICLES:
        articles_hub()
        indexable.append("/stati/")
        for a in ARTICLES:
            article_page(a)
            indexable.append(a["url"])
    about_page()
    indexable.append("/o-kompanii/")
    if policy_page():
        indexable.append("/politika-konfidencialnosti/")
    not_found()
    urls = "".join(f"<url><loc>{SITE['base_url']}{p}</loc></url>" for p in indexable)
    (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (ROOT / "CNAME").write_text(SITE["domain"] + "\n", encoding="utf-8")  # свой домен для GitHub Pages
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")  # отдавать файлы как есть, без Jekyll
    (ROOT / "robots.txt").write_text(f"User-agent: *\nDisallow: /_build/\nDisallow: /docs/\nDisallow: /workers/\nSitemap: {SITE['base_url']}/sitemap.xml\n", encoding="utf-8")
    total = 1 + len(SECTIONS) + sum(len(s["subs"]) for s in SECTIONS) + 4 + (len(ARTICLES) + 1 if ARTICLES else 0) + len(GEO) + sum(1 for x in LISTINGS if x.get("photos")) + has_contacts() + any(x.get("photos") for x in LISTINGS)
    print(f"страниц: {total}, в индексе: {len(indexable)}")


if __name__ == "__main__":
    main()
