#!/usr/bin/env python3
"""Сборка статических страниц magazinural.ru.

    python3 _build/build.py

Шапка, подвал, форма заявки и SEO-обвязка одинаковы на всех страницах, поэтому
лежат здесь, а страницы — производные от данных в _build/data/.

Что скрипт делает намеренно:
  * страница без объявлений и без собственного текста собирается с noindex
    и не попадает в sitemap: пустой каталог не отдаём поиску;
  * не выдумывает объявления: пока подрядчики не переданы, вместо сетки —
    пустое состояние с образцом паспорта (поля без значений);
  * не размечает цены через schema.org/Offer, пока цены не реальные.
"""

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data.site import SITE, HEADER_SECTIONS, WHEN_OPTIONS
from data.sections import SECTIONS
from data.listings import LISTINGS, CONTRACTORS
from data.texts import TEXTS, LEADS
from data.seo import SEO

ROOT = Path(__file__).resolve().parent.parent
VER = "6"  # меняйте при правке css/js

BY_KEY = {s["key"]: s for s in SECTIONS}
CONTRACTOR = {c["id"]: c for c in CONTRACTORS}


def e(t):
    return html.escape(str(t), quote=True)


NO_TURNKEY = {"services", "maf", "garden", "nastil", "fence"}


def cap(t):
    return t[:1].upper() + t[1:]


def rub(n):
    return f"{n:,}".replace(",", " ") + " ₽"


def md(text):
    """Мини-разметка текстов разделов: ## заголовок, - список, абзацы."""
    out, items = [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>")
            items.clear()

    for block in text.strip().split("\n\n"):
        block = block.strip()
        lines = block.split("\n")
        if all(l.startswith("- ") for l in lines):
            items.extend(e(l[2:]) for l in lines)
            continue
        flush()
        if block.startswith("## "):
            out.append(f"<h2>{e(block[3:])}</h2>")
        else:
            out.append(f"<p>{e(' '.join(lines))}</p>")
    flush()
    return "\n".join(out)


# ---------- иконки (одна толщина линии, 24×24) ----------

def icon(name):
    paths = {
        "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
        "photo": '<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="16" cy="9" r="1.6"/>',
    }
    return (f'<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>')


# Знак: табличка паспорта под двускатной кровлей.
LOGO = ('<svg class="logo__mark" viewBox="0 0 32 32" aria-hidden="true">'
        '<path d="M3 14 16 4l13 10" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linejoin="round"/>'
        '<rect x="7" y="15" width="18" height="13" rx="1.5" fill="currentColor"/>'
        '<path d="M10 19.5h12M10 23.5h8" stroke="var(--frame)" stroke-width="2"/></svg>')


# ---------- каркас страницы ----------

def head(title, desc, path, index):
    robots = "" if index else '<meta name="robots" content="noindex, follow">\n'
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{robots}<link rel="canonical" href="{SITE['base_url']}{path}">
<link rel="preload" href="/assets/fonts/golos-cyrillic.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/site.css?v={VER}">
<meta name="theme-color" content="#1c3a8e">
</head>
<body>
<a class="skip" href="#main">К содержанию</a>
"""


def header():
    links = "".join(f'<li><a href="{BY_KEY[k]["url"]}">{e(BY_KEY[k]["name"])}</a></li>' for k in HEADER_SECTIONS if k in BY_KEY)
    return f"""<header class="top">
  <div class="top__in">
    <a class="logo" href="/">{LOGO}<span class="logo__text"><b>{e(SITE['name'])}</b><small>{e(SITE['tagline'])}</small></span></a>
    <details class="nav">
      <summary class="nav__toggle" aria-label="Разделы">{icon('menu')}<span class="nav__label">Разделы</span></summary>
      <nav aria-label="Разделы каталога"><ul>{links}<li><a href="/#razdely">Все постройки</a></li></ul></nav>
    </details>
    <a class="btn btn--enamel top__cta" href="#zayavka"><span class="top__cta-long">Оставить заявку</span><span class="top__cta-short">Заявка</span></a>
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
                + '<li><a href="/podryadchikam/">Подрядчикам</a></li><li><a href="/politika-konfidencialnosti/">Политика конфиденциальности</a></li></ul>')
    return f"""<footer class="foot">
  <div class="foot__in">
    <div class="foot__brand"><a class="logo logo--foot" href="/">{LOGO}<span class="logo__text"><b>{e(SITE['name'])}</b><small>{e(SITE['region'])}</small></span></a>
      <p>Площадка подрядчиков: сданные объекты, параметры и условия мастеров в одном месте.</p></div>
    <div class="foot__cols">{''.join(cols)}</div>
  </div>
</footer>
<script src="/assets/js/site.js?v={VER}" defer></script>
</body>
</html>
"""


