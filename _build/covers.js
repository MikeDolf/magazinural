const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [dir, root] = process.argv.slice(2);
  const items = JSON.parse(fs.readFileSync(dir + '/covers.json', 'utf8'));
  const svg = fs.readFileSync(root + '/favicon.svg', 'utf8');
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
  for (const it of items) {
    const big = it.h1.length > 70 ? 50 : it.h1.length > 48 ? 58 : 66;
    fs.writeFileSync(root + '/_cover.html', `<meta charset=utf-8><style>
@font-face{font-family:G;src:url(assets/fonts/golos-cyrillic.woff2)}
*{margin:0;box-sizing:border-box}
body{width:1200px;height:630px;background:#6c381a;font-family:G;color:#fff;padding:56px 72px;display:flex;flex-direction:column;justify-content:space-between}
.top{display:flex;align-items:center;gap:16px;font-size:30px;font-weight:700}.top svg{width:56px;height:56px}
.card{background:#fff;color:#302017;border-radius:6px;padding:36px 46px 40px;border-left:10px solid #f8ac3d}
.lab{font-size:20px;letter-spacing:.12em;text-transform:uppercase;color:#6e584c;margin-bottom:16px}
h1{font-size:${big}px;line-height:1.08;letter-spacing:-.01em;font-weight:750}
.bar{font-size:22px;letter-spacing:.12em;text-transform:uppercase;color:#e4d1b8}</style>
<div class="top">${svg}<span>Магазин Урал</span></div>
<div class="card"><div class="lab">Статья · ${esc(it.sec)}</div><h1>${esc(it.h1)}</h1></div>
<div class="bar">Деревянные постройки · Екатеринбург и пригороды</div>`);
    await p.goto('file://' + root + '/_cover.html');
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: `${root}/assets/img/stati/${it.slug}.jpg`, type: 'jpeg', quality: 82 });
  }
  fs.unlinkSync(root + '/_cover.html');
  await b.close();
})();
