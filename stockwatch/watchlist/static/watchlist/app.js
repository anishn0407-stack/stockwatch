/* Shared behaviour: wishlist stars, search autocomplete, sector filter, desktop button. */
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const post = (url) =>
    fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf }, credentials: "same-origin" });

  // ---- toast ------------------------------------------------------------
  const toastEl = document.getElementById("toast");
  let toastTimer;
  function toast(message) {
    toastEl.textContent = message;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 3500);
  }

  // ---- wishlist star ------------------------------------------------------
  function setStar(btn, on) {
    btn.setAttribute("aria-pressed", String(on));
    const name = btn.dataset.name;
    btn.setAttribute("aria-label", `${on ? "Remove" : "Add"} ${name} ${on ? "from" : "to"} wishlist`);
    const label = btn.querySelector(".star-label");
    if (label) label.textContent = on ? "In your wishlist" : "Add to wishlist";
  }

  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("button.star");
    if (!btn) return;
    btn.disabled = true;
    try {
      const res = await post(`/api/wishlist/toggle/${encodeURIComponent(btn.dataset.symbol)}/`);
      if (!res.ok) throw new Error("toggle failed");
      const data = await res.json();
      document
        .querySelectorAll(`button.star[data-symbol="${CSS.escape(btn.dataset.symbol)}"]`)
        .forEach((b) => setStar(b, data.in_wishlist));
      toast(data.in_wishlist ? "Added to wishlist." : "Removed from wishlist.");
    } catch (err) {
      toast("Could not update the wishlist. Try again.");
    } finally {
      btn.disabled = false;
    }
  });

  // ---- search autocomplete ----------------------------------------------
  const input = document.getElementById("search");
  const list = document.getElementById("search-results");
  let items = [];
  let active = -1;
  let timer;
  let latest = 0;

  function render() {
    list.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "none";
      li.textContent = "No stocks match that search.";
      list.appendChild(li);
    }
    items.forEach((it, i) => {
      const li = document.createElement("li");
      li.id = `result-${i}`;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(i === active));
      const name = document.createElement("span");
      name.textContent = it.name;
      const sym = document.createElement("span");
      sym.className = "sym";
      sym.textContent = it.symbol;
      li.append(name, sym);
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        go(it);
      });
      list.appendChild(li);
    });
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    input.setAttribute("aria-activedescendant", active >= 0 ? `result-${active}` : "");
  }

  function close() {
    list.hidden = true;
    active = -1;
    input.setAttribute("aria-expanded", "false");
  }

  function go(it) {
    window.location.href = `/stock/${encodeURIComponent(it.symbol)}/`;
  }

  async function search(q) {
    const ticket = ++latest;
    try {
      const res = await fetch(`/api/search/?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (ticket !== latest) return; // a newer search is already running
      items = data.results;
      active = -1;
      render();
    } catch (err) {
      close();
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (!q) {
      latest++;
      close();
      return;
    }
    timer = setTimeout(() => search(q), 150);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") return close();
    if (list.hidden || !items.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      active = (active + step + items.length) % items.length;
      render();
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(items[active >= 0 ? active : 0]);
    }
  });

  input.addEventListener("blur", close);

  // ---- sector filter on the home page --------------------------------------
  const sector = document.getElementById("sector-filter");
  if (sector) {
    sector.addEventListener("change", () => {
      document.querySelectorAll("tr[data-sector]").forEach((row) => {
        row.hidden = sector.value !== "" && row.dataset.sector !== sector.value;
      });
    });
  }

  // ---- open the tkinter window ------------------------------------------------
  const desktop = document.getElementById("open-desktop");
  if (desktop) {
    desktop.addEventListener("click", async () => {
      desktop.disabled = true;
      try {
        const res = await post("/desktop/open/");
        const data = await res.json().catch(() => ({}));
        toast(res.ok ? "Desktop window is opening." : data.error || "Could not open the desktop window.");
      } catch (err) {
        toast("Could not reach the server.");
      } finally {
        desktop.disabled = false;
      }
    });
  }
})();
