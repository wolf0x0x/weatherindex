(function () {
  "use strict";

  const LANG_CODES = ["en", "zh", "es", "fr", "de", "ja", "ru", "kr", "ar"];
  const LANG_NAMES = { en: "English", zh: "中文", es: "Español", fr: "Français", de: "Deutsch", ja: "日本語", ru: "Русский", kr: "한국어", ar: "العربية" };
  const LANG_FLAGS = { en: "🇺🇸", zh: "🇨🇳", es: "🇪🇸", fr: "🇫🇷", de: "🇩🇪", ja: "🇯🇵", ru: "🇷🇺", kr: "🇰🇷", ar: "🇸🇦" };
  const qs = new URLSearchParams(location.search);

  const searchInputs = document.querySelectorAll("[data-search-input]");
  const goSearch = (value) => {
    const q = value.trim();
    if (q) location.href = `${rootPrefix()}search.html?q=${encodeURIComponent(q)}`;
  };
  searchInputs.forEach((input) => input.addEventListener("keydown", (e) => { if (e.key === "Enter") goSearch(input.value); }));

  document.querySelectorAll("[data-locate]").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const data = await locateByIp();
      if (data.city) goSearch(data.city);
    } catch (error) {
      button.disabled = false;
    } finally {
      button.disabled = false;
    }
  }));

  const resultInput = document.querySelector("[data-results-search]");
  if (resultInput) {
    resultInput.value = qs.get("q") || "";
    const cards = [...document.querySelectorAll(".result-card")];
    const count = document.querySelector(".result-count");
    const empty = document.querySelector(".empty-state");
    let timer = 0;
    const filter = () => {
      const q = resultInput.value.trim().toLowerCase();
      let shown = 0;
      cards.forEach((card) => {
        const ok = !q || card.dataset.city.includes(q);
        card.style.display = ok ? "" : "none";
        if (ok) shown += 1;
      });
      if (count) count.textContent = q ? `${shown} indexed results` : `${shown} indexed cities`;
      if (empty) empty.style.display = shown ? "none" : "block";
      clearTimeout(timer);
      timer = setTimeout(() => liveLookup(q, shown), 500);
    };
    resultInput.addEventListener("input", filter);
    filter();
  }

  document.querySelectorAll("[data-clock]").forEach((el) => {
    const update = () => { el.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); };
    update();
    setInterval(update, 1000);
  });

  document.querySelectorAll("[data-share]").forEach((button) => button.addEventListener("click", async () => {
    if (navigator.share) await navigator.share({ title: document.title, url: location.href });
    else await navigator.clipboard.writeText(location.href);
  }));

  document.querySelectorAll("[data-lang-switch]").forEach((btn) => btn.addEventListener("click", (e) => {
    e.preventDefault();
    openLanguageModal(btn.dataset.langTitle || LANG_NAMES.en);
  }));

  function openLanguageModal(title) {
    const existing = document.getElementById("wx-lang-modal");
    if (existing) existing.remove();
    const overlay = document.createElement("div");
    overlay.id = "wx-lang-modal";
    overlay.className = "fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4";
    overlay.innerHTML = `<div class="bg-white rounded-2xl shadow-xl max-w-md w-full p-6"><div class="flex justify-between items-center mb-4"><h2 class="text-lg font-bold text-slate-800">🌐 ${escapeHtml(title)}</h2><button id="wx-close-lang" class="text-slate-400 hover:text-slate-600 text-2xl leading-none">&times;</button></div><div class="grid grid-cols-1 gap-2 max-h-[60vh] overflow-y-auto">${LANG_CODES.map((code) => `<button data-lang="${code}" class="wx-lang-option flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-blue-50 text-left transition"><span class="text-xl">${LANG_FLAGS[code]}</span><span class="font-medium text-slate-700">${LANG_NAMES[code]}</span></button>`).join("")}</div></div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (e) => { if (e.target === overlay || e.target.id === "wx-close-lang") overlay.remove(); });
    overlay.querySelectorAll(".wx-lang-option").forEach((opt) => opt.addEventListener("click", () => { overlay.remove(); switchToLanguage(opt.dataset.lang); }));
  }

  function switchToLanguage(lang) {
    const repo = location.pathname.startsWith("/weatherindex/") ? "/weatherindex" : "";
    const rest = repo ? location.pathname.slice(repo.length) : location.pathname;
    const parts = rest.split("/").filter(Boolean);
    if (LANG_CODES.includes(parts[0])) parts[0] = lang;
    else parts.unshift(lang);
    location.href = `${repo}/${parts.join("/")}${location.search}${location.hash}`;
  }

  (function autoRedirect() {
    if (qs.has("noredir") || sessionStorage.getItem("wx_redirected")) return;
    const path = location.pathname;
    const isRoot = path === "/" || path.endsWith("/index.html");
    if (!isRoot || LANG_CODES.some((c) => path.includes(`/${c}/`))) return;
    sessionStorage.setItem("wx_redirected", "1");
    locateByIp().then((data) => {
      const map = { CN: "zh", US: "en", GB: "en", ES: "es", FR: "fr", DE: "de", JP: "ja", RU: "ru", KR: "kr", SA: "ar", AE: "ar", EG: "ar" };
      const lang = map[data.countryCode || data.country_code] || "en";
      if (lang !== "en") switchToLanguage(lang);
    }).catch(() => {});
  })();

  async function locateByIp() {
    const providers = [
      async () => { const r = await fetch("https://ipapi.co/json/"); const d = await r.json(); return { city: d.city, countryCode: d.country_code }; },
      async () => { const r = await fetch("https://ipinfo.io/json"); const d = await r.json(); return { city: d.city, countryCode: d.country }; },
      async () => { const r = await fetch("https://ipwho.is/"); const d = await r.json(); return { city: d.city, countryCode: d.country_code }; },
      async () => { const r = await fetch("https://iplocate.io/api/lookup/"); const d = await r.json(); return { city: d.city, countryCode: d.country_code }; },
    ];
    for (const provider of providers) {
      try { const data = await provider(); if (data.city || data.countryCode) return data; } catch (error) {}
    }
    throw new Error("IP location unavailable");
  }

  async function liveLookup(query, indexedCount) {
    const box = document.querySelector("[data-live-lookup]");
    const list = document.querySelector(".live-results");
    if (!box || !list || !query || query.length < 3 || indexedCount > 0) {
      if (box) box.classList.add("hidden");
      return;
    }
    box.classList.remove("hidden");
    list.innerHTML = `<p class="text-sm text-slate-400">Loading live weather…</p>`;
    try {
      const geo = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=3&q=${encodeURIComponent(query)}`, { headers: { "Accept-Language": document.documentElement.lang || "en" } });
      const places = await geo.json();
      if (!Array.isArray(places) || !places.length) { list.innerHTML = ""; return; }
      const rows = await Promise.all(places.slice(0, 3).map(async (place) => {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${encodeURIComponent(place.lat)}&longitude=${encodeURIComponent(place.lon)}&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m&timezone=auto`;
        const res = await fetch(url);
        const weather = await res.json();
        const current = weather.current || {};
        return `<div class="p-4 rounded-xl border border-slate-100"><h3 class="font-semibold text-slate-800">${escapeHtml(place.display_name)}</h3><p class="text-blue-600 font-semibold mt-1">${current.temperature_2m ?? "—"}°C · ${iconFor(current.weather_code)} · ${current.wind_speed_10m ?? "—"} km/h</p><p class="text-xs text-slate-400 mt-1">Nominatim + Open-Meteo</p></div>`;
      }));
      list.innerHTML = rows.join("");
    } catch (error) {
      list.innerHTML = "";
    }
  }

  function iconFor(code) {
    const map = { 0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 61: "🌦️", 63: "🌧️", 71: "🌨️", 80: "🌦️", 95: "⛈️" };
    return map[Number(code)] || "🌤️";
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
  }

  function rootPrefix() {
    const parts = location.pathname.split("/").filter(Boolean);
    const inLang = LANG_CODES.includes(parts[0]);
    const inSub = ["city", "wiki", "alert"].includes(parts[inLang ? 1 : parts.length - 2]);
    return inSub ? "../" : "./";
  }
})();
