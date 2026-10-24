// Форма заявки и «Перезвоните мне»: проверка полей и отправка на Worker из <meta name="form-endpoint">.
// Пока адреса нет, честно пишем, что приём не подключён.
const endpoint = (document.querySelector('meta[name="form-endpoint"]') || {}).content;

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
      return;
    }
    const data = Object.fromEntries([...new FormData(form)].filter(([k]) => k !== "agree"));
    data.page = location.href;
    data.title = document.title;
    const btn = form.querySelector("[type=submit]");
    btn.disabled = true;
    status.textContent = "Отправляем…";
    fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
      .then((r) => { if (!r.ok) throw new Error(r.status); })
      .then(() => {
        status.classList.add("is-ok");
        status.textContent = "Заявка отправлена. Перезвоним в рабочее время.";
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

// «Перезвоните мне»: диалог с короткой формой. Проверку и честный статус даёт общий обработчик форм выше.
const cb = document.getElementById("callback");
if (cb && typeof cb.showModal === "function") {
  document.querySelectorAll("[data-callback]").forEach((b) => b.addEventListener("click", () => {
    cb.showModal();
    cb.querySelector("input[name=name]").focus();
  }));
  cb.querySelector("[data-callback-close]").addEventListener("click", () => cb.close());
  cb.addEventListener("click", (ev) => { if (ev.target === cb) cb.close(); });
} else {
  // Старые браузеры без <dialog>: ведём к основной форме заявки.
  document.querySelectorAll("[data-callback]").forEach((b) => b.addEventListener("click", () => {
    location.hash = document.getElementById("zayavka") ? "#zayavka" : "/#zayavka";
  }));
}

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
