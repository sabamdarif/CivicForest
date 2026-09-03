/* Upgrades the shop's filter form, sort select, chips and pagination to fetch-and-replace.
 *
 * The contract from D2: the page already works as plain GET forms and links, and this only
 * saves the reload. The server renders the same region either way, so the two paths cannot
 * disagree about what matches. Anything unexpected falls back to a normal navigation.
 *
 * The mobile drawer is deliberately not enhanced: its Apply button submits, which is both the
 * no-JS behaviour and the reason a swap can never close a panel someone is still using.
 */

const region = document.querySelector("[data-shop]");

const hideRedundant = (root) => {
  for (const element of root.querySelectorAll("[data-js-hide]")) element.hidden = true;
};

const urlFor = (form) => {
  const params = new URLSearchParams();
  for (const [name, value] of new FormData(form)) {
    if (value !== "") params.append(name, value);
  }
  // Any new selection is a new result set, so it starts at page one.
  params.delete("page");
  const query = params.toString();
  return query ? `${form.action}?${query}` : form.action;
};

const load = async (url, { push = true, scroll = false } = {}) => {
  const focused = document.activeElement?.id;
  region.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(url, { headers: { "X-Partial": "shop" } });
    if (!response.ok) throw new Error(response.status);
    region.innerHTML = await response.text();
  } catch {
    window.location.assign(url);
    return;
  } finally {
    region.removeAttribute("aria-busy");
  }
  hideRedundant(region);
  // The swap destroys the control that was in use, so focus has to be put back on its
  // replacement or a keyboard user is dropped at the top of the document.
  if (focused) document.getElementById(focused)?.focus();
  if (push) history.pushState({}, "", url);
  if (scroll) region.scrollIntoView({ block: "start", behavior: "smooth" });
};

if (region) {
  hideRedundant(document);

  region.addEventListener("change", (event) => {
    const form = event.target.closest("form[data-filters], form[data-sort]");
    if (form) load(urlFor(form));
  });

  region.addEventListener("click", (event) => {
    const link = event.target.closest("a.pagination__link[href], a.chip[href]");
    const plain = event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey;
    if (!link || !plain) return;
    event.preventDefault();
    load(link.href, { scroll: true });
  });

  window.addEventListener("popstate", () => load(window.location.href, { push: false }));
}
