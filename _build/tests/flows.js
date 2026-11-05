// Сценарии: меню, окна, квиз, формы, калькуляторы, вкладки, «показать все», оглавление, справочник норм, без JS
const { chromium } = require('playwright');
const L = 'http://localhost:8765';
(async () => {
  const b = await chromium.launch(); const res = [];
  const ok = (name, cond, extra = '') => res.push((cond ? 'OK   ' : 'FAIL ') + name + (extra ? ' — ' + extra : ''));
  for (const [w, tag] of [[390, 'моб'], [1366, 'комп']]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 850 }, isMobile: w < 768, hasTouch: w < 768 });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto(L + '/besedki/', { waitUntil: 'networkidle' });
    if (w < 1300) {
      await p.click('.menu-btn'); await p.waitForTimeout(600);
      ok(`${tag}: меню открывается`, await p.$eval('#menu', d => d.open));
      ok(`${tag}: страница под меню не прокручивается`, await p.evaluate(() => document.documentElement.classList.contains('has-dlg')));
      await p.keyboard.press('Escape'); await p.waitForTimeout(500);
      ok(`${tag}: меню закрывается по Esc`, !(await p.$eval('#menu', d => d.open)));
      ok(`${tag}: прокрутка возвращается`, !(await p.evaluate(() => document.documentElement.classList.contains('has-dlg'))));
      await p.click('.menu-btn'); await p.waitForTimeout(500); await p.click('#menu .drawer__all summary'); await p.waitForTimeout(300);
      ok(`${tag}: «Все постройки» раскрываются`, await p.$eval('#menu .drawer__all', d => d.open));
      await p.mouse.click(5, 400); await p.waitForTimeout(500);
      ok(`${tag}: меню закрывается кликом по фону`, !(await p.$eval('#menu', d => d.open)));
    } else {
      ok(`${tag}: меню в шапке видно`, await p.$eval('.nav', n => getComputedStyle(n).display !== 'none' && n.open));
    }
    await p.click('.top__max'); await p.waitForTimeout(500);
    ok(`${tag}: окно MAX`, await p.$eval('#max', d => d.open));
    await p.click('#max .mxd__alt [data-callback]'); await p.waitForTimeout(600);
    ok(`${tag}: из MAX → «Перезвоните мне»`, (await p.$eval('#callback', d => d.open)) && !(await p.$eval('#max', d => d.open)));
    await p.click('#callback [type=submit]'); await p.waitForTimeout(200);
    ok(`${tag}: пустой телефон — подсказка`, await p.$eval('#cb-phone-err', e => !e.hidden));
    await p.fill('#callback input[name=phone]', '+7 900 111-22-33'); await p.click('#callback [type=submit]'); await p.waitForTimeout(200);
    ok(`${tag}: без галочки согласия — подсветка`, await p.$eval('#callback .agree', e => e.classList.contains('is-invalid')));
    await p.keyboard.press('Escape'); await p.waitForTimeout(500);
    ok(`${tag}: звонок закрывается по Esc`, !(await p.$eval('#callback', d => d.open)));
    const tel = await p.$eval('.top__phone', a => a.getAttribute('href'));
    ok(`${tag}: телефон в шапке кликабельный`, tel === 'tel:+79506460953', tel);
    await p.click('.intro__cta [data-quiz]'); await p.waitForTimeout(500);
    ok(`${tag}: квиз открылся на шаге размера`, (await p.$eval('#quiz .quiz__step', e => e.textContent)).includes('Шаг 2'));
    for (let i = 0; i < 3; i++) { await p.click('#quiz [data-q="1"]'); await p.waitForTimeout(150); }
    const sum = await p.$eval('#quiz .calc__sum', e => e.textContent).catch(() => '');
    ok(`${tag}: квиз дошёл до расчёта`, sum.includes('₽'), sum);
    ok(`${tag}: в квизе написано «примерная»`, (await p.$eval('#quiz', d => d.textContent)).includes('Цена примерная'));
    await p.click('#quiz [data-calc-back]'); await p.waitForTimeout(200);
    ok(`${tag}: в квизе можно вернуться назад`, (await p.$eval('#quiz .quiz__step', e => e.textContent)).includes('Шаг 4'));
    await p.keyboard.press('Escape'); await p.waitForTimeout(500);
    await p.evaluate(() => document.querySelector('.scalc').scrollIntoView());
    await p.locator('.scalc .chip >> text=4×4 м').dispatchEvent('click'); await p.waitForTimeout(100);
    const s2 = await p.$eval('.scalc .calc__sum', e => e.textContent);
    await p.click('.scalc [data-calc-apply]'); await p.waitForTimeout(400);
    const note = await p.$eval('#zayavka textarea[name=note]', e => e.value), size = await p.$eval('#zayavka input[name=size]', e => e.value);
    ok(`${tag}: калькулятор раздела → заявка`, note.includes('4×4') && size === '4×4 м', s2 + ' | ' + note.slice(0, 60));
    const vis = () => p.$$eval('.grid[data-more] .passport', a => a.filter(x => getComputedStyle(x).display !== 'none').length);
    const before = await vis(); await p.click('[data-more-btn]'); await p.waitForTimeout(300); const after = await vis();
    ok(`${tag}: «Показать все»`, after > before, `${before} → ${after}`);
    await p.click('.steps__tab >> nth=2'); await p.waitForTimeout(200);
    ok(`${tag}: вкладки этапов`, await p.$eval('#steps-h-p3', e => !e.hidden));
    await p.click('[data-size="3×3 м"]'); await p.waitForTimeout(300);
    ok(`${tag}: кнопка размера заполняет форму`, (await p.$eval('#zayavka input[name=size]', e => e.value)) === '3×3 м');
    await p.goto(L + '/besedki/obekt-001/', { waitUntil: 'networkidle' });
    await p.click('.intro__cta [data-object]'); await p.waitForTimeout(300);
    ok(`${tag}: «Хочу такую же» заполняет пожелания`, (await p.$eval('#zayavka textarea[name=note]', e => e.value)).includes('Зеркальце'));
    await p.goto(L + '/stati/besedka-svoimi-rukami/', { waitUntil: 'networkidle' });
    const tocOpen = await p.$eval('[data-toc]', d => d.open);
    ok(`${tag}: оглавление ${w >= 1100 ? 'раскрыто' : 'свёрнуто'}`, w >= 1100 ? tocOpen : !tocOpen);
    if (w < 1100) {
      await p.click('[data-toc] summary'); await p.click('[data-toc] a >> nth=2'); await p.waitForTimeout(600);
      ok(`${tag}: переход по оглавлению сворачивает его`, !(await p.$eval('[data-toc]', d => d.open)));
    }
    await p.goto(L + '/gde-postavit-postroyku/', { waitUntil: 'networkidle' });
    const radios = await p.$$('.norms input[name=norm]');
    if (radios.length > 1) {
      await radios[1].check({ force: true }); await p.waitForTimeout(200);
      ok(`${tag}: справочник норм переключается`, await p.$$eval('[data-norm]', a => a.filter(x => !x.hidden).length === 1));
    }
    await p.goto(L + '/kalkulyator/', { waitUntil: 'networkidle' });
    await p.locator('[data-calc="page"] .chip >> text=Свой размер').first().dispatchEvent('click');
    await p.fill('[data-calc="page"] input[name$="-w"]', '5'); await p.fill('[data-calc="page"] input[name$="-l"]', '7'); await p.waitForTimeout(200);
    ok(`${tag}: калькулятор — свой размер 5×7`, (await p.$eval('[data-calc="page"]', e => e.textContent)).includes('5×7'));
    ok(`${tag}: ошибок скриптов нет`, errs.length === 0, errs.join('; '));
    await ctx.close();
  }
  const nj = await b.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 850 } }); const q = await nj.newPage();
  await q.goto(L + '/besedki/');
  ok('без JS: все карточки видны', await q.$$eval('.passport', a => a.every(x => getComputedStyle(x).display !== 'none' && getComputedStyle(x).opacity !== '0')));
  ok('без JS: все этапы видны', await q.$$eval('.steps__panel', a => a.every(x => !x.hidden)));
  await q.goto(L + '/kalkulyator/');
  ok('без JS: калькулятор объясняет, что делать', (await q.content()).includes('Калькулятору нужен JavaScript'));
  console.log(res.join('\n')); await b.close();
})();
