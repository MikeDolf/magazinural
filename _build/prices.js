// Сбор цен и сроков со страниц конкурентов (semantics/competitors/pages.json) → semantics/competitors/prices.json
//   NODE_PATH=$(npm root -g) node _build/prices.js
const fs = require('fs'); const path = require('path'); const { chromium } = require('playwright');
const DIR = path.join(__dirname, '..', 'semantics', 'competitors');
const pages = JSON.parse(fs.readFileSync(path.join(DIR, 'pages.json'), 'utf8')).filter((p) => !p.error && p.features && p.features['цены в каталоге']);
(async () => {
  const b = await chromium.launch(process.env.HTTPS_PROXY ? { proxy: { server: process.env.HTTPS_PROXY } } : {});
  const ctx = await b.newContext({ locale: 'ru-RU', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36' });
  const out = []; const queue = [...pages];
  await Promise.all(Array.from({ length: 6 }, async () => {
    for (let pg; (pg = queue.shift());) {
      const p = await ctx.newPage();
      try {
        await p.goto(pg.url, { timeout: 45000, waitUntil: 'domcontentloaded' }); await p.waitForTimeout(2000);
        const r = await p.evaluate(() => {
          const lines = document.body.innerText.split('\n').map((s) => s.replace(/\s+/g, ' ').trim()).filter(Boolean);
          const items = [];
          lines.forEach((l, i) => {
            const m = l.match(/(?:от\s*)?(\d{1,3}(?:[\s ]\d{3})+|\d{4,7})\s*(?:₽|руб|р\.)/i);
            if (!m) return;
            const price = +m[1].replace(/\D/g, '');
            if (price < 3000 || price > 15000000) return;
            const ctx = lines.slice(Math.max(0, i - 4), i + 1).join(' | ').slice(0, 300);
            items.push({ price, from: /от\s*\d/i.test(l), ctx });
          });
          const terms = lines.filter((l) => /(срок|изготов|за \d+ (дн|недел)|от \d+ (дн|недел)|\d+\s*(рабочих )?дн)/i.test(l) && l.length < 200).slice(0, 15);
          return { items: items.slice(0, 80), terms };
        });
        out.push({ url: pg.url, host: pg.host, hits: pg.hits.map((h) => h.query), ...r }); console.log('ok', pg.url, r.items.length);
      } catch (e) { console.log('ERR', pg.url); }
      await p.close().catch(() => {});
    }
  }));
  await b.close();
  fs.writeFileSync(path.join(DIR, 'prices.json'), JSON.stringify(out, null, 1));
})();