def crumbs(items):
    li = []
    for i, (name, url) in enumerate(items):
        last = i == len(items) - 1
        li.append(f'<li><span aria-current="page">{e(name)}</span></li>' if last else f'<li><a href="{url}">{e(name)}</a></li>')
    return f'<nav class="crumbs" aria-label="Навигация"><ol>{"".join(li)}</ol></nav>'


# ---------- паспорт объекта ----------

PASSPORT_ROWS = [
    ("Подрядчик", "contractor"), ("Сдан", "built"), ("Где", "place"), ("Размер", "size"),
    ("Материал", "material"), ("Крыша", "roof"), ("Фундамент", "foundation"), ("Срок работ", "duration"),
    ("Договор", "contract"), ("Гарантия", "warranty"),
]


def passport(item=None):
    sample = item is None
    item = item or {}
    rows = []
    for label, k in PASSPORT_ROWS:
        v = item.get(k)
        c = CONTRACTOR.get(item.get("contractor"), {})
        if k == "contractor" and v:
            v = c.get("name", v)
        if k in ("contract", "warranty"):
            v = c.get(k)
            if k == "contract" and v is not None:
                v = "да" if v else "нет"
        rows.append(f'<tr><th scope="row">{label}</th><td>{e(v) if v else "<span class=blank></span>"}</td></tr>')
    price = item.get("price_from")
    price_html = (f'<span class="passport__price-label">Цена от</span> <b>{rub(price)}</b>' if price
                  else '<span class="passport__price-label">Цена</span> <span class="passport__ask">по запросу</span>')
    num = f'№ {e(item["id"])}' if not sample else "№ — · образец"
    if sample:
        figure = f'<div class="passport__photo passport__photo--empty">{icon("photo")}<span>Фото сданного объекта</span></div>'
        title = "Название объекта"
        action = '<a class="btn btn--ghost" href="/podryadchikam/">Разместить свой объект</a>'
    else:
        src = item["photos"][0] if item.get("photos") else ""
        figure = f'<img class="passport__photo" src="/{e(src)}" alt="{e(item["title"])}" loading="lazy" width="640" height="420">'
        title = item["title"]
        action = f'<a class="btn btn--frame" href="#zayavka" data-object="{e(item["title"])}">Заявка мастеру</a>'
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
      <h2 id="zayavka-h">Одна заявка — несколько мастеров</h2>
      <p>Опишите, что хотите построить. Мы передадим заявку подрядчикам, которые делают такие постройки в вашем районе, и они свяжутся с вами сами.</p>
      <ul class="ticks">
        <li>{icon('check')}Сравниваете предложения, а не обзваниваете компании</li>
        <li>{icon('check')}Телефон получают только подходящие мастера</li>
      </ul>
    </div>
    <form class="form" novalidate data-form>
      <div class="form__grid">
        <label class="field"><span>Что строим</span><select name="type">{opts}</select></label>
        <label class="field"><span>Размер, если знаете</span><input name="size" placeholder="например, 3×4 м" autocomplete="off"></label>
        <label class="field"><span>Где участок</span><input name="place" placeholder="город, посёлок или СНТ"></label>
        <label class="field"><span>Когда</span><select name="when">{when}</select></label>
        <label class="field field--wide"><span>Что важно</span><textarea name="note" rows="3" placeholder="мангал, остекление, материал, бюджет"></textarea></label>
        <label class="field"><span>Имя</span><input name="name" autocomplete="name"></label>
        <label class="field"><span>Телефон <i aria-hidden="true">*</i></span><input name="phone" type="tel" autocomplete="tel" required placeholder="+7" inputmode="tel" aria-describedby="phone-err"><em class="field__err" id="phone-err" hidden>Укажите телефон, чтобы мастер мог перезвонить</em></label>
      </div>
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


