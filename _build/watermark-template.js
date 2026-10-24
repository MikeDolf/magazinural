const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
 const font = fs.readFileSync('assets/fonts/golos-cyrillic.woff2').toString('base64');
 const html = `<meta charset=utf-8><style>@font-face{font-family:G;src:url(data:font/woff2;base64,${font})}
 *{margin:0}body{width:1080px;height:720px;background:transparent;overflow:hidden;font-family:G}
 .w{position:absolute;left:40px;top:250px;width:1020px;height:230px;transform:rotate(-13deg);transform-origin:50% 50%;display:flex;align-items:center;gap:26px;
   color:rgba(255,255,255,.62);filter:drop-shadow(0 0 1.5px rgba(0,0,0,.55)) drop-shadow(0 2px 6px rgba(0,0,0,.35))}
 .band{position:absolute;left:-20px;top:300px;width:1120px;height:150px;transform:rotate(-13deg);background:radial-gradient(60% 70% at 50% 50%,rgba(40,25,15,.30),rgba(40,25,15,0) 75%);filter:blur(14px)}
 svg{width:190px;height:190px;flex:none}
 .t{display:flex;flex-direction:column;gap:10px}.n{white-space:nowrap;font-size:88px;font-weight:800;letter-spacing:.02em;line-height:.9;text-transform:uppercase}
 .l{height:7px;background:currentColor;border-radius:4px}.s{white-space:nowrap;font-size:32px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}</style>
 <div class=band></div>
 <div class=w><svg viewBox="0 0 64 64"><path d="M6 31 32 9l26 22" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 29v25h38V29L32 13z" fill="currentColor"/><rect x="27" y="38" width="10" height="16" rx="1.5" fill="rgba(0,0,0,.35)"/></svg>
 <div class=t><div class=n>Магазин Урал</div><div class=l></div><div class=s>строим из дерева на Урале с 2013 года</div></div></div>`;
 const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 720 } });
 await p.setContent(html); await p.evaluate(() => document.fonts.ready);
 await p.screenshot({ path: process.argv[2], omitBackground: true }); await b.close(); })();
