Ты работаешь в моём Chrome. Собери топ-10 органической выдачи Яндекса (регион Екатеринбург) и Google по 40 коммерческим запросам для сайта magazinural.ru: строим деревянные постройки в Екатеринбурге — беседки, бани, навесы, террасы, веранды, хозблоки, каркасные и мини-дома, детские домики и площадки. Мне нужны адреса сайтов конкурентов, чтобы потом разобрать их структуру.

ПРАВИЛА
1. Ты только читаешь выдачу. Не нажимай на рекламу и результаты, не меняй настройки поиска и аккаунта.
2. Сбор делает скрипт ниже. Выполни его через JavaScript на странице поисковика, целиком, не сокращая.
3. В ответах инструмента выводи только статус, не сырые данные.
4. Скрипт делает паузу 5–9 секунд между запросами, сбор по одному поисковику идёт 4–6 минут. Не жди его одним вызовом: запусти и проверяй статус раз в минуту.
5. Результаты сохраняются в хранилище браузера (localStorage) после каждого запроса. Если вкладка перезагрузилась, выполни скрипт заново и вызови __serp.run(): собранные запросы он пропустит.

ПОРЯДОК (сначала Яндекс, потом Google)
Шаг 1. Открой https://yandex.ru/search/?text=беседки&lr=54 . Если Яндекс показал капчу, попроси меня её пройти.
Шаг 2. Выполни скрипт из блока СКРИПТ. Он вернёт «скрипт загружен: yandex…».
Шаг 3. Выполни: await __serp.check() — должно вернуться «ok, результатов: N» с N от 5 и больше.
   Если вернулось «0 результатов» или ошибка разбора — переходи к РУЧНОМУ РЕЖИМУ ниже.
Шаг 4. Выполни: __serp.run(). Раз в минуту выполняй JSON.stringify(__serp.status()) и коротко сообщай прогресс.
   — Если в статусе «капча»: true — попроси меня пройти проверку на этой вкладке (обнови страницу), потом выполни скрипт заново и __serp.run().
Шаг 5. Когда «готово»: true — выполни __serp.export(). Скачается serp_yandex_ДАТА.json.
Шаг 6. Открой https://www.google.com/search?q=беседки+екатеринбург&hl=ru и повтори шаги 2–5. Скачается serp_google_ДАТА.json.
Шаг 7. Отчитайся: сколько запросов собрано в каждом поисковике, где пусто или ошибка.

РУЧНОЙ РЕЖИМ (если check() не находит результаты: поисковик не отдал выдачу скрипту)
Выполни __serp.manualList() — он вернёт список адресов поиска. Открывай их по очереди в этой вкладке (не чаще раза в 5 секунд), после загрузки каждой страницы выполни скрипт заново и затем __serp.parseHere(). Он разберёт открытую страницу и сохранит результат. Когда пройдёшь все, выполни __serp.export().

