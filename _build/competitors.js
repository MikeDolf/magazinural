// Разбор страниц конкурентов из топа выдачи: порядок блоков, элементы конверсии, SEO.
//
//   NODE_PATH=$(npm root -g) node _build/competitors.js semantics/serp_yandex_*.json semantics/serp_google_*.json [--top 5]
//   NODE_PATH=$(npm root -g) node _build/competitors.js --url https://site.ru/page/ [--url ...]
//
// Входные файлы — выгрузки по docs/serp-top5.md. Результат — semantics/competitors/:
// pages.json (разбор каждой страницы), report.md (сводка: что есть у большинства топа).
// semantics/ в .gitignore: это исследование рынка, в публичный репозиторий не кладём.

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const OUT = path.join(__dirname, '..', 'semantics', 'competitors');
const SKIP = /(^|\.)(avito|youtube|vk|ok|dzen|pinterest|ozon|wildberries|market\.yandex|2gis|zoon|flamp|yell|profi|youdo|wikipedia|t-j|e1|drive2|forumhouse|houzz|instagram|tiktok|rutube|lemanapro|leroymerlin|petrovich|vseinstrumenti|aliexpress|sima-land|livemaster|hoff|domclick|rg|onduline|realty\.yandex|cian|kp|ria|pulscen|arendabesedok|park66|ratingfirmporemontu)\./;

const args = process.argv.slice(2);
const top = Number((args[args.indexOf('--top') + 1]) || 0) || 5;
const urls = new Map(); // url -> [{engine, query, pos}]
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--url') { urls.set(args[++i], [{ engine: 'вручную', query: '', pos: 0 }]); continue; }
  if (args[i] === '--top') { i++; continue; }
  const j = JSON.parse(fs.readFileSync(args[i], 'utf8'));
  for (const [q, r] of Object.entries(j.data)) {
    r.organic.slice(0, top).forEach((x, n) => {
      const h = new URL(x.url).hostname.replace(/^www\./, '');
      if (SKIP.test(h + '.')) return;
      if (!urls.has(x.url)) urls.set(x.url, []);
      urls.get(x.url).push({ engine: j.engine, query: q, pos: n + 1 });
    });
  }
}

