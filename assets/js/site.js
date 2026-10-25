// Форма заявки и «Перезвоните мне»: проверка полей и отправка на Worker из <meta name="form-endpoint">.
// Пока адреса нет, честно пишем, что приём не подключён.
const endpoint = (document.querySelector('meta[name="form-endpoint"]') || {}).content;
const formKey = (document.querySelector('meta[name="form-key"]') || {}).content;  // Web3Forms
// Цели Метрики: идентификатор счётчика — в <html data-ym>.
const goal = (name, params) => { const id = +document.documentElement.dataset.ym; if (id && window.ym) window.ym(id, "reachGoal", name, params); };
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("a, [data-callback]");
  if (!a) return;
  if (a.matches("[data-callback]")) goal("callback_open");
  else if ((a.getAttribute("href") || "").startsWith("tel:")) goal("tel_click");
  else if ((a.getAttribute("href") || "").includes("max.ru")) goal("max_click");
});

document.querySelectorAll("[data-form]").forEach((form) => {
  const phone = form.elements.phone;
  const agree = form.elements.agree;
  const err = form.querySelector(".field__err");
  const status = form.querySelector(".form__status");

  const phoneOk = () => phone.value.replace(/\D/g, "").length >= 10;

  phone.addEventListener("input", () => {
    if (phone.getAttribute("aria-invalid") === "true" && phoneOk()) {
      phone.removeAttribute("aria-invalid");
      err.hidden = true;
    }
  });
  agree.addEventListener("change", () => agree.closest(".agree").classList.toggle("is-invalid", !agree.checked));

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    let ok = true;
    if (!phoneOk()) {
      phone.setAttribute("aria-invalid", "true");
      err.hidden = false;
      ok = false;
    }
    agree.closest(".agree").classList.toggle("is-invalid", !agree.checked);
    if (!agree.checked) ok = false;
    if (!ok) {
      (phoneOk() ? agree : phone).focus();
      return;
    }
    status.hidden = false;
    status.classList.remove("is-ok");
    if (!endpoint) {
      status.textContent = "Приём заявок подключим перед запуском сайта. Сейчас заявка никуда не отправлена.";
      goal("zayavka_try", { page: location.pathname });
      return;
    }
    const data = Object.fromEntries([...new FormData(form)].filter(([k]) => k !== "agree"));
    data.page = location.href;
    data.title = document.title;
    if (formKey) {
      if (data.website) return;  // ловушка для ботов заполнена — молча не отправляем
      delete data.website;
      Object.assign(data, { access_key: formKey, subject: `Заявка с magazinural.ru: ${data.type || "постройка"}`, from_name: "magazinural.ru" });
    }
    const btn = form.querySelector("[type=submit]");
    btn.disabled = true;
    status.textContent = "Отправляем…";
    fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(data) })
      .then((r) => r.json().catch(() => ({})).then((j) => { if (!r.ok || j.success === false) throw new Error(r.status); }))
      .then(() => {
        status.classList.add("is-ok");
        goal("zayavka", { type: data.type || "", page: location.pathname });
        status.textContent = "Заявка отправлена. Скоро перезвоним.";
        form.reset();
        const dlg = form.closest("dialog");
        if (dlg) setTimeout(() => dlg.close(), 2500);
      })
      .catch(() => { status.textContent = "Не получилось отправить. Проверьте интернет и попробуйте ещё раз."; })
      .finally(() => { btn.disabled = false; });
  });
});

// «Хочу такую же» в паспорте: подставляем объект в поле пожеланий.
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-object]");
  if (!a) return;
  const note = document.querySelector("[data-form] textarea[name=note]");
  if (!note) return;
  // Подставляем, если поле пустое или заполнено нами же раньше; текст, который человек написал сам, не трогаем.
  if (!note.value || note.dataset.auto === note.value) {
    note.value = `Как объект «${a.dataset.object}»`;
    note.dataset.auto = note.value;
  }
});

// «Рассчитать 3×4» в популярных размерах: подставляем размер в форму, если человек не вписал свой.
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-size]");
  if (!a) return;
  const size = document.querySelector("[data-form] input[name=size]");
  if (size && (!size.value || size.dataset.auto === size.value)) {
    size.value = a.dataset.size;
    size.dataset.auto = size.value;
  }
});