def section_page(section, sub=None):
    path = sub["url"] if sub else section["url"]
    name = sub["name"] if sub else section["name"]
    items = listings_for(section, sub["url"] if sub else None)
    text = TEXTS.get(path)
    index = bool(items) or bool(text)
    h1 = f"{name} под ключ в Екатеринбурге" if not sub and section["key"] not in NO_TURNKEY else f"{name} в Екатеринбурге"
    seo = SEO.get(path)
    if seo:
        h1 = seo[0]
    lead = LEADS.get(path) or (f"Сданные объекты мастеров Екатеринбурга и области: параметры, цена «от» и кто строил. "
                               f"Оставьте одну заявку — её получат подходящие подрядчики.")
    tabs = [("Все", section["url"], len(listings_for(section)))] + [
        (cap(s["name"].replace(section["name"], "").strip(" ,") or s["name"]), s["url"], len(listings_for(section, s["url"])))
        for s in section["subs"]]
    tabs_html = ""
    if section["subs"]:
        tabs_html = '<nav class="tabs" aria-label="Подкатегории"><ul>' + "".join(
            f'<li><a href="{u}"{" aria-current=page" if u == path else ""}>{e(t)} <span class="tabs__n">{n}</span></a></li>'
            for t, u, n in tabs) + "</ul></nav>"
    if items:
        grid = '<div class="grid">' + "".join(passport(i) for i in items) + "</div>"
        count = f'<p class="board__count">На стенде {len(items)} объект(ов)</p>'
    else:
        grid = f"""<div class="empty">
  <div class="empty__text">
    <h2>Стенд пока пуст</h2>
    <p>Мы собираем сданные объекты подрядчиков Екатеринбурга. У каждого объявления будет паспорт: кто строил, когда сдан, размер, материал, крыша, фундамент, договор, гарантия и цена «от».</p>
    <p>Пока объявлений нет, оставьте заявку — подберём мастера вручную.</p>
    <p class="empty__actions"><a class="btn btn--frame" href="#zayavka">Оставить заявку</a> <a class="btn btn--ghost" href="/podryadchikam/">Я подрядчик</a></p>
  </div>
  {passport()}
</div>"""
        count = ""
    others = [s for s in SECTIONS if s["key"] != section["key"] and s["core"]][:8]
    related = '<section class="related" aria-labelledby="rel-h"><h2 id="rel-h">Другие постройки из дерева</h2><ul>' + "".join(
        f'<li><a href="{s["url"]}">{e(s["name"])}{icon("arrow")}</a></li>' for s in others) + "</ul></section>"
    article = f'<section class="article" aria-label="Как выбрать">{md(text)}</section>' if text else ""
    trail = [("Главная", "/"), (section["name"], section["url"])] + ([(name, path)] if sub else [])
    priced = any(i.get("price_from") for i in items)
    if seo:
        title = seo[1].replace("{цены}", ", цены" if priced else "") + f" | {SITE['name']}"
        desc = seo[2]
    else:
        title = f"{h1} — объекты и мастера | {SITE['name']}"
        desc = lead
    body = f"""{head(title, desc, path, index)}{header()}
<main id="main">
  <div class="page">
    {crumbs(trail)}
    <div class="intro">
      <h1>{e(h1)}</h1>
      <p class="intro__lead">{e(lead)}</p>
    </div>
    {tabs_html}
    <section class="board" aria-label="Объявления">{count}{grid}</section>
  </div>
  {lead_form(section['key'])}
  <div class="page">
    {article}
    {related}
  </div>
</main>
{footer()}"""
    write(path, body)
    return path, index


