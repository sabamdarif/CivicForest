import { NextResponse, type NextRequest } from "next/server";

// Server-side auth gate (works because the Django session cookie is scoped to the
// parent domain — SESSION_COOKIE_DOMAIN — so the Next server receives it too):
//   /login, /signup    → already authenticated? force-redirect to /account
//   /account/*         → not authenticated? force-redirect to /login
// The pages keep their client-side checks as a fallback for when the API is down.

const AUTH_PAGES = new Set(["/login", "/signup"]);

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Password reset lives under /account but must stay reachable anonymously
  // (allauth's reset email links here).
  if (pathname.startsWith("/account/password")) return NextResponse.next();

  const onAuthPage = AUTH_PAGES.has(pathname);

  // No session cookie at all: definitely anonymous — skip the API round-trip.
  if (!req.cookies.has("sessionid")) {
    return onAuthPage
      ? NextResponse.next()
      : NextResponse.redirect(new URL("/login", req.url));
  }

  // Cookie present — validate it against the API. A stale cookie must not count as
  // authenticated, or /login → /account → /login would redirect-loop.
  let authed = false;
  try {
    const base =
      process.env.INTERNAL_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
    const res = await fetch(`${base}/_allauth/browser/v1/auth/session`, {
      headers: {
        cookie: req.headers.get("cookie") ?? "",
        accept: "application/json",
      },
      cache: "no-store",
    });
    const data = (await res.json().catch(() => null)) as
      | { meta?: { is_authenticated?: boolean } }
      | null;
    authed = data?.meta?.is_authenticated === true;
  } catch {
    return NextResponse.next(); // API unreachable — fail open to the client-side gates
  }

  if (onAuthPage && authed) {
    return NextResponse.redirect(new URL("/account", req.url));
  }
  if (!onAuthPage && !authed) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/login", "/signup", "/account/:path*"],
};
