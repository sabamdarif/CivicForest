/**
 * Colour swatches swap the gallery and the size row without a reload (E2), and the size-guide
 * link opens the accordion it points at.
 *
 * The swatches are already links to `?color=`, which the server answers with the right gallery
 * and the right size availability, so this only saves the paint. It splices the same page the
 * server renders rather than asking for a partial: one click's worth of traffic is not worth a
 * second template, which is the opposite of the shop grid's case.
 */

const region = document.querySelector("[data-product]");

const swap = (from, selector) => {
  const next = from.querySelector(selector);
  const here = document.querySelector(selector);
  if (next && here) here.replaceWith(next);
};

const load = async (url) => {
  region.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
    if (!response.ok) throw new Error(response.status);
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    swap(page, "[data-gallery]");
    swap(page, "[data-buy]");
    history.pushState({}, "", url);
    // The gallery node is new, so whatever was observing the old one has to start again.
    document.dispatchEvent(new CustomEvent("cf:swap"));
  } catch {
    window.location.assign(url);
  } finally {
    region.removeAttribute("aria-busy");
  }
};

if (region) {
  region.addEventListener("click", (event) => {
    const swatch = event.target.closest("a[data-colour]");
    const plain = event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey;
    if (swatch && plain) {
      event.preventDefault();
      load(swatch.href);
      return;
    }

    // The link points at a <details> by id. Only some browsers expand one to reach a fragment,
    // so with JavaScript the link always does what it says.
    const guide = event.target.closest('a[href="#size-guide"]');
    const panel = guide && document.getElementById("size-guide");
    if (panel && plain) {
      // Default-prevented deliberately: letting the fragment navigation run as well fights the
      // exclusive-accordion group these panels share and lands with this one closed again.
      event.preventDefault();
      panel.open = true;
      panel.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  });

  window.addEventListener("popstate", () => window.location.reload());
}