// Признаки на странице: что ищем и как называем в отчёте.
const FEATURES = {
  'телефон в шапке': (d) => !!d.querySelector('header a[href^="tel:"], [class*=header] a[href^="tel:"]'),
  'обратный звонок': (d, t) => /перезвон|обратный звонок|заказать звонок/i.test(t),
  'мессенджеры (WhatsApp/Telegram)': (d) => !!d.querySelector('a[href*="wa.me"], a[href*="whatsapp"], a[href*="t.me/"], a[href*="telegram"]'),
  'цены в каталоге': (d, t) => (t.match(/(от\s*)?\d[\d\s]{2,}\s*(₽|руб)/gi) || []).length >= 3,
  'карточки товаров/проектов': (d) => d.querySelectorAll('[class*=card], [class*=product], [class*=item]').length >= 6,
  'фильтр / сортировка': (d, t) => !!d.querySelector('select, [class*=filter], [class*=sort]') || /фильтр|сортир/i.test(t),
  'калькулятор': (d, t) => /калькулятор|рассчитать стоимость|расчёт стоимости онлайн/i.test(t) || !!d.querySelector('input[type=range]'),
  'квиз (опрос из шагов)': (d, t) => /квиз|ответьте на \d+ вопрос|шаг \d+ из \d+|пройдите тест/i.test(t),
  'отзывы': (d, t) => /отзыв/i.test(t),
  'фото выполненных работ / портфолио': (d, t) => /наши работы|выполненные (работы|объекты)|портфолио|фото работ|наши объекты/i.test(t),
  'видео': (d) => !!d.querySelector('video, iframe[src*="youtube"], iframe[src*="rutube"], iframe[src*="vk.com/video"]'),
  'этапы работы': (d, t) => /этапы работ|как мы работаем|схема работы|порядок работ/i.test(t),
  'гарантия': (d, t) => /гаранти/i.test(t),
  'договор': (d, t) => /договор/i.test(t),
  'рассрочка / кредит': (d, t) => /рассрочк|кредит|сплит|ипотек/i.test(t),
  'доставка и монтаж': (d, t) => /доставк/i.test(t) && /монтаж|сборк|установк/i.test(t),
  'производство / цех': (d, t) => /производств|наш цех|собственн(ое|ый) (производство|цех)/i.test(t),
  'выезд на замер': (d, t) => /замер/i.test(t),
  'цифры о компании (лет, объектов)': (d, t) => /\d+\s*(лет|года) (на рынке|опыта|работы)|\d+\s*(объектов|построек|клиентов|проектов)/i.test(t),
  'FAQ на странице': (d, t) => /частые вопросы|вопросы и ответы|часто задаваемые/i.test(t) || !!d.querySelector('details'),
  'SEO-текст на странице': (d, t, m) => m.words >= 400,
  'карта / адрес офиса': (d) => !!d.querySelector('iframe[src*="yandex.ru/map"], iframe[src*="map"], [class*=map]'),
  'реквизиты (ИНН, ОГРН)': (d, t) => /ИНН|ОГРН/.test(t),
  'акции / скидки': (d, t) => /акци|скидк|спецпредложен/i.test(t),
  'варианты комплектации': (d, t) => /комплектац/i.test(t),
  'проекты с планировкой': (d, t) => /планировк|проект[ыа]? (бань|беседок|домов)/i.test(t),
  'хлебные крошки': (d) => !!d.querySelector('[class*=breadcrumb], [itemtype*=BreadcrumbList], nav[aria-label*=крош]'),
  'попап / онлайн-чат': (d) => !!d.querySelector('[class*=jivo], [class*=chat], [id*=jivo], [class*=popup], [class*=modal]'),
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch(process.env.HTTPS_PROXY ? { proxy: { server: process.env.HTTPS_PROXY } } : {});
  const ctx = await b.newContext({ locale: 'ru-RU', viewport: { width: 1366, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36' });
  const pages = [];
  const queue = [...urls];
  const crawl = async (url, hits) => {
    const p = await ctx.newPage();
    try {
      await p.goto(url, { timeout: 45000, waitUntil: 'domcontentloaded' });
      await p.waitForTimeout(2500);
      await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 800) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); } });
      const fnSrc = Object.fromEntries(Object.entries(FEATURES).map(([k, f]) => [k, f.toString()]));
      const r = await p.evaluate((fnSrc) => {
        const d = document;
        const t = d.body.innerText;
        const main = d.querySelector('main') || d.body;
        const words = (main.innerText.match(/[А-Яа-яЁёA-Za-z0-9-]+/g) || []).length;
        const m = { words };
        // Порядок блоков: заголовки h1–h3 сверху вниз с позицией на странице (в экранах).
        // Заголовки на div (частый случай у конструкторов) ловим по крупному жирному шрифту.
        const isHead = (h) => /^H[1-3]$/.test(h.tagName) || (h.children.length === 0 && parseFloat(getComputedStyle(h).fontSize) >= 24 && +getComputedStyle(h).fontWeight >= 500 && h.innerText.trim().length < 90);
        const blocks = [...d.querySelectorAll('h1, h2, h3, div, p, span, strong, b')].filter((h) => h.offsetParent && h.innerText.trim() && isHead(h))
          .map((h) => ({ tag: /^H[1-3]$/.test(h.tagName) ? h.tagName.toLowerCase() : 'h2*', text: h.innerText.trim().replace(/\s+/g, ' ').slice(0, 90), screen: +((h.getBoundingClientRect().top + scrollY) / innerHeight).toFixed(1) }))
          .filter((x, i, a) => x.text.length > 6 && !/^[\d\s.,]+(руб|₽)/i.test(x.text) && !a.slice(0, i).some((y) => y.text === x.text))
          .sort((x, y) => x.screen - y.screen);
        const schema = [...d.querySelectorAll('script[type="application/ld+json"]')].flatMap((s) => {
          try { const j = JSON.parse(s.textContent); return [].concat(j['@graph'] || j).map((x) => x['@type']).flat(); } catch (e) { return []; }
        });
        const micro = [...new Set([...d.querySelectorAll('[itemtype]')].map((x) => x.getAttribute('itemtype').split('/').pop()))];
        const features = {};
        for (const [k, src] of Object.entries(fnSrc)) { try { features[k] = !!(0, eval)('(' + src + ')')(d, t, m); } catch (e) { features[k] = false; } }
        const forms = d.querySelectorAll('form').length;
        const ctas = [...d.querySelectorAll('a, button')].map((x) => x.innerText.trim()).filter((x) => /заявк|рассчит|расчёт|расчет|заказ|звон|смет|консульт|получить|узнать цену|купить/i.test(x) && x.length < 40);
        return {
          title: d.title, desc: (d.querySelector('meta[name=description]') || {}).content || '',
          h1: (d.querySelector('h1') || {}).innerText || '', words, blocks, schema: [...new Set(schema)], micro,
          images: d.querySelectorAll('img').length, forms, ctas: [...new Set(ctas)].slice(0, 15), ctaCount: ctas.length,
          height: Math.round(d.body.scrollHeight / innerHeight), features,
          firstScreen: [...d.querySelectorAll('h1, h2, a, button')].filter((x) => x.getBoundingClientRect().top + scrollY < innerHeight && x.innerText.trim()).map((x) => x.innerText.trim().slice(0, 50)).slice(0, 25),
        };
      }, fnSrc);
      pages.push({ url, host: new URL(url).hostname.replace(/^www\./, ''), hits, ...r });
      console.log('ok', url, r.words, 'слов,', r.blocks.length, 'блоков');
    } catch (err) {
      pages.push({ url, hits, error: err.message.slice(0, 200) });
      console.log('ERR', url, err.message.slice(0, 100));
    }
    await p.close().catch(() => {});
  };
  // 6 вкладок параллельно; страница, которая висит дольше 90 с, считается ошибкой.
  await Promise.all(Array.from({ length: 6 }, async () => {
    for (let job; (job = queue.shift());) {
      const [url, hits] = job;
      let timer;
      await Promise.race([crawl(url, hits), new Promise((ok) => { timer = setTimeout(() => { pages.push({ url, hits, error: 'таймаут 90 с' }); console.log('ERR', url, 'таймаут'); ok(); }, 90000); })]);
      clearTimeout(timer);
    }
  }));
  await b.close();
  // страница, досчитанная после таймаута, могла попасть дважды — оставляем удачную запись
  const seen = new Map();
  for (const x of pages) if (!seen.has(x.url) || seen.get(x.url).error) seen.set(x.url, x);
  pages.splice(0, pages.length, ...seen.values());
  fs.writeFileSync(path.join(OUT, 'pages.json'), JSON.stringify(pages, null, 1));

  // Сводка
  const ok = pages.filter((x) => !x.error);
  const pct = (n) => Math.round((100 * n) / (ok.length || 1));
  const med = (a) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  const lines = [`# Разбор топа: ${ok.length} страниц (ошибок загрузки: ${pages.length - ok.length})`, ''];
  lines.push(`Медиана: ${med(ok.map((x) => x.words))} слов, ${med(ok.map((x) => x.blocks.length))} заголовков, ${med(ok.map((x) => x.images))} картинок, ${med(ok.map((x) => x.ctaCount))} призывов, ${med(ok.map((x) => x.height))} экранов в высоту.`, '');
  lines.push('## Что есть у топа (доля страниц)', '');
  for (const k of Object.keys(FEATURES).sort((a, z) => ok.filter((x) => x.features[z]).length - ok.filter((x) => x.features[a]).length)) {
    lines.push(`- ${pct(ok.filter((x) => x.features[k]).length)}% — ${k}`);
  }
  const sch = {};
  ok.forEach((x) => [...x.schema, ...x.micro].forEach((s) => { sch[s] = (sch[s] || 0) + 1; }));
  lines.push('', '## Разметка schema.org', '', ...Object.entries(sch).sort((a, z) => z[1] - a[1]).map(([s, n]) => `- ${s}: ${n}`));
  const hosts = {};
  ok.forEach((x) => { hosts[x.host] = (hosts[x.host] || 0) + x.hits.length; });
  lines.push('', '## Сайты по числу попаданий в топ', '', ...Object.entries(hosts).sort((a, z) => z[1] - a[1]).map(([h, n]) => `- ${h}: ${n}`));
  lines.push('', '## Страницы: порядок блоков', '');
  for (const x of ok) {
    lines.push(`### ${x.host} — ${x.hits.map((h) => `${h.engine} «${h.query}» #${h.pos}`).join(', ')}`, x.url,
      `title (${x.title.length}): ${x.title}`, `H1: ${x.h1.trim()}`, `${x.words} слов, ${x.images} картинок, ${x.forms} форм, ${x.height} экранов; первый экран: ${x.firstScreen.join(' · ')}`,
      `Есть: ${Object.entries(x.features).filter(([, v]) => v).map(([k]) => k).join(', ')}`, '');
    x.blocks.forEach((bl) => lines.push(`${'  '.repeat(Math.max(0, +bl.tag[1] - 1))}- [${bl.screen}] ${bl.tag}: ${bl.text}`));
    lines.push('');
  }
  fs.writeFileSync(path.join(OUT, 'report.md'), lines.join('\n'));
  console.log('готово:', path.join(OUT, 'report.md'));
})();
