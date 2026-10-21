/**
 * Toasts: the one behaviour here with no platform equivalent.
 *
 * One live region is created on demand and reused. A confirmation is polite, so it waits
 * its turn; an error is assertive, because an action that failed should not wait. Nothing
 * takes focus: a toast is never the only way to learn what happened.
 */

const AUTO_DISMISS_MS = 6000;
const ICONS = { success: "check-circle", error: "alert" };

let region;

function toastRegion() {
  if (!region) {
    region = document.createElement("div");
    region.className = "toast-region";
    document.body.append(region);
  }
  return region;
}

export function toast(message, variant = "") {
  const el = document.createElement("div");
  el.className = variant ? `toast toast--${variant}` : "toast";
  el.setAttribute("role", variant === "error" ? "alert" : "status");

  const icon = ICONS[variant];
  el.innerHTML =
    (icon
      ? `<svg class="icon toast__icon" width="18" height="18" aria-hidden="true" focusable="false"><use href="#i-${icon}"></use></svg>`
      : "") +
    '<p class="toast__body"></p>' +
    '<button class="icon-btn icon-btn--sm" type="button" aria-label="Dismiss">' +
    '<svg class="icon" width="16" height="16" aria-hidden="true" focusable="false"><use href="#i-close"></use></svg>' +
    "</button>";
  // textContent, not innerHTML: a message may carry a product name someone else typed.
  el.querySelector(".toast__body").textContent = message;
  el.querySelector("button").addEventListener("click", () => el.remove());

  toastRegion().append(el);
  setTimeout(() => el.remove(), AUTO_DISMISS_MS);
  return el;
}

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-toast]");
  if (trigger) toast(trigger.dataset.toast, trigger.dataset.toastVariant || "");
});
