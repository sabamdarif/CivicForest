/**
 * Records the product in the recently-viewed cookie (D10).
 *
 * The server renders the strip from this cookie, so all this has to do is write it. Nothing on
 * the page depends on the script having run: a visitor with no JavaScript simply never gets a
 * strip, which is the right way for an enhancement to be absent.
 */

const COOKIE = "cf_recent";
const LIMIT = 6;
const DAYS = 30;

const read = () =>
  document.cookie
    .split("; ")
    .find((pair) => pair.startsWith(`${COOKIE}=`))
    ?.slice(COOKIE.length + 1) ?? "";

const slug = document.querySelector("[data-product-slug]")?.dataset.productSlug;

if (slug) {
  // The server validates every slug it reads back, so the only job here is order and the cap.
  const seen = [slug, ...read().split(",").filter(Boolean)];
  const trimmed = [...new Set(seen)].slice(0, LIMIT).join(",");
  const expires = new Date(Date.now() + DAYS * 86400000).toUTCString();
  document.cookie = `${COOKIE}=${trimmed}; path=/; expires=${expires}; samesite=lax`;
}
