/* Price chart for the stock page: plain canvas, no libraries. */
(() => {
  const root = document.getElementById("chart");
  if (!root) return;

  const symbol = root.dataset.symbol;
  const currency = root.dataset.currency;
  const canvas = root.querySelector("canvas");
  const tip = root.querySelector(".chart-tip");
  const msg = root.querySelector(".chart-msg");
  const summary = document.getElementById("range-change");
  const buttons = document.querySelectorAll(".ranges button");
  const ctx = canvas.getContext("2d");
  const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const nf = new Intl.NumberFormat(currency === "₹" ? "en-IN" : "en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const money = (v) => currency + nf.format(v);

  let data = null;
  let range = "1Y";
  let hover = -1;
  const pad = { l: 8, r: 70, t: 14, b: 28 };

  function hexToRgba(hex, alpha) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  }

  function niceTicks(lo, hi, count = 4) {
    const span = hi - lo || 1;
    const raw = span / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / mag;
    const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
    const ticks = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(v);
    return ticks;
  }

  function dateLabel(iso, long) {
    const d = new Date(iso + "T00:00:00");
    if (long) return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    if (range === "1M" || range === "6M") return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    if (range === "MAX") return String(d.getFullYear());
    return d.toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
  }

  function draw() {
    if (!data || !data.close.length) return;
    const dpr = window.devicePixelRatio || 1;
    const w = root.clientWidth;
    const h = root.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const ys = data.close;
    const n = ys.length;
    let min = Math.min(...ys);
    let max = Math.max(...ys);
    const margin = (max - min || max * 0.02) * 0.06;
    min -= margin;
    max += margin;

    const plotW = w - pad.l - pad.r;
    const plotH = h - pad.t - pad.b;
    const x = (i) => pad.l + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const y = (v) => pad.t + ((max - v) / (max - min)) * plotH;

    // grid + y axis labels
    ctx.font = '12px "Schibsted Grotesk", system-ui, sans-serif';
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    ctx.lineWidth = 1;
    for (const t of niceTicks(min, max)) {
      const ty = Math.round(y(t)) + 0.5;
      ctx.strokeStyle = cssVar("--line");
      ctx.beginPath();
      ctx.moveTo(pad.l, ty);
      ctx.lineTo(w - pad.r + 4, ty);
      ctx.stroke();
      ctx.fillStyle = cssVar("--muted");
      ctx.fillText(nf.format(t).replace(/\.00$/, ""), w - pad.r + 10, ty);
    }

    // x axis labels
    ctx.textBaseline = "top";
    const labelCount = Math.min(5, n);
    for (let k = 0; k < labelCount; k++) {
      const i = labelCount === 1 ? 0 : Math.round((k / (labelCount - 1)) * (n - 1));
      ctx.textAlign = k === 0 ? "left" : k === labelCount - 1 ? "right" : "center";
      ctx.fillStyle = cssVar("--muted");
      ctx.fillText(dateLabel(data.dates[i]), x(i), h - pad.b + 8);
    }

    // line + soft area, green if the period ended higher than it began
    const color = cssVar(ys[n - 1] >= ys[0] ? "--up" : "--down");
    const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + plotH);
    grad.addColorStop(0, hexToRgba(color, 0.16));
    grad.addColorStop(1, hexToRgba(color, 0));
    ctx.beginPath();
    ys.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.lineTo(x(n - 1), pad.t + plotH);
    ctx.lineTo(x(0), pad.t + plotH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    ys.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();

    // hover crosshair + tooltip
    if (hover >= 0 && hover < n) {
      const hx = x(hover);
      const hy = y(ys[hover]);
      ctx.strokeStyle = cssVar("--muted");
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(Math.round(hx) + 0.5, pad.t);
      ctx.lineTo(Math.round(hx) + 0.5, pad.t + plotH);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(hx, hy, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = cssVar("--surface");
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.stroke();

      tip.hidden = false;
      tip.innerHTML = "";
      const price = document.createElement("b");
      price.textContent = money(ys[hover]);
      tip.append(price, document.createTextNode(dateLabel(data.dates[hover], true)));
      const tw = tip.offsetWidth;
      tip.style.left = Math.max(8, Math.min(hx + 14, w - tw - 8)) + "px";
      if (hx + 14 + tw > w - 8) tip.style.left = Math.max(8, hx - tw - 14) + "px";
    } else {
      tip.hidden = true;
    }
  }

  function showSummary() {
    const first = data.close[0];
    const last = data.close[data.close.length - 1];
    const pct = ((last - first) / first) * 100;
    const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
    const label = range === "MAX" ? "all time" : range;
    summary.innerHTML = "";
    const strong = document.createElement("strong");
    strong.className = pct >= 0 ? "up" : "down";
    strong.textContent = `${sign}${Math.abs(pct).toFixed(2)}%`;
    summary.append(strong, document.createTextNode(` over ${label}`));
    canvas.setAttribute(
      "aria-label",
      `${symbol} closing price over ${label}: from ${money(first)} to ${money(last)}`
    );
  }

  async function load(next) {
    range = next;
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.range === range)));
    msg.hidden = false;
    msg.textContent = "Loading price history…";
    try {
      const res = await fetch(`/api/history/${encodeURIComponent(symbol)}/?range=${range}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Price history is unavailable.");
      if (range !== next) return; // user clicked another range meanwhile
      data = body;
      hover = -1;
      msg.hidden = true;
      showSummary();
      draw();
    } catch (err) {
      data = null;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      tip.hidden = true;
      summary.textContent = "";
      msg.hidden = false;
      msg.textContent = err.message || "Price history is unavailable. Try again in a minute.";
    }
  }

  canvas.addEventListener("pointermove", (e) => {
    if (!data) return;
    const rect = canvas.getBoundingClientRect();
    const plotW = rect.width - pad.l - pad.r;
    const ratio = (e.clientX - rect.left - pad.l) / plotW;
    const n = data.close.length;
    const idx = Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))));
    if (idx !== hover) {
      hover = idx;
      draw();
    }
  });
  canvas.addEventListener("pointerleave", () => {
    hover = -1;
    draw();
  });

  buttons.forEach((b) => b.addEventListener("click", () => load(b.dataset.range)));
  new ResizeObserver(draw).observe(root);
  load(range);
})();