// Меню разделов: на широком экране всегда раскрыто, на узком — закрывается по клику вне и по Esc.
const nav = document.querySelector(".nav");
if (nav) {
  const wide = matchMedia("(min-width: 1241px)");
  const sync = () => { nav.open = wide.matches; };
  sync();
  wide.addEventListener("change", sync);
  document.addEventListener("click", (ev) => { if (!wide.matches && nav.open && !nav.contains(ev.target)) nav.open = false; });
  document.addEventListener("keydown", (ev) => { if (!wide.matches && ev.key === "Escape" && nav.open) { nav.open = false; nav.querySelector("summary").focus(); } });
}

// «Где поставить постройку»: выбор постройки показывает её паспорт места.
document.querySelectorAll(".norms").forEach((box) => {
  const cards = box.querySelectorAll("[data-norm]");
  box.addEventListener("change", (ev) => {
    if (ev.target.name !== "norm") return;
    cards.forEach((c) => { c.hidden = c.dataset.norm !== ev.target.value; });
  });
});

// Окна: меню, «Перезвоните мне», «Написать в MAX», квиз. Открытое окно закрываем, прежде чем открыть другое.
// Закрытие с анимацией: класс is-closing, по окончании — close(). Пока окно открыто, страница под ним не прокручивается.
const reduce = matchMedia("(prefers-reduced-motion: reduce)");
// dialog.close() (его зовёт и общий обработчик форм) закрывает с анимацией; настоящее закрытие — d._close().
document.querySelectorAll("dialog").forEach((d) => { d._close = d.close.bind(d); d.close = () => closeDlg(d); });
const closeDlg = (d) => {
  if (!d.open || d.classList.contains("is-closing")) return;
  if (reduce.matches) { d._close(); return; }
  d.classList.add("is-closing");
  let done = false;
  const fin = () => { if (done) return; done = true; d.classList.remove("is-closing"); d._close(); };
  d.addEventListener("animationend", fin, { once: true });
  setTimeout(fin, 400);  // если анимация не запустилась
};
const dlgOpen = (id) => {
  const d = document.getElementById(id);
  if (!d || typeof d.showModal !== "function") return null;
  document.querySelectorAll("dialog[open]").forEach((x) => { x.classList.remove("is-closing"); x._close(); });
  d.showModal();
  document.documentElement.classList.add("has-dlg");
  return d;
};
document.querySelectorAll("dialog").forEach((d) => {
  d.addEventListener("click", (ev) => {
    if (ev.target === d || ev.target.closest("[data-dialog-close], [data-callback-close]")) closeDlg(d);
  });
  d.addEventListener("cancel", (ev) => { ev.preventDefault(); closeDlg(d); });  // Esc — тоже с анимацией
  d.addEventListener("close", () => { if (!document.querySelector("dialog[open]")) document.documentElement.classList.remove("has-dlg"); });
});
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-callback], [data-max], [data-quiz], [data-menu]");
  if (!b) return;
  if (b.matches("[data-menu]")) {
    if (!dlgOpen("menu")) location.href = "/#razdely";
  } else if (b.matches("[data-callback]")) {
    const d = dlgOpen("callback");
    if (d) d.querySelector("input[name=name]").focus();
    else location.href = document.getElementById("zayavka") ? "#zayavka" : "/#zayavka";  // старые браузеры без <dialog>
  } else if (b.matches("[data-max]")) {
    goal("max_open");
    if (!dlgOpen("max")) window.open(document.querySelector(".btn--max").href, "_blank", "noopener");
  } else {
    goal("quiz_open", { page: location.pathname });
    if (window.CALC && quiz && dlgOpen("quiz")) quiz(b.dataset.quiz);
    else location.href = "/kalkulyator/" + (b.dataset.quiz ? `?type=${b.dataset.quiz}` : "");
  }
});
// Меню: отмечаем текущий раздел; ссылка-якорь на этой же странице закрывает меню.
const menu = document.getElementById("menu");
if (menu) {
  menu.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href");
    if (href !== "/" && location.pathname.startsWith(href)) a.setAttribute("aria-current", "page");
    a.addEventListener("click", () => { if (href.includes("#")) closeDlg(menu); });
  });
}

// Шапка: тень и компактная высота после начала прокрутки.
const topBar = document.querySelector(".top");
if (topBar) {
  const onTop = () => topBar.classList.toggle("is-scrolled", scrollY > 8);
  addEventListener("scroll", onTop, { passive: true });
  onTop();
}