def home_page():
    if LISTINGS:
        home_lead = ("Смотрите сданные объекты разных подрядчиков с паспортом: размер, материал, крыша, сроки, гарантия и цена «от». "
                     "Опишите задачу один раз — заявку получат подходящие мастера.")
        step1 = "и посмотрите паспорта сданных объектов: кто строил, из чего, за сколько."
    else:
        home_lead = ("Собираем сданные объекты подрядчиков Екатеринбурга: у каждого будет паспорт с размером, материалом, сроками, гарантией и ценой «от». "
                     "Пока стенд наполняется, опишите задачу — подберём мастера вручную.")
        step1 = "Скоро здесь будут паспорта сданных объектов: кто строил, из чего, за сколько."
    dirs = []
    for s in SECTIONS:
        subs = "".join(f'<li><a href="{x["url"]}">{e(x["name"])}</a></li>' for x in s["subs"][:4])
        dirs.append(f'<li class="dir__item"><a class="dir__head" href="{s["url"]}">{e(s["name"])}</a>{f"<ul>{subs}</ul>" if subs else ""}</li>')
    core = "".join(d for d, s in zip(dirs, SECTIONS) if s["core"])
    ext = "".join(d for d, s in zip(dirs, SECTIONS) if not s["core"])
    body = f"""{head(f"Деревянные постройки под ключ в Екатеринбурге — мастера и сданные объекты | {SITE['name']}",
                 "Беседки, бани, навесы, террасы, хозблоки и другие деревянные постройки от подрядчиков Екатеринбурга: сданные объекты с параметрами и одна заявка нескольким мастерам.",
                 "/", True)}{header()}
<main id="main">
  <div class="page">
    <div class="intro intro--home">
      <h1>Деревянные постройки для участка — от мастеров Екатеринбурга</h1>
      <p class="intro__lead">{home_lead}</p>
      <p><a class="btn btn--frame" href="#zayavka">Оставить заявку</a> <a class="btn btn--ghost" href="#razdely">Выбрать постройку</a></p>
    </div>
    <section class="how" aria-labelledby="how-h">
      <h2 id="how-h">Как это работает</h2>
      <ol class="how__list">
        <li><b>Выберите тип постройки</b><span>{step1}</span></li>
        <li><b>Оставьте одну заявку</b><span>с размером, местом и пожеланиями — без звонков в десять компаний.</span></li>
        <li><b>Мастера свяжутся сами</b><span>и предложат смету. Сравниваете по фактам и выбираете.</span></li>
      </ol>
    </section>
    <section class="dir" id="razdely" aria-labelledby="dir-h">
      <h2 id="dir-h">Что строим</h2>
      <ul class="dir__list">{core}</ul>
      <h3 class="dir__sub">Дома и большие постройки</h3>
      <ul class="dir__list">{ext}</ul>
    </section>
  </div>
  {lead_form()}
</main>
{footer()}"""
    write("/", body)


def simple_page(path, title, h1, html_body, index=True):
    body = f"""{head(f"{title} | {SITE['name']}", title, path, index)}{header()}
<main id="main"><div class="page">{crumbs([("Главная", "/"), (h1, path)])}
<div class="intro"><h1>{e(h1)}</h1></div>
<section class="article">{html_body}</section></div>
{lead_form() if path == "/podryadchikam/" else ""}
</main>
{footer()}"""
    write(path, body)


def contractors_page():
    simple_page("/podryadchikam/", "Подрядчикам: разместить объекты", "Подрядчикам", md("""
## Как попасть на площадку

Мы размещаем сданные объекты — не рендеры и не чужие фото. Для каждого объекта нужен паспорт: что за постройка, когда сдана, где, размер, материал, крыша, фундамент, срок работ и цена «от».

## Что прислать

- Название бригады или компании и где вы работаете.
- Фото сданных объектов: общий вид и детали, не меньше трёх на объект.
- Параметры по каждому объекту — по списку выше.
- Условия: договор, гарантия, выезд на замер.

## Что вы получаете

Заявки от людей, которым нужна именно ваша постройка в вашем районе. Условия передачи заявок обсуждаем лично.
""") + "<p>Пока форма для подрядчиков не подключена — напишите через форму заявки ниже, указав в поле «Что важно», что вы подрядчик.</p>", index=False)


def policy_page():
    simple_page("/politika-konfidencialnosti/", "Политика конфиденциальности", "Политика конфиденциальности",
                "<p>Политика обработки персональных данных будет опубликована здесь до запуска приёма заявок, вместе с реквизитами оператора.</p>",
                index=False)


def not_found():
    body = f"""{head(f"Страница не найдена | {SITE['name']}", "Страница не найдена", "/404.html", False)}{header()}
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
    contractors_page()
    policy_page()
    not_found()
    urls = "".join(f"<url><loc>{SITE['base_url']}{p}</loc></url>" for p in indexable)
    (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nDisallow: /_build/\nDisallow: /docs/\nSitemap: {SITE['base_url']}/sitemap.xml\n", encoding="utf-8")
    total = 1 + len(SECTIONS) + sum(len(s["subs"]) for s in SECTIONS) + 3
    print(f"страниц: {total}, в индексе: {len(indexable)}")


if __name__ == "__main__":
    main()
