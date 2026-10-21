/**
 * Mobile navigation panel.
 *
 * The panel is a <details>, so opening, closing and keyboard operation already work with
 * JavaScript off (P6). This adds only the three things markup cannot: Escape, clicking the
 * scrim, and closing when the viewport grows past the breakpoint the panel belongs to.
 */

const DESKTOP = window.matchMedia("(width >= 60rem)");

for (const nav of document.querySelectorAll("[data-nav]")) {
  const summary = nav.querySelector("summary");

  const close = ({ refocus = false } = {}) => {
    if (!nav.open) return;
    nav.open = false;
    if (refocus) summary?.focus();
  };

  nav.querySelector("[data-nav-scrim]")?.addEventListener("click", () => close());

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close({ refocus: true });
  });

  DESKTOP.addEventListener("change", (event) => {
    if (event.matches) close();
  });
}
