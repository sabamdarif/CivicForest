/* Admin sales dashboard chart (M10.5). Externalized from an inline <script> so the site CSP
 * can forbid inline script. Reads the server data from the cf-dash-data json_script island,
 * the same data-island pattern the storefront's designer.js uses. */
(function () {
  const data = JSON.parse(document.getElementById("cf-dash-data").textContent);
  const host = document.getElementById("cf-dash-chart");
  const tip = document.getElementById("cf-dash-tip");
  const inr = v => "₹" + v.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const compact = v => v >= 1e6 ? "₹" + +(v / 1e6).toFixed(1) + "M"
    : v >= 1e3 ? "₹" + +(v / 1e3).toFixed(1) + "K" : "₹" + v;

  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }

  function render() {
    const W = host.clientWidth || 600, H = 220;
    const m = { top: 8, right: 8, bottom: 22, left: 52 };
    const pw = W - m.left - m.right, ph = H - m.top - m.bottom;
    const max = niceMax(Math.max(...data.map(d => d.revenue)));
    const band = pw / data.length;
    const barW = Math.max(2, Math.min(24, band - 2));
    const y = v => m.top + ph * (1 - v / max);
    let g = "";
    for (let t = 0; t <= 4; t++) {
      const yy = y(max * t / 4);
      g += `<line x1="${m.left}" x2="${W - m.right}" y1="${yy}" y2="${yy}" stroke="var(${t === 0 ? "--cf-axis" : "--cf-grid"})" stroke-width="1"/>`
        + `<text x="${m.left - 8}" y="${yy + 3}" text-anchor="end" class="cf-tick">${compact(max * t / 4)}</text>`;
    }
    data.forEach((d, i) => {
      const cx = m.left + band * i + band / 2;
      if (d.revenue > 0) {
        const top = y(d.revenue), h = m.top + ph - top;
        const r = Math.min(4, h, barW / 2), x0 = cx - barW / 2;
        g += `<path fill="var(--cf-series)" d="M${x0},${m.top + ph} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x0 + barW - r} Q${x0 + barW},${top} ${x0 + barW},${top + r} V${m.top + ph} Z"/>`;
      }
      if (i % 5 === 0 || i === data.length - 1)
        g += `<text x="${cx}" y="${H - 6}" text-anchor="middle" class="cf-tick">${d.label}</text>`;
      g += `<rect class="cf-hit" data-i="${i}" x="${m.left + band * i}" y="${m.top}" width="${band}" height="${ph}" fill="transparent"/>`;
    });
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", W); svg.setAttribute("height", H);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Daily revenue, last 30 days");
    svg.innerHTML = g;
    host.replaceChildren(svg);

    svg.addEventListener("mousemove", e => {
      const hit = e.target.closest(".cf-hit");
      if (!hit) { tip.hidden = true; return; }
      const d = data[+hit.dataset.i];
      tip.textContent = `${d.label} · ${inr(d.revenue)} · ${d.orders} order${d.orders === 1 ? "" : "s"}`;
      tip.hidden = false;
      const r = host.getBoundingClientRect();
      tip.style.left = Math.min(e.clientX - r.left + 12, r.width - tip.offsetWidth - 4) + "px";
      tip.style.top = (e.clientY - r.top - 30) + "px";
    });
    svg.addEventListener("mouseleave", () => { tip.hidden = true; });
  }

  if (data.some(d => d.revenue > 0)) {
    render();
    let t;
    addEventListener("resize", () => { clearTimeout(t); t = setTimeout(render, 150); });
  } else {
    host.innerHTML = '<p class="cf-empty">No paid orders in the last 30 days yet.</p>';
  }
})();