// Блоки плавно появляются при прокрутке (только то, что ниже первого экрана; без JS и при reduced-motion всё видно сразу).
if ("IntersectionObserver" in window && !reduce.matches) {
  const sel = ".passport, .ocards > li, .size, .adv > li, .dir__item, .cards4 > li, .facts > li, .howto__card, .faq__item, .steps, .lead__in, .author, .calc__form, .calc__result, .related li, .post__cover, .toc";
  const io = new IntersectionObserver((list) => list.forEach((en) => {
    if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
  }), { rootMargin: "0px 0px -6% 0px" });
  document.querySelectorAll(sel).forEach((el) => {
    if (el.closest("dialog")) return;
    if (el.getBoundingClientRect().top < innerHeight * 0.95) return;
    const sib = [...el.parentElement.children].indexOf(el);
    el.style.setProperty("--d", `${(sib % 4) * 70}ms`);
    el.classList.add("rv");
    io.observe(el);
  });
}

// Плавающая кнопка MAX: появляется, когда первый экран прокручен.
const fab = document.querySelector(".fab");
if (fab) {
  const onScroll = () => fab.classList.toggle("is-on", scrollY > 500);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

// ---------- калькулятор и квиз «Рассчитать стоимость» ----------
// Данные — window.CALC из calc-data.js (собирается из _build/data/calc.py). Цена всегда примерная: вилка по средним ценам рынка.
const C = window.CALC;
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const rub = (n) => n.toLocaleString("ru-RU") + " ₽";
const r5 = (v) => Math.round(v / 5000) * 5000;
const areaOf = (t, size) => t.unit === "area" ? +size : size.split("×").reduce((a, x) => a * parseFloat(x.replace(",", ".")), 1);
// Цена базовой комплектации по опорным точкам — та же формула, что calc_base() в build.py.
const basePrice = (t, a) => {
  const p = t.points, n = p.length;
  let v;
  if (a <= p[0][0]) v = a * p[0][1] / p[0][0];
  else if (a >= p[n - 1][0]) v = p[n - 1][1] + (a - p[n - 1][0]) * (p[n - 1][1] - p[n - 2][1]) / (p[n - 1][0] - p[n - 2][0]);
  else for (let i = 1; i < n; i++) if (a <= p[i][0]) { v = p[i - 1][1] + (a - p[i - 1][0]) * (p[i][1] - p[i - 1][1]) / (p[i][0] - p[i - 1][0]); break; }
  return Math.max(t.min, v);
};
const estimate = (st) => {
  const a = areaOf(st.t, st.size);
  let k = 1, add = 0;
  st.t.options.forEach((g, i) => { const o = g.items[st.opt[i] || 0]; k *= o.k || 1; add += (o.add || 0) + (o.m2 || 0) * a; });
  const v = basePrice(st.t, a) * k + add;
  return [r5(v * C.range[0]), r5(v * C.range[1])];
};
const sizeText = (st) => st.t.unit === "area" ? `${st.size} м²` : `${st.size} м`;
const summary = (st) => [`${st.t.name} ${sizeText(st)}`, ...st.t.options.map((g, i) => `${g.name}: ${g.items[st.opt[i] || 0].name}`)].join("; ");
const sumText = (st) => { const [lo, hi] = estimate(st); return `${lo.toLocaleString("ru-RU")} – ${rub(hi)}`; };
const newState = (key) => {
  const t = (C.types.find((x) => x.key === key) || C.types[0]);
  return { t, size: t.sizes[t.sizes.length > 2 ? 1 : 0], custom: false, opt: t.options.map(() => 0), place: 0, when: 0 };
};

// Разметка групп: радиокнопки-плитки и «чипы» (работают с клавиатуры), имена полей уникальны для каждого виджета.
let uid = 0;
const chips = (name, legend, items, cur, extra = "") =>
  `<fieldset class="calc__group"><legend>${esc(legend)}</legend><div class="chips">` +
  items.map((x, i) => `<label class="chip"><input type="radio" name="${name}" value="${i}"${i === cur ? " checked" : ""}><span>${esc(x)}</span></label>`).join("") +
  `</div>${extra}</fieldset>`;
const typesHTML = (id, st, none) =>
  `<fieldset class="calc__group"><legend>Что строим</legend><div class="calc__types">` +
  C.types.map((t) => `<label class="ctile"><input type="radio" name="${id}-type" value="${t.key}"${t === st.t && !none ? " checked" : ""}>` +
    `<img src="${t.img}" alt="" width="360" height="240" loading="lazy" decoding="async"><span class="ctile__t">${esc(t.name)}</span>` +
    `<span class="ctile__p">от ${rub(t.from)}</span></label>`).join("") + `</div></fieldset>`;
const sizeHTML = (id, st) => {
  const t = st.t, labels = t.sizes.map((s) => t.unit === "area" ? `${s} м²` : `${s} м`);
  const cur = st.custom ? t.sizes.length : t.sizes.indexOf(st.size);
  const [w, l] = st.custom ? st.size.split("×") : (t.unit === "area" ? ["", ""] : st.size.split("×"));
  const custom = t.custom ? `<div class="calc__custom"${st.custom ? "" : " hidden"}>` +
    `<label class="field"><span>Ширина, м</span><input type="number" name="${id}-w" min="1" max="20" step="0.5" value="${esc(w)}" inputmode="decimal"></label>` +
    `<span aria-hidden="true">×</span><label class="field"><span>Длина, м</span><input type="number" name="${id}-l" min="1" max="30" step="0.5" value="${esc(l)}" inputmode="decimal"></label></div>` : "";
  return chips(`${id}-size`, t.unit === "area" ? "Площадь дома" : "Размер", t.custom ? [...labels, "Свой размер"] : labels, cur, custom);
};
const optsHTML = (id, st) => st.t.options.map((g, i) => chips(`${id}-o${i}`, g.name, g.items.map((x) => x.name), st.opt[i] || 0)).join("");
const placeHTML = (id, st) => chips(`${id}-place`, "Где участок", C.places, st.place) + chips(`${id}-when`, "Когда строить", C.when, st.when);
const resultHTML = (st) =>
  `<p class="calc__label">Примерная стоимость</p><p class="calc__sum">≈ ${sumText(st)}</p>` +
  `<p class="calc__what">${esc(summary(st))}</p><p class="calc__note">${esc(C.note)}</p>`;

// Изменение любого поля → состояние. Возвращает true, если сменилась постройка (тогда перерисовываем размеры и опции).
const readField = (id, st, el) => {
  const n = el.name.slice(id.length + 1);
  if (n === "type") { Object.assign(st, newState(el.value)); return true; }
  if (n === "size") {
    const i = +el.value;
    st.custom = i >= st.t.sizes.length;
    const box = el.closest(".calc__group").querySelector(".calc__custom");
    if (box) box.hidden = !st.custom;
    if (!st.custom) st.size = st.t.sizes[i];
    else readCustom(id, st, el.closest(".calc__group"));
  } else if (n === "w" || n === "l") readCustom(id, st, el.closest(".calc__group"));
  else if (n[0] === "o") st.opt[+n.slice(1)] = +el.value;
  else if (n === "place" || n === "when") st[n] = +el.value;
  return false;
};
const readCustom = (id, st, box) => {
  const w = parseFloat(box.querySelector(`[name="${id}-w"]`).value), l = parseFloat(box.querySelector(`[name="${id}-l"]`).value);
  const ok = (x, max) => x >= 1 && x <= max;
  if (ok(w, 20) && ok(l, 30)) st.size = `${String(w).replace(".", ",")}×${String(l).replace(".", ",")}`;
};

// Калькулятор на странице /kalkulyator/: все поля сразу, итог пересчитывается на лету.
document.querySelectorAll('[data-calc="page"]').forEach((box) => {
  if (!C) return;
  const id = `c${uid++}`;
  const st = newState(new URLSearchParams(location.search).get("type"));
  box.innerHTML = `<div class="calc__grid"><div class="calc__form">${typesHTML(id, st)}<div class="calc__dyn"></div></div>` +
    `<aside class="calc__result" aria-live="polite"><div class="calc__res"></div>` +
    `<a class="btn btn--enamel" href="#zayavka" data-calc-apply>Получить точный расчёт</a></aside></div><p class="calc__note calc__note--page">${esc(C.note)}</p>`;
  const dyn = box.querySelector(".calc__dyn"), res = box.querySelector(".calc__res");
  const draw = () => { dyn.innerHTML = sizeHTML(id, st) + optsHTML(id, st); };
  const show = () => { res.innerHTML = resultHTML(st); };
  draw(); show();
  let used = false;
  box.addEventListener("input", (ev) => {
    if (!ev.target.name) return;
    if (readField(id, st, ev.target)) draw();
    show();
    if (!used) { used = true; goal("calc_use"); }
  });
  // «Получить точный расчёт»: переносим выбор в форму заявки, текст, который человек написал сам, не трогаем.
  box.querySelector("[data-calc-apply]").addEventListener("click", () => {
    const f = document.querySelector("#zayavka [data-form]");
    if (!f) return;
    const type = f.elements.type, size = f.elements.size, note = f.elements.note;
    const opt = [...type.options].find((o) => o.value === st.t.section);
    if (opt) type.value = opt.value;
    if (size && (!size.value || size.dataset.auto === size.value)) { size.value = sizeText(st); size.dataset.auto = size.value; }
    if (note && (!note.value || note.dataset.auto === note.value)) { note.value = `${summary(st)}. Калькулятор: примерно ${sumText(st)}`; note.dataset.auto = note.value; }
  });
});

// Квиз в окне: 5 шагов, в конце — примерная цена и форма заявки (общая отправка выше).
const quizBox = document.querySelector('[data-calc="quiz"]');
const quiz = quizBox && C ? (() => {
  const id = `q${uid++}`, dlg = quizBox.closest("dialog"), form = dlg.querySelector(".quiz__form"), bar = dlg.querySelector(".quiz__bar span");
  const STEPS = [["Что будем строить?", (i, s) => typesHTML(i, s, true)], ["Какой размер?", sizeHTML], ["Комплектация", optsHTML], ["Где и когда?", placeHTML]];
  let st, step;
  const render = () => {
    const last = step === STEPS.length;
    bar.style.width = `${((step + 1) / (STEPS.length + 1)) * 100}%`;
    form.hidden = !last;
    if (last) {
      quizBox.innerHTML = `<p class="quiz__step">Шаг ${step + 1} из ${STEPS.length + 1}: ваш расчёт</p><div class="calc__result calc__result--quiz">${resultHTML(st)}</div>`;
      const el = form.elements;
      el.type.value = `${st.t.name} — расчёт в квизе`;
      el.size.value = sizeText(st);
      el.place.value = C.places[st.place];
      el.when.value = C.when[st.when];
      el.note.value = summary(st);
      el.estimate.value = `примерно ${sumText(st)}`;
      goal("quiz_result", { type: st.t.key });
      el.phone.focus();
      return;
    }
    const [h, fn] = STEPS[step];
    quizBox.innerHTML = `<p class="quiz__step">Шаг ${step + 1} из ${STEPS.length + 1}</p><h3 class="quiz__h">${h}</h3><div class="quiz__body">${fn(id, st)}</div>` +
      `<div class="quiz__nav">${step ? '<button class="btn btn--ghost" type="button" data-q="-1">Назад</button>' : ""}` +
      `${step ? '<button class="btn btn--frame" type="button" data-q="1">Далее</button>' : ""}</div>`;
    const first = quizBox.querySelector("input:checked") || quizBox.querySelector("input");
    if (first) first.focus();
  };
  quizBox.addEventListener("input", (ev) => {
    if (!ev.target.name) return;
    readField(id, st, ev.target);
    if (step === 0) { step = 1; render(); }  // выбрали постройку — сразу к размерам
  });
  quizBox.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-q]");
    if (b) { step += +b.dataset.q; render(); }
  });
  form.querySelector("[data-calc-back]").addEventListener("click", () => { step = STEPS.length - 1; render(); });
  return (key) => {
    st = newState(key);
    step = key && C.types.some((t) => t.key === key) ? 1 : 0;
    form.querySelector(".form__status").hidden = true;
    render();
  };
})() : null;

