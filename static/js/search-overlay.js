/* The header search overlay (D7, M3.8).
 *
 * Everything structural is the <dialog> element's: focus trap, inert page, backdrop, Escape,
 * and returning focus to the icon on close. modal.js wires the icon's click to showModal(), so
 * this file only adds the suggestions, and the icon stays a plain link to /search/ when
 * JavaScript is off or this module fails to load (P6).
 *
 * The payload is rendered with textContent and element properties, never innerHTML: a product
 * name is staff-entered text and must not be able to become markup.
 */

import "./modal.js";

const DEBOUNCE = 250;
const MIN_LENGTH = 2;
const ENDPOINT = "/api/v1/search/suggest/";

const form = document.querySelector("[data-search]");
const input = form?.querySelector("[data-search-input]");
const results = form?.querySelector("[data-search-results]");
const count = form?.querySelector("[data-search-count]");

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
};

const row = (child) => {
  const item = el("li");
  item.append(child);
  return item;
};

const anchor = (href, className, text) => {
  const node = el("a", className, text);
  node.href = href;
  return node;
};

const thumbnail = (hit) => {
  const image = el("img", "search-suggest__thumb");
  image.src = hit.image;
  if (hit.srcset) image.srcset = hit.srcset;
  image.width = 48;
  image.height = 64;
  image.alt = "";
  image.loading = "lazy";
  return image;
};

const product = (hit) => {
  const node = anchor(hit.url, "search-suggest__hit");
  if (hit.image) node.append(thumbnail(hit));
  const text = el("span", "search-suggest__text");
  text.append(el("span", "search-suggest__name", hit.name));
  const price = el("span", "search-suggest__price", hit.price);
  if (hit.mrp) price.append(el("s", "search-suggest__mrp", hit.mrp));
  text.append(price);
  node.append(text);
  return row(node);
};

const section = (title, items) => {
  const group = el("section", "search-suggest__group");
  group.append(el("h3", "search-suggest__title", title));
  const list = el("ul", "search-suggest__list");
  list.append(...items);
  group.append(list);
  return group;
};

const render = (payload, term) => {
  results.replaceChildren();
  if (!payload) {
    count.textContent = "";
    return;
  }

  if (payload.products.length) {
    results.append(section("Products", payload.products.map(product)));
  }
  if (payload.categories.length) {
    const items = payload.categories.map((category) =>
      row(anchor(category.url, "search-suggest__term", category.name)),
    );
    results.append(section("Categories", items));
  }
  if (payload.queries.length) {
    const items = payload.queries.map((query) =>
      row(anchor(`/search/?q=${encodeURIComponent(query)}`, "search-suggest__term", query)),
    );
    results.append(section("Popular searches", items));
  }
  if (!payload.total) {
    results.append(el("p", "search-suggest__none", `No matches for “${term}”.`));
  }
  // The list is enough for a sighted user; this is how a screen reader hears it change.
  count.textContent = payload.total === 1 ? "1 result" : `${payload.total} results`;
};

const load = async (term) => {
  try {
    const response = await fetch(`${ENDPOINT}?q=${encodeURIComponent(term)}`);
    if (!response.ok) throw new Error(response.status);
    render(await response.json(), term);
  } catch {
    // Submitting still works, so a failed suggestion stays silent rather than shouting.
    render(null);
  }
};

if (form && input && results && count) {
  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    const term = input.value.trim();
    if (term.length < MIN_LENGTH) {
      render(null);
      return;
    }
    timer = setTimeout(() => load(term), DEBOUNCE);
  });

  // Arrow keys walk the suggestions and come back to the field, so the list is reachable
  // without tabbing past the close button, as every autocomplete behaves.
  form.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const stops = [input, ...results.querySelectorAll("a")];
    const here = stops.indexOf(document.activeElement);
    const next = here + (event.key === "ArrowDown" ? 1 : -1);
    if (here === -1 || next < 0 || next >= stops.length) return;
    event.preventDefault();
    stops[next].focus();
  });
}