СКРИПТ
```js
(() => {
  const ENGINE = location.hostname.includes('yandex') ? 'yandex' : location.hostname.includes('google') ? 'google' : null;
  if (!ENGINE) return 'ОШИБКА: открой yandex.ru или google.com';
  const KEY = 'serp_magazinural_' + ENGINE;
  const QUERIES = [
    'беседки под ключ', 'купить беседку', 'беседка из бруса', 'закрытая беседка', 'беседка с мангалом',
    'каркасные дома под ключ', 'навесы', 'навес для автомобиля', 'навес из дерева', 'терраса под ключ',
    'терраса к дому', 'веранда к дому', 'сарай для дачи купить', 'купить баню', 'баня под ключ',
    'баня бочка', 'каркасная баня под ключ', 'мобильная баня купить', 'мангальная зона под ключ', 'хозблок купить',
    'хозблок для дачи', 'дачный туалет купить', 'пергола деревянная', 'мини дом под ключ', 'барнхаус под ключ',
    'деревянный забор под ключ', 'детский домик для дачи', 'садовые качели деревянные', 'дачный домик под ключ', 'дровник купить',
    'пристрой к дому под ключ', 'каркасный гараж под ключ', 'летний душ для дачи', 'летняя кухня под ключ', 'детская площадка для дачи',
    'курятник купить', 'грядки из дерева', 'деревянная горка для детей', 'гриль домик купить', 'дом баня под ключ',
  ];
  const urlFor = (q) => ENGINE === 'yandex'
    ? '/search/?lr=54&text=' + encodeURIComponent(q)
    : '/search?hl=ru&gl=ru&num=10&q=' + encodeURIComponent(q + ' екатеринбург');
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } };
  const save = (d) => localStorage.setItem(KEY, JSON.stringify(d));
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
  const own = /(^|\.)(yandex\.|ya\.ru|google\.|gstatic|googleusercontent|youtube\.com\/results)/;

  function parse(doc) {
    const out = [];
    if (ENGINE === 'yandex') {
      for (const li of doc.querySelectorAll('li.serp-item')) {
        const label = (li.querySelector('.Organic-Subtitle, .OrganicTextContentSpan, .Label, .organic__subtitle') || li).textContent.slice(0, 400);
        const ad = li.querySelector('[data-fast-name="direct"], [data-fast-subtype*="direct"]') || /(^|\s)(Реклама|Промо)(\s|$)/.test(label);
        const a = li.querySelector('a.OrganicTitle-Link, h2 a, a.organic__url');
        if (!a || !a.href || own.test(host(a.href))) continue;
        out.push({ url: a.href, title: (li.querySelector('h2') || a).textContent.trim(), ad: !!ad });
      }
    } else {
      for (const h3 of doc.querySelectorAll('#search a h3, #rso a h3, a h3')) {
        const a = h3.closest('a');
        let href = a.getAttribute('href') || '';
        if (href.startsWith('/url?')) href = new URLSearchParams(href.slice(5)).get('q') || '';
        if (!/^https?:/.test(href) || own.test(host(href)) || out.some((x) => x.url === href)) continue;
        out.push({ url: href, title: h3.textContent.trim(), ad: !!a.closest('[data-text-ad], #tads, #bottomads') });
      }
    }
    const organic = out.filter((x) => !x.ad);
    return { organic: organic.slice(0, 10), ads: out.filter((x) => x.ad).map((x) => host(x.url)) };
  }

  const captcha = (url, doc) => /showcaptcha|\/sorry\//.test(url) || /Вы не робот|unusual traffic/i.test(doc.title + ' ' + (doc.body ? doc.body.textContent.slice(0, 2000) : ''));
  const st = { engine: ENGINE, всего: QUERIES.length, собрано: 0, текущий: null, ошибок: 0, капча: false, готово: false, сбой: null };
  let stopFlag = false;

  async function one(q) {
    const r = await fetch(urlFor(q), { credentials: 'include' });
    const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
    if (captcha(r.url, doc)) { st.капча = true; throw new Error('капча'); }
    return parse(doc);
  }

  window.__serp = {
    async check() {
      try { const res = await one(QUERIES[0]); return res.organic.length ? `ok, результатов: ${res.organic.length}, первый: ${host(res.organic[0].url)}` : '0 результатов — нужен ручной режим'; }
      catch (e) { return 'ОШИБКА: ' + e.message; }
    },
    async run() {
      stopFlag = false; st.капча = false; st.сбой = null;
      const d = load();
      for (const q of QUERIES) {
        if (stopFlag) break;
        if (d[q] && d[q].organic.length) continue;
        st.текущий = q;
        try {
          const res = await one(q);
          if (!res.organic.length) throw new Error('пусто');
          d[q] = { ...res, date: new Date().toISOString() }; save(d);
        } catch (e) {
          st.ошибок++; st.сбой = q + ': ' + e.message;
          if (st.капча) return 'капча — пройди проверку и запусти снова';
        }
        st.собрано = Object.keys(load()).length;
        await new Promise((ok) => setTimeout(ok, 5000 + Math.random() * 4000));
      }
      st.собрано = Object.keys(load()).length; st.текущий = null;
      st.готово = QUERIES.every((q) => load()[q]);
      return 'завершено';
    },
    stop() { stopFlag = true; return 'остановлено'; },
    status() { st.собрано = Object.keys(load()).length; return st; },
    manualList() { return QUERIES.filter((q) => !load()[q]).map((q) => location.origin + urlFor(q)); },
    parseHere() {
      const p = new URLSearchParams(location.search);
      let q = p.get('text') || p.get('q') || '';
      q = q.replace(/\s*екатеринбург$/, '');
      if (!QUERIES.includes(q)) return 'ОШИБКА: этот запрос не из списка: ' + q;
      const res = parse(document);
      if (!res.organic.length) return 'ОШИБКА: на странице не нашёл результатов';
      const d = load(); d[q] = { ...res, date: new Date().toISOString(), manual: true }; save(d);
      return `сохранено: ${q}, результатов ${res.organic.length}; осталось ${QUERIES.length - Object.keys(d).length}`;
    },
    export() {
      const d = load();
      const blob = new Blob([JSON.stringify({ engine: ENGINE, region: ENGINE === 'yandex' ? 54 : 'gl=ru + «екатеринбург» в запросе', data: d }, null, 1)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = `serp_${ENGINE}_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a); a.click(); a.remove();
      return `выгружено запросов: ${Object.keys(d).length} из ${QUERIES.length}, файл ${a.download}`;
    },
  };
  return `скрипт загружен: ${ENGINE}, запросов ${QUERIES.length}, уже собрано ${Object.keys(load()).length}`;
})();
```
