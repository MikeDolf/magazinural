Ты работаешь в моём Chrome на вкладке wordstat.yandex.ru, я залогинен в Яндексе. Собери в Яндекс Вордстате полную семантику для сайта magazinural.ru, который я буду продвигать. Тема сайта — деревянное загородное строительство в Екатеринбурге и Свердловской области: беседки, террасы и веранды, навесы и перголы, хозблоки, дровники и сараи, летние кухни и барбекю-зоны, каркасные бани и дома, дачные и садовые домики, детские домики и площадки, качели, зимние горки, постройки для животных. На сайте будут каталог построек с объявлениями подрядчиков, информационные статьи и страницы по пригородам.

ЧТО НУЖНО
— Каждую маску из скрипта ниже собрать в двух регионах: Екатеринбург (регион 54) и Свердловская область (регион 11162).
— По каждой маске скачать все фразы, которые отдаёт Вордстат: все страницы таблицы «Популярные запросы» (10 страниц по 200 строк, лимит Вордстата — 2000 фраз на маску), а также «Похожие», если они есть.
— Маски, которые упёрлись в лимит 2000, скрипт сам доберёт уточнениями и вариантом с минус-словами, чтобы получить фразы за пределом лимита.
— В конце скачать один архив: файл на каждую маску по каждому региону и общий файл всех фраз без дублей с частотностью по Екатеринбургу и по области.

ПРАВИЛА
1. Ты только читаешь данные. Не меняй настройки аккаунта, не нажимай на рекламу, не уходи с wordstat.yandex.ru и не перезагружай вкладку без необходимости.
2. Весь сбор делает скрипт ниже. Выполни его на странице через JavaScript. Не переписывай и не сокращай его, вставь целиком.
3. Не выводи сырые данные в ответах инструмента, только статус. Тысячи строк забьют твой контекст.
4. Сбор идёт в фоне 20–40 минут. Не жди его одним вызовом с await: запусти и проверяй статус раз в 1–2 минуты.
5. Данные сохраняются в хранилище браузера (IndexedDB) после каждой маски и не пропадают при перезагрузке или закрытии вкладки. Если вкладка перезагрузилась, снова выполни скрипт целиком и вызови __ws.run(): собранные маски он пропустит и продолжит с места остановки.

ПОРЯДОК
Шаг 1. Выполни на странице скрипт из блока СКРИПТ целиком. Он вернёт строку «скрипт загружен…».
Шаг 2. Выполни: await __ws.check()
   Должно вернуться «ok…» и около 200 строк на первой странице. Если пришла ОШИБКА, проверь, что открыт wordstat.yandex.ru и выполнен вход в Яндекс. Если не помогло, остановись и напиши мне.
Шаг 3. Выполни: __ws.run()
Шаг 4. Раз в 1–2 минуты выполняй JSON.stringify(__ws.status()) и коротко сообщай мне прогресс: какая маска идёт, сколько собрано и сколько ошибок.
   — Если «ошибок» растёт подряд (больше 10 за пару минут), выполни __ws.stop(), подожди 5 минут и снова __ws.run().
   — Если «сбой» не null, сообщи мне текст сбоя.
   — Если Вордстат показал капчу или попросил войти, остановись (__ws.stop()) и попроси меня пройти проверку. Потом снова __ws.run().