// Этапы работы: вкладки с клавиатурой (стрелки), без JS все этапы видны подряд.
document.querySelectorAll("[data-steps]").forEach((box) => {
  const tabs = [...box.querySelectorAll("[role=tab]")];
  const show = (i, focus) => {
    tabs.forEach((t, n) => {
      const on = n === i;
      t.setAttribute("aria-selected", on);
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
    if (focus) tabs[i].focus();
  };
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => show(i));
    t.addEventListener("keydown", (ev) => {
      const d = { ArrowRight: 1, ArrowLeft: -1 }[ev.key];
      if (d) { ev.preventDefault(); show((i + d + tabs.length) % tabs.length, true); }
    });
  });
  show(0);
});

// «Показать все» в каталоге раздела: карточки уже в HTML, просто открываем скрытые.
document.querySelectorAll("[data-more-btn]").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".grid[data-more] .is-more").forEach((c) => c.classList.remove("is-more"));
  b.closest(".more").remove();
}));

// Оглавление статьи: на широком экране — раскрытая колонка справа, на телефоне — свёрнуто; переход по пункту сворачивает.
document.querySelectorAll("[data-toc]").forEach((t) => {
  const wide = matchMedia("(min-width: 1100px)");
  const sync = () => { t.open = wide.matches; };
  sync();
  wide.addEventListener("change", sync);
  t.addEventListener("click", (ev) => { if (ev.target.closest("a") && !wide.matches) t.open = false; });
});
