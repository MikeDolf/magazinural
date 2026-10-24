// Cloudflare Worker: принимает заявки с magazinural.ru и пересылает в Telegram.
// Настройка — docs/zayavki-telegram.md. Секреты задаются в панели Cloudflare, в коде их нет:
//   TG_BOT_TOKEN — токен бота от @BotFather;
//   TG_CHAT_ID   — id чата, куда слать заявки (личный чат или группа).

const ORIGINS = ["https://magazinural.ru", "https://www.magazinural.ru"];
const FIELDS = [
  ["type", "Что строим"], ["size", "Размер"], ["place", "Где участок"], ["when", "Когда"],
  ["note", "Что важно"], ["name", "Имя"], ["phone", "Телефон"],
];

const cors = (origin) => ({
  "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Vary": "Origin",
});

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (request.method === "OPTIONS") return new Response(null, { headers: cors(origin) });
    if (request.method !== "POST" || !ORIGINS.includes(origin)) return new Response("Forbidden", { status: 403 });

    let data;
    try {
      data = await request.json();
    } catch {
      return new Response("Bad request", { status: 400, headers: cors(origin) });
    }
    const clean = (v) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, 500);
    // Ловушка для ботов: человек это поле не видит. Отвечаем «ок», чтобы бот не пробовал снова.
    if (clean(data.website)) return new Response("ok", { headers: cors(origin) });
    if (clean(data.phone).replace(/\D/g, "").length < 10) return new Response("Phone required", { status: 422, headers: cors(origin) });

    const lines = ["Новая заявка с magazinural.ru"];
    for (const [k, label] of FIELDS) if (clean(data[k])) lines.push(`${label}: ${clean(data[k])}`);
    if (clean(data.page)) lines.push(`Страница: ${clean(data.page)}`);

    const tg = await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: env.TG_CHAT_ID, text: lines.join("\n"), disable_web_page_preview: true }),
    });
    return new Response(tg.ok ? "ok" : "Telegram error", { status: tg.ok ? 200 : 502, headers: cors(origin) });
  },
};
