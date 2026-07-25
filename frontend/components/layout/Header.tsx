"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/brand/Logo";
import { CartDrawer } from "@/components/cart/CartDrawer";
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
      <div className="container-page grid h-20 grid-cols-[1fr_auto_1fr] items-center">
        <Logo variant="gold" compact className="justify-self-start" />

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

        <div className="flex items-center gap-5 justify-self-end">
          <button
            type="button"
            aria-label="Search"
            onClick={() => setSearchOpen(true)}
            className="text-cream/85 transition hover:text-gold"
          >
            <SearchIcon />
          </button>
          <button
            type="button"
            aria-label="Account"
            onClick={() => goAuthed("/account")}
            className="text-cream/85 transition hover:text-gold"
          >
            <UserIcon />
          </button>
          <button
            type="button"
            onClick={() => goAuthed("/cart")}
            aria-label={`Cart (${itemCount} items)`}
            className="relative text-cream/85 transition hover:text-gold"
          >
            <BagIcon />
            {itemCount > 0 && (
              <span className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-gold px-1 text-[10px] font-bold text-charcoal">
                {itemCount}
              </span>
            )}
          </button>
        </div>
      </div>

      <SearchOverlay open={searchOpen} onClose={() => setSearchOpen(false)} />
      <CartDrawer />
    </header>
  );
}
