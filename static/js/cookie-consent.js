/**
 * Cookie consent, gating GA4 (M9.9, L5).
 *
 * Analytics never loads until the visitor accepts: with no stored choice the banner is shown and
 * nothing is tracked; Accept stores consent and injects gtag.js; Decline stores the refusal and
 * loads nothing. A returning visitor who accepted before gets gtag without being asked again.
 * gtag.js stays an external script (no inline), so the M10 CSP only has to allowlist
 * googletagmanager, not relax inline-script rules.
 */

const COOKIE = "cf_consent";
const ONE_YEAR = 60 * 60 * 24 * 365;

const banner = document.querySelector("[data-cookie-banner]");

function stored() {
  const match = document.cookie.match(/(?:^|;\s*)cf_consent=(granted|denied)/);
  return match ? match[1] : null;
}

function remember(choice) {
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${COOKIE}=${choice}; Max-Age=${ONE_YEAR}; Path=/; SameSite=Lax${secure}`;
}

function loadAnalytics(id) {
  const tag = document.createElement("script");
  tag.async = true;
  tag.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
  document.head.appendChild(tag);

  window.dataLayer = window.dataLayer || [];
  function gtag() {
    window.dataLayer.push(arguments);
  }
  gtag("js", new Date());
  gtag("config", id);
}

if (banner) {
  const id = banner.dataset.gaId;
  const choice = stored();

  if (choice === "granted") {
    loadAnalytics(id);
  } else if (choice === null) {
    banner.hidden = false;
    banner.querySelector("[data-cookie-accept]")?.addEventListener("click", () => {
      remember("granted");
      banner.hidden = true;
      loadAnalytics(id);
    });
    banner.querySelector("[data-cookie-decline]")?.addEventListener("click", () => {
      remember("denied");
      banner.hidden = true;
    });
  }
}