Шаг 5. Когда в статусе «готово»: true, выполни: await __ws.export()
   Скачается архив wordstat_magazinural_ДАТА.zip. Если Chrome спросит про скачивание, попроси меня разрешить.
   Внутри архива:
   README.txt — параметры сбора и итоги;
   00_vse_frazy_bez_dubley.csv — фраза; частотность Екатеринбург; частотность Свердловская обл.; тип запроса; маски-источники;
   01_ekaterinburg/*.csv и 02_sverdlovskaya_obl/*.csv — по файлу на маску: фраза; частотность; тип запроса;
   03_zhurnal_masok.csv — журнал: строк по маске, упёрлась ли в 2000, статус.
   Формат: UTF-8 с BOM, разделитель «;».
Шаг 6. Отчитайся мне: сколько масок собрано по каждому региону, сколько дали ноль и сколько с ошибкой (назови их), какие маски упёрлись в 2000, сколько вышло уникальных фраз и по типам, имя скачанного архива. Всё это есть в ответе __ws.export().

Если нужно выгрузить промежуточный результат до конца сбора, просто выполни await __ws.export(): выгрузится всё собранное на этот момент, а сбор продолжится.

СКРИПТ
```js
(() => {
  const PAUSE = 350;
  const REGIONS = {'54': 'Екатеринбург', '11162': 'Свердловская обл.'};
  const DB_NAME = 'wordstat_magazinural', STORE = 'masks';

  // ===== МАСКИ =====
  const BASE = [
    // беседки
    'беседка', 'беседки', 'беседка закрытая', 'беседка открытая', 'беседка остекленная', 'беседка зимняя',
    'беседка теплая', 'беседка с мангалом', 'беседка с барбекю', 'беседка с печью', 'беседка с летней кухней',
    'беседка шестигранная', 'беседка восьмигранная', 'беседка для дачи', 'беседка из бруса', 'беседка из бревна',
    'беседка деревянная', 'беседка каркасная', 'беседка 3х3', 'беседка 3х4', 'беседка 4х4', 'беседка 4х6',
    'беседка 6х6', 'беседка 3 на 4', 'беседка 4 на 6', 'мягкие окна для беседки',
    // террасы, веранды, крыльцо
    'терраса', 'веранда', 'терраса к дому', 'веранда к дому', 'пристрой веранды', 'пристроить веранду',
    'веранда закрытая', 'терраса открытая', 'терраса из дерева', 'терраса с крышей', 'терраса к бане',
    'крыльцо деревянное', 'крыльцо с навесом',
    // навесы
    'навес', 'навес для машины', 'навес к дому', 'навес деревянный', 'навес над крыльцом', 'навес для дров',
    'пергола', 'карпорт',
    // хозпостройки
    'хозблок', 'хозблок с дровником', 'хозблок с туалетом', 'хозблок с душем', 'дровник', 'сарай',
    'сарай деревянный', 'бытовка', 'летний душ', 'туалет дачный', 'туалет деревянный', 'мастерская на участке',
    // кухни и зоны отдыха
    'летняя кухня', 'барбекю зона', 'мангальная зона', 'зона отдыха на даче',
    // бани
    'каркасная баня', 'баня под ключ', 'баня из бруса', 'баня бочка', 'баня мобильная', 'баня с террасой',
    'баня с комнатой отдыха', 'баня 3х4', 'баня 4х6', 'баня 6х6', 'строительство бани', 'банный комплекс',
    'купель для бани',
    // дома
    'каркасный дом', 'каркасный дом под ключ', 'дачный домик', 'садовый домик', 'домик для дачи',
    'гостевой дом на участке', 'дом из бруса', 'модульный дом', 'мини дом', 'дом шалаш', 'а фрейм дом',
    'барнхаус',
    // детское
    'детский домик', 'детский домик на дачу', 'домик на дереве', 'детская площадка для дачи',
    'детский игровой комплекс', 'детская горка деревянная', 'песочница', 'качели садовые', 'качели деревянные',
    'качели для дачи',
    // горки
    'горка зимняя', 'горка деревянная', 'ледяная горка', 'горка для катания',
    // для животных
    'курятник', 'собачья будка', 'вольер для собаки', 'крольчатник',
    // прочее
    'деревянный забор', 'деревянное строительство', 'малые архитектурные формы', 'садовый мостик',
    // информационные
    'беседка своими руками', 'как построить беседку', 'чертеж беседки', 'проект беседки', 'размеры беседки',
    'фундамент для беседки', 'винтовые сваи для беседки', 'крыша для беседки', 'чем покрыть крышу беседки',
    'пол в беседке', 'мангал в беседке', 'печь для беседки', 'освещение беседки', 'отделка беседки',
    'навес своими руками', 'беседка или навес', 'фундамент под баню', 'свайный фундамент для бани',
    'какую баню выбрать', 'каркасная баня или из бруса', 'утепление каркасной бани', 'сколько строится баня',
    'проект бани', 'баня своими руками', 'усадка бруса', 'каркасный дом своими руками',
    'утепление каркасного дома', 'фундамент для каркасного дома', 'сколько стоит построить каркасный дом',
    'пропитка для дерева', 'антисептик для дерева', 'чем обработать брус', 'защита дерева от гниения',
    'покраска деревянного дома', 'лиственница или сосна', 'строганый брус или клееный',
    'разрешение на строительство бани', 'нужно ли разрешение на баню', 'регистрация бани на участке',
    'налог на баню', 'налог на беседку', 'расстояние от бани до забора', 'расстояние от хозблока до забора',
    'расстояние от постройки до забора', 'нормы застройки участка', 'снт что можно строить',
    'хозблок своими руками', 'дровник своими руками', 'детский домик своими руками', 'горка своими руками',
    'курятник своими руками', 'летняя кухня своими руками',
    // конкуренты
    'woods stroy', 'вудс строй', 'беседки екатеринбург производитель', 'строительство беседок екатеринбург',
    'строительство бань екатеринбург', 'каркасные бани екатеринбург'
  ];
  // уточнения: каждая основа + каждый хвост
  const REFINE_BASE = ['беседка', 'терраса', 'веранда', 'навес', 'хозблок', 'дровник', 'летняя кухня',
    'каркасная баня', 'баня', 'каркасный дом', 'дачный домик', 'детский домик', 'детская площадка',
    'горка деревянная', 'пергола'];
  const REFINE_TAIL = ['под ключ', 'цена', 'цены', 'стоимость', 'сколько стоит', 'купить', 'заказать', 'на заказ',
    'екатеринбург', 'екб', 'недорого', 'от производителя', 'готовые', 'с установкой', 'отзывы', 'из дерева',
    'из бруса', 'проект', 'проекты', 'размеры', 'своими руками', 'как построить', 'фундамент', 'чертеж', 'фото',
    'разрешение', 'какая лучше'];
  // пригороды: основа + город
  const GEO_BASE = ['беседка', 'баня под ключ', 'каркасный дом', 'навес', 'терраса'];
  const GEO_CITY = ['березовский', 'арамиль', 'верхняя пышма', 'среднеуральск', 'сысерть', 'полевской', 'ревда',
    'первоуральск', 'заречный', 'асбест', 'кольцово', 'белоярский', 'каменск уральский', 'нижний тагил'];
  // добор для масок, упёршихся в 2000
  const DEEP_TAIL = ['для дачи', 'на дачу', 'из дерева', 'из бруса', 'деревянная', 'деревянный', 'с мангалом',
    'закрытая', 'закрытый', 'открытая', 'своими руками', 'фото', 'проект', 'размеры', 'цена', 'купить',
    'под ключ', 'екатеринбург', '3х3', '3х4', '4х4', '4х6', '6х6', '6х8'];
  const MINUS = '-аренда -снять -забронировать -прокат -парк -отель -кафе -ресторан -шарташ -уктус ' +
    '-майнкрафт -раскраска -рисунок';

  function masks() {
    const m = [...BASE];
    for (const b of REFINE_BASE) for (const t of REFINE_TAIL) m.push(`${b} ${t}`);
    for (const b of GEO_BASE) for (const c of GEO_CITY) m.push(`${b} ${c}`);
    return [...new Set(m.map(s => s.trim().toLowerCase()))];
  }
  const tasksFor = (list, level) => list.flatMap(mask => Object.keys(REGIONS).map(region => ({mask, region, level})));

  // ===== IndexedDB: данные переживают перезагрузку и закрытие вкладки =====
  let dbp;
  const db = () => dbp || (dbp = new Promise((res, rej) => {
    const r = indexedDB.open(DB_NAME, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE);
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  }));
  const tx = async (mode, fn) => {
    const d = await db();
    return new Promise((res, rej) => {
      const x = d.transaction(STORE, mode);
      const req = fn(x.objectStore(STORE));
      x.oncomplete = () => res(req && req.result);
      x.onerror = () => rej(x.error);
    });
  };
  const put = (k, v) => tx('readwrite', s => s.put(v, k));
  const keys = () => tx('readonly', s => s.getAllKeys());
  const all = () => tx('readonly', s => s.getAll());
  const keyOf = t => `${t.region}|${t.mask}`;

  // ===== запросы к Вордстату =====
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  async function page(t, p) {
    for (let a = 0; a < 4; a++) {
      try {
        const r = await fetch('/wordstat/api/getMoreTableData', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({currentDevice: 'desktop,phone,tablet', dbname: 'rus', phPage: String(p),
                                filters: {region: t.region, tableType: 'popular'}, searchValue: t.mask})
        });
        if (r.ok) {
          const j = await r.json();
          if (j && Array.isArray(j.popular)) return j;
        }
      } catch (e) {}
      await sleep(1500 * (a + 1));
    }
    return null;
  }
  async function collect(t) {
    const rows = [];
    let truncated = false;
    for (let p = 0; p < 10; p++) {
      const j = await page(t, p);
      if (!j) { if (p === 0) return null; break; }
      for (const x of j.popular) rows.push([x.text, x.value, 'popular']);
      if (p === 0) for (const x of (j.associations || [])) rows.push([x.text, x.value, 'похожие']);
      if (!j.hasNextPage) break;
      if (p === 9) truncated = true;
      await sleep(PAUSE);
    }
    return {rows, truncated};
  }

  // ===== разметка =====
  const RX = [
    ['нецелевой', /аренд|снять|забронир|прокат|парк|отел|база отдыха|кафе|ресторан|день рождения|шарташ|уктус|академ|виктори|чемоданчик|карасики|белкино|майнкрафт|раскраск|рисун|песн|фильм|ваканси|игр[аыуе]|мультик/],
    ['коммерческий', /цен[аы]|стоимост|сколько стоит|купить|заказ|под ключ|недорог|продаж|производ|изготов|компани|фирм|строительств|прайс|екатеринбург|екб|свердлов|отзыв|с установкой|готов/],
    ['информационный', /своими руками|как |чертеж|чертёж|схем|фото|видео|размер|фундамент|проект|виды|какой|какая|какие|из чего|иде[ия]|вариант|разрешени|инструкц|нужно ли|расстояни|норм|налог|чем |можно ли| или /]
  ];
  const classify = s => { const x = ` ${s.toLowerCase()} `; for (const [n, r] of RX) if (r.test(x)) return n; return 'общий'; };

  // ===== ZIP без сжатия, без внешних библиотек =====
  const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  function zip(files) {
    const enc = new TextEncoder(), parts = [], central = [];
    let offset = 0;
    const d = new Date();
    const time = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1);
    const date = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
    for (const f of files) {
      const name = enc.encode(f.name), data = enc.encode(f.text), crc = crc32(data);
      const h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true);
      h.setUint16(8, 0, true); h.setUint16(10, time, true); h.setUint16(12, date, true);
      h.setUint32(14, crc, true); h.setUint32(18, data.length, true); h.setUint32(22, data.length, true);
      h.setUint16(26, name.length, true); h.setUint16(28, 0, true);
      parts.push(new Uint8Array(h.buffer), name, data);
      const c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true);
      c.setUint16(8, 0x0800, true); c.setUint16(10, 0, true); c.setUint16(12, time, true);
      c.setUint16(14, date, true); c.setUint32(16, crc, true); c.setUint32(20, data.length, true);
      c.setUint32(24, data.length, true); c.setUint16(28, name.length, true);
      c.setUint32(42, offset, true);
      central.push(new Uint8Array(c.buffer), name);
      offset += 30 + name.length + data.length;
    }
    const cdSize = central.reduce((s, x) => s + x.length, 0);
    const e = new DataView(new ArrayBuffer(22));
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true);
    e.setUint32(12, cdSize, true); e.setUint32(16, offset, true);
    return new Blob([...parts, ...central, new Uint8Array(e.buffer)], {type: 'application/zip'});
  }
  function download(name, blob) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 120000);
  }
  const q = s => `"${String(s ?? '').replace(/"/g, '""')}"`;
  const csv = rows => '﻿' + rows.map(r => r.map(q).join(';')).join('\r\n');
  const fname = s => s.replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, ' ').slice(0, 120);

  // ===== состояние и управление =====
  const W = window.__ws = window.__ws || {};
  W.st = W.st || {};
  const st = W.st;

  async function pass(tasks) {
    const have = new Set(await keys());
    st.total += tasks.length;
    for (let i = 0; i < tasks.length; i++) {
      if (st.stopFlag) return;
      const t = tasks[i], k = keyOf(t);
      st.current = `этап ${t.level}, ${i + 1}/${tasks.length}: «${t.mask}» [${REGIONS[t.region]}]`;
      if (have.has(k)) { st.skipped++; continue; }
      const res = await collect(t);
      if (!res) { st.errors.push(k); await sleep(PAUSE); continue; }
      await put(k, {...t, ...res, status: res.rows.length ? 'ok' : 'ноль', ts: Date.now()});
      have.add(k);
      st.done++;
      st.phrases += res.rows.length;
      await sleep(PAUSE);
    }
  }

  W.run = () => {
    if (st.running) return 'уже идёт: ' + st.current;
    Object.assign(st, {running: true, finished: false, stopFlag: false, total: 0, done: 0, skipped: 0,
                       phrases: 0, errors: [], current: '', fatal: null});
    (async () => {
      try {
        await pass(tasksFor(masks(), 1));
        if (!st.stopFlag) {
          const hit = (await all()).filter(v => v.level === 1 && v.truncated);
          const deep = [];
          for (const v of hit) {
            deep.push({mask: `${v.mask} ${MINUS}`, region: v.region, level: 2});
            for (const t of DEEP_TAIL) deep.push({mask: `${v.mask} ${t}`, region: v.region, level: 2});
          }
          await pass(deep);
        }
        if (!st.stopFlag && st.errors.length) {
          const retry = st.errors.map(k => { const [region, ...m] = k.split('|'); return {mask: m.join('|'), region, level: 3}; });
          st.errors = [];
          await sleep(30000);
          await pass(retry);
        }
        if (!st.stopFlag) st.finished = true;
      } catch (e) { st.fatal = String(e); }
      st.running = false;
    })();
    return `запущено, масок: ${masks().length}, запросов первого этапа: ${masks().length * 2}`;
  };
  W.stop = () => { st.stopFlag = true; return 'остановится после текущей маски'; };
  W.status = () => ({сейчас: st.current, задач: st.total, собрано: st.done, пропущено_уже_было: st.skipped,
    фраз: st.phrases, ошибок: (st.errors || []).length, последние_ошибки: (st.errors || []).slice(-5),
    идёт: !!st.running, готово: !!st.finished, сбой: st.fatal || null});
  W.check = async () => {
    const j = await page({mask: 'беседка', region: '54'}, 0);
    if (!j || !j.popular.length) return 'ОШИБКА: Вордстат не отвечает. Проверь, что открыт wordstat.yandex.ru и выполнен вход в Яндекс.';
    return `ok: «беседка», Екатеринбург: строк на первой странице ${j.popular.length}, первая: ${j.popular[0].text} — ${j.popular[0].value}`;
  };

  W.export = async () => {
    const data = (await all()).filter(v => v && v.mask);
    const files = [];
    const folder = {'54': '01_ekaterinburg', '11162': '02_sverdlovskaya_obl'};
    const map = new Map();
    for (const v of data) {
      files.push({name: `${folder[v.region]}/${fname(v.mask)}.csv`,
                  text: csv([['фраза', 'частотность', 'тип запроса', 'источник строки'],
                             ...v.rows.map(r => [r[0], r[1], classify(String(r[0])), r[2]])])});
      for (const [text, value] of v.rows) {
        const k = String(text).toLowerCase().replace(/\s+/g, ' ').trim();
        if (!k) continue;
        const e = map.get(k) || {text: k, '54': '', '11162': '', src: new Set()};
        if (e[v.region] === '' || Number(value) > Number(e[v.region])) e[v.region] = value;
        e.src.add(v.mask);
        map.set(k, e);
      }
    }
    const types = {};
    const merged = [...map.values()].sort((a, b) => (Number(b['54']) || 0) - (Number(a['54']) || 0)).map(e => {
      const ty = classify(e.text); types[ty] = (types[ty] || 0) + 1;
      return [e.text, e['54'], e['11162'], ty, [...e.src].join(' | ')];
    });
    files.unshift({name: '00_vse_frazy_bez_dubley.csv',
      text: csv([['фраза', 'частотность Екатеринбург', 'частотность Свердловская обл.', 'тип запроса', 'маски-источники'], ...merged])});
    const log = data.map(v => [v.mask, REGIONS[v.region], v.level, v.rows.length, v.truncated ? 'да' : 'нет', v.status]);
    for (const k of (st.errors || [])) { const [r, ...m] = k.split('|'); log.push([m.join('|'), REGIONS[r], '', 0, '', 'ошибка']); }
    files.push({name: '03_zhurnal_masok.csv',
      text: csv([['маска', 'регион', 'этап', 'строк', 'упёрлась в 2000', 'статус'], ...log])});
    const hit = data.filter(v => v.truncated).map(v => `  ${v.mask} [${REGIONS[v.region]}]`);
    const byRegion = r => data.filter(v => v.region === r);
    files.unshift({name: 'README.txt', text: [
      'Семантика для magazinural.ru (деревянное загородное строительство), Яндекс Вордстат',
      `Выгружено: ${new Date().toLocaleString('ru-RU')}`,
      'Регионы: 54 — Екатеринбург, 11162 — Свердловская область. Устройства: все. Таблица «Популярные запросы».',
      `Масок собрано: Екатеринбург ${byRegion('54').length}, Свердловская обл. ${byRegion('11162').length}`,
      `С нулевым результатом: ${data.filter(v => v.status === 'ноль').length}; с ошибкой: ${(st.errors || []).length}`,
      `Уникальных фраз: ${map.size}; по типам: ${Object.entries(types).map(([k, n]) => k + ' ' + n).join(', ')}`,
      'Этап 1 — основные маски; этап 2 — добор для масок, упёршихся в лимит 2000; этап 3 — повтор ошибок.',
      'Упёрлись в 2000 (данные за пределом лимита добраны уточнениями этапа 2):', ...hit,
      '', 'Файлы: 00 — все фразы без дублей; 01 и 02 — по файлу на маску; 03 — журнал масок.',
      'CSV: UTF-8 с BOM, разделитель «;».'
    ].join('\r\n')});
    const stamp = new Date().toISOString().slice(0, 10);
    download(`wordstat_magazinural_${stamp}.zip`, zip(files));
    return `скачан архив wordstat_magazinural_${stamp}.zip: файлов ${files.length}, уникальных фраз ${map.size}, ` +
           `масок ${data.length}, упёрлись в 2000: ${hit.length}, типы: ${JSON.stringify(types)}`;
  };

  return `скрипт загружен. Масок: ${masks().length} × 2 региона. Дальше: await __ws.check(), затем __ws.run()`;
})();
```
