"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/brand/Logo";
import { CartDrawer } from "@/components/cart/CartDrawer";
import { MobileNav } from "@/components/layout/MobileNav";
import { SearchOverlay } from "@/components/search/SearchOverlay";
import { BagIcon, SearchIcon, UserIcon } from "@/components/ui/icons";
import { getSession } from "@/lib/auth/allauth";
import { useCart } from "@/lib/cart/CartProvider";

const NAV = [
  ["Home", "/"],
  ["Shop", "/shop"],
  ["Collections", "/collections"],
  ["About Us", "/about"],
  ["Contact", "/contact"],
];

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { itemCount } = useCart();

  async function goAuthed(dest: string) {
    let authed = false;
    try {
      const session = await getSession();
      authed = session.meta?.is_authenticated ?? false;
    } catch {
      // Session check failed (API down etc.) — treat as logged out.
    }
    router.push(authed ? dest : "/login");
  }

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-40 bg-charcoal text-cream shadow-[0_1px_0_rgba(255,255,255,0.06)]">
      <div className="container-page flex h-20 items-center justify-between gap-4 md:grid md:grid-cols-[1fr_auto_1fr]">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setMobileNavOpen(true)}
            className="flex h-10 w-10 items-center justify-center rounded-sm text-cream/85 hover:bg-cream/10 hover:text-gold md:hidden"
          >
            <MenuIcon />
          </button>
          <Logo variant="gold" compact className="justify-self-start" />
        </div>

        <nav className="hidden items-center gap-8 md:flex">
          {NAV.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              className={`text-sm font-medium tracking-wide transition ${
                isActive(href)
                  ? "text-gold"
                  : "text-cream/85 hover:text-gold"
              }`}
            >
              {label.toUpperCase()}
              {isActive(href) && (
                <span className="mt-1 block h-px w-full bg-gold" />
              )}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-4 justify-self-end sm:gap-5">
          <button
            type="button"
            aria-label="Search"
            onClick={() => setSearchOpen(true)}
            className="flex h-9 w-9 items-center justify-center text-cream/85 transition hover:text-gold"
          >
            <SearchIcon />
          </button>
          <button
            type="button"
            aria-label="Account"
            onClick={() => goAuthed("/account")}
            className="hidden h-9 w-9 items-center justify-center text-cream/85 transition hover:text-gold sm:flex"
          >
            <UserIcon />
          </button>
          <button
            type="button"
            onClick={() => goAuthed("/cart")}
            aria-label={`Cart (${itemCount} items)`}
            className="relative flex h-9 w-9 items-center justify-center text-cream/85 transition hover:text-gold"
          >
            <BagIcon />
            {itemCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-gold px-1 text-[10px] font-bold text-charcoal">
                {itemCount}
              </span>
            )}
          </button>
        </div>
      </div>

      <SearchOverlay open={searchOpen} onClose={() => setSearchOpen(false)} />
      <CartDrawer />
      <MobileNav
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        onOpenSearch={() => setSearchOpen(true)}
      />
    </header>
  );
}

function MenuIcon() {
  return (
    <svg className="h-6 w-6 stroke-current" fill="none" viewBox="0 0 24 24" strokeWidth="1.75">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
    </svg>
  );
}

