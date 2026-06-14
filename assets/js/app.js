(function () {
  const qs = new URLSearchParams(location.search);
  const searchInputs = document.querySelectorAll("[data-search-input]");
  const goSearch = (value) => {
    const q = value.trim();
    if (q) location.href = `${rootPrefix()}search.html?q=${encodeURIComponent(q)}`;
  };
  searchInputs.forEach((input) => input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") goSearch(input.value);
  }));

  document.querySelectorAll("[data-locate]").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const res = await fetch("https://ip-api.com/json/?fields=status,city");
      const data = await res.json();
      if (data.status === "success" && data.city) goSearch(data.city);
    } catch (error) {
      goSearch("Tokyo");
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
    const filter = () => {
      const q = resultInput.value.trim().toLowerCase();
      let shown = 0;
      cards.forEach((card) => {
        const ok = !q || card.dataset.city.includes(q);
        card.style.display = ok ? "" : "none";
        if (ok) shown += 1;
      });
      count.textContent = q ? `"${resultInput.value}" — ${shown} results found` : `${shown} cities available`;
      empty.style.display = shown ? "none" : "block";
    };
    resultInput.addEventListener("input", filter);
    filter();
  }

  document.querySelectorAll("[data-clock]").forEach((el) => {
    setInterval(() => {
      el.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }, 1000);
  });

  document.querySelectorAll("[data-share]").forEach((button) => button.addEventListener("click", async () => {
    if (navigator.share) await navigator.share({ title: document.title, url: location.href });
    else await navigator.clipboard.writeText(location.href);
  }));

  function rootPrefix() {
    const parts = location.pathname.split("/").filter(Boolean);
    const last = parts[parts.length - 1] || "";
    if (["city", "wiki", "alert"].includes(parts[parts.length - 2])) return "../";
    if (/^(en|es|fr|de|ja|ru|kr|ar)$/.test(parts[0]) && ["city", "wiki", "alert"].includes(parts[1])) return "../../";
    if (/^(en|es|fr|de|ja|ru|kr|ar)$/.test(parts[0])) return "../";
    return "./";
  }
})();
