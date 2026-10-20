// Форма заявки: проверка полей. Отправка ещё не подключена — говорим об этом честно.
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
    status.textContent = "Приём заявок подключим перед запуском площадки. Сейчас заявка никуда не отправлена.";
  });
});

// «Заявка мастеру» в паспорте: подставляем объект в поле пожеланий.
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-object]");
  if (!a) return;
  const note = document.querySelector("[data-form] textarea[name=note]");
  if (note && !note.value) note.value = `Как объект «${a.dataset.object}»`;
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
