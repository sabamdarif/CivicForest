/* The custom design tool (M7.5).
 *
 * The one documented exception to "works without JavaScript": positioning artwork on a
 * garment needs a canvas the server cannot render. Everything it decides is still checked
 * server-side. The tool never sends a price: it shows a live estimate and the authoritative
 * total is recomputed at checkout. It serialises exactly Qikink's fields: a placement SKU and
 * a width and height in inches, per side.
 *
 * Upload path (bytes never touch Django): ask for a presigned URL, PUT the file straight to
 * storage, then confirm so the server sanitises it and returns the print-ready preview.
 */

const root = document.querySelector("[data-designer]");
if (root) init(root);

function init(root) {
  const config = JSON.parse(root.querySelector("[data-config]").textContent);
  const csrf = root.querySelector("[name=csrfmiddlewaretoken]")?.value ?? "";
  const stage = root.querySelector("[data-stage]");
  const area = root.querySelector("[data-print-area]");
  const art = root.querySelector("[data-art]");
  const scale = root.querySelector("[data-scale]");
  const priceEl = root.querySelector("[data-price]");
  const dpiWarn = root.querySelector("[data-dpi-warning]");
  const rights = root.querySelector("[data-rights]");
  const addBtn = root.querySelector("[data-add]");
  const errorEl = root.querySelector("[data-error]");
  const uploadInput = root.querySelector("[data-upload]");
  const uploadStatus = root.querySelector("[data-upload-status]");
  const form = root.querySelector("[data-add-form]");

  // Per-side state. Front is required; back is optional.
  const sides = {
    front: { design: null, nativeW: 0, nativeH: 0 },
    back: { design: null, nativeW: 0, nativeH: 0 },
  };
  let side = "front";

  root.hidden = false;
  showSide();
  render();

  function areaFor(key) {
    return config.printAreas?.[key];
  }

  // A back tab only makes sense if the blank has a back print area.
  root.querySelectorAll("[data-side]").forEach((tab) => {
    const key = tab.dataset.side;
    if (!areaFor(key)) {
      tab.disabled = true;
      return;
    }
    tab.addEventListener("click", () => {
      side = key;
      root.querySelectorAll("[data-side]").forEach((t) =>
        t.setAttribute("aria-selected", String(t.dataset.side === side))
      );
      showSide();
      render();
    });
  });

  function showSide() {
    const a = areaFor(side);
    const st = sides[side];
    if (a?.px) {
      Object.assign(area.style, {
        left: `${a.px.x}px`,
        top: `${a.px.y}px`,
        width: `${a.px.w}px`,
        height: `${a.px.h}px`,
      });
    }
    scale.value = st.scalePct ?? 70;
    if (st.design) {
      art.src = st.previewUrl;
      art.hidden = false;
    } else {
      art.hidden = true;
      art.removeAttribute("src");
    }
    sizeArt();
  }

  function sizeArt() {
    const a = areaFor(side);
    const st = sides[side];
    if (!a?.px || !st.design) return;
    const pct = Number(scale.value) / 100;
    art.style.width = `${a.px.w * pct}px`;
    art.style.height = "auto";
  }

  // Printed size in inches for one side, from its slider fraction and native aspect,
  // clamped to the printable bounds. This is exactly what the server clamps to as well.
  function inchesFor(key) {
    const a = areaFor(key);
    const st = sides[key];
    if (!a || !st.design) return null;
    const pct = (st.scalePct ?? 70) / 100;
    const w = Math.min(pct * a.max_width_in, a.max_width_in);
    let h = w * (st.nativeH / st.nativeW);
    h = Math.min(h, a.max_height_in);
    return { w: round2(w), h: round2(h) };
  }

  function surchargeFor(key) {
    const inches = inchesFor(key);
    const tiers = config.surchargeTiers || [];
    if (!inches || !tiers.length) return 0;
    for (const tier of tiers) {
      if (inches.w <= tier.max_width_in && inches.h <= tier.max_height_in) {
        return Number(tier.surcharge);
      }
    }
    return Number(tiers[tiers.length - 1].surcharge);
  }

  function render() {
    sizeArt();
    // Live estimate only: the authoritative total is recomputed server-side at checkout.
    let total = Number(config.basePrice);
    total += surchargeFor("front");
    if (sides.back.design) total += surchargeFor("back");
    priceEl.textContent = `Estimated ${money(total)} (final price shown at checkout)`;

    // Resolution warning against the current side's printed width.
    const st = sides[side];
    const inches = inchesFor(side);
    if (st.design && inches) {
      const dpi = st.nativeW / inches.w;
      dpiWarn.hidden = dpi >= config.minDpi;
    } else {
      dpiWarn.hidden = true;
    }

    addBtn.disabled = !(sides.front.design && rights.checked);
  }

  scale.addEventListener("input", () => {
    sides[side].scalePct = Number(scale.value);
    render();
  });
  rights.addEventListener("change", render);

  // ── Upload: presign, PUT straight to storage, confirm to sanitise ──────────
  uploadInput.addEventListener("change", async () => {
    const file = uploadInput.files?.[0];
    if (!file) return;
    setStatus("Uploading…");
    try {
      const ticket = await postJSON("/api/v1/designs/upload-url/", {
        content_type: file.type,
        bytes: file.size,
      });
      const put = await fetch(ticket.upload_url, {
        method: ticket.method,
        headers: ticket.headers,
        body: file,
      });
      if (!put.ok) throw new Error("upload failed");
      const design = await postJSON(`/api/v1/designs/${ticket.design_id}/complete/`, {});
      if (design.status !== "ready") {
        setStatus(design.review_reason || "That file could not be used. Try another image.");
        return;
      }
      loadDesign(side, {
        id: ticket.design_id,
        previewUrl: design.preview_url,
        nativeW: design.width_px,
        nativeH: design.height_px,
      });
      setStatus(design.review_status === "flagged" ? "Uploaded. Low resolution, see below." : "Uploaded.");
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        location.assign(`/accounts/login/?next=${encodeURIComponent(location.pathname)}`);
        return;
      }
      setStatus("Upload failed. Please try again.");
    }
  });

  root.querySelectorAll("[data-saved-id]").forEach((btn) => {
    btn.addEventListener("click", () =>
      loadDesign(side, {
        id: btn.dataset.savedId,
        previewUrl: btn.dataset.savedUrl,
        nativeW: Number(btn.dataset.savedW),
        nativeH: Number(btn.dataset.savedH),
      })
    );
  });

  function loadDesign(key, design) {
    sides[key] = { ...sides[key], design, ...design, scalePct: sides[key].scalePct ?? 70 };
    showSide();
    render();
  }

  // ── Add to cart ────────────────────────────────────────────────────────────
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!sides.front.design) return;
    errorEl.hidden = true;
    const front = inchesFor("front");
    const payload = {
      blank_slug: config.slug,
      design_id: sides.front.design.id,
      size: form.querySelector("[name=size]:checked")?.value,
      color: form.querySelector("[name=color]:checked")?.value,
      placement_sku: areaFor("front").placement_sku,
      width_inches: front.w,
      height_inches: front.h,
      quantity: Number(form.querySelector("[data-qty]").value) || 1,
      rights_accepted: rights.checked,
    };
    if (sides.back.design) {
      const back = inchesFor("back");
      Object.assign(payload, {
        back_design_id: sides.back.design.id,
        back_placement_sku: areaFor("back").placement_sku,
        back_width_inches: back.w,
        back_height_inches: back.h,
      });
    }
    try {
      await postJSON("/api/v1/designs/add-to-cart/", payload);
      location.assign("/cart/");
    } catch (err) {
      errorEl.textContent = err.detail || "Could not add to cart. Please check your selection.";
      errorEl.hidden = false;
    }
  });

  function setStatus(text) {
    uploadStatus.textContent = text;
  }

  async function postJSON(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const error = new Error("request failed");
      error.status = response.status;
      error.detail = data.error?.message;
      throw error;
    }
    return response.json();
  }
}

function round2(n) {
  return Math.round(n * 100) / 100;
}

// A light Indian-grouped estimate for display only. The rupee filter on the server is the
// single source of truth for money; this never feeds a total back to it.
function money(n) {
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

