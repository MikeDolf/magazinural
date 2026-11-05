// Глубокая проверка: типовые страницы × ширины экрана
const { chromium } = require('playwright');
const pages = ['/', '/besedki/', '/besedki/dlya-dachi/', '/besedki/berezovskiy/', '/besedki/obekt-001/', '/bani/proekt-p23/', '/postroyki-dlya-zhivotnyh/proekt-k01/',
  '/stati/besedka-svoimi-rukami/', '/stati/', '/kalkulyator/', '/ceny/', '/kontakty/', '/o-kompanii/', '/o-kompanii/nikulov/', '/nashi-raboty/', '/proekty/',
  '/gde-postavit-postroyku/', '/voprosy-i-otvety/', '/garantiya/', '/karta-sayta/', '/gorki/', '/404.html'];
const widths = [360, 390, 768, 1024, 1366, 1920];
(async () => {
  const b = await chromium.launch(); const issues = [];
  for (const w of widths) {
    const ctx = await b.newContext({ viewport: { width: w, height: 800 }, isMobile: w < 768, hasTouch: w < 1024 });
    for (const u of pages) {
      const p = await ctx.newPage(); const errs = [];
      p.on('pageerror', e => errs.push('JS: ' + e.message)); p.on('console', m => { if (m.type() === 'error' && !/mc\.yandex|metrika|ERR_|net::/i.test(m.text())) errs.push('console: ' + m.text()); });
      p.on('requestfailed', r => { if (r.url().includes('localhost')) errs.push('fail ' + r.url()); });
      p.on('response', r => { if (r.url().includes('localhost') && r.status() >= 400 && !r.url().endsWith('404.html') && !r.url().includes('favicon')) errs.push(r.status() + ' ' + r.url()); });
      await p.addInitScript(() => { window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); });
      await p.goto('http://localhost:8765' + u, { waitUntil: 'networkidle' });
      // прокрутка до низа, чтобы сработали появления и lazy
      await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 500) { scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } scrollTo(0, document.body.scrollHeight); });
      await p.waitForTimeout(1200);
      const r = await p.evaluate((w) => {
        const out = [];
        if (document.documentElement.scrollWidth > innerWidth + 1) out.push('горизонтальная прокрутка ' + document.documentElement.scrollWidth);
        const imgs = [...document.querySelectorAll('img')].filter(i => !i.closest('dialog') && i.complete && i.naturalWidth === 0 && i.getAttribute('src') && !i.src.includes('mc.yandex'));
        if (imgs.length) out.push('битые картинки: ' + imgs.slice(0, 3).map(i => i.getAttribute('src')).join(', '));
        const hidden = [...document.querySelectorAll('.rv:not(.in)')]; if (hidden.length) out.push('не проявились при прокрутке: ' + hidden.length);
        if (w < 768) {
          const small = [...document.querySelectorAll('a, button, input, select, summary')].filter(el => {
            if (el.closest('dialog') || el.closest('.crumbs') || el.closest('p, li, td, figcaption, .foot__contacts, .foot__req') && el.tagName === 'A' && !el.classList.contains('btn')) return false;
            const s = getComputedStyle(el); if (s.display === 'none' || s.visibility === 'hidden' || el.type === 'hidden' || el.closest('.hp')) return false;
            const rc = el.getBoundingClientRect(); if (!rc.width) return false;
            return (rc.height < 36 || rc.width < 36) && !(el.type === 'checkbox' || el.type === 'radio');
          });
          if (small.length) out.push('мелкие элементы (<36px): ' + small.slice(0, 4).map(e => e.tagName + '.' + (e.className || '') + '«' + (e.textContent || '').trim().slice(0, 20) + '»').join(' | '));
        }
        const h = document.querySelectorAll('h1'); if (h.length !== 1 && !location.pathname.endsWith('404.html')) out.push('h1: ' + h.length);
        out.push('CLS=' + window.__cls.toFixed(3));
        return out;
      }, w);
      const cls = parseFloat(r.pop().split('=')[1]); if (cls > 0.1) r.push('сдвиг вёрстки CLS ' + cls.toFixed(3));
      const all = [...errs, ...r]; if (all.length) issues.push(`${w} ${u}: ${all.join(' ; ')}`);
      await p.close();
    }
    await ctx.close();
  }
  console.log(issues.length ? issues.join('\n') : 'проблем не найдено'); await b.close();
})();
