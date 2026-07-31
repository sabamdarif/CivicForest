"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";

import { Logo } from "@/components/brand/Logo";
import { ArrowRight, BagIcon, SearchIcon, UserIcon, HeartIcon } from "@/components/ui/icons";
import { getSession } from "@/lib/auth/allauth";
import { useCart } from "@/lib/cart/CartProvider";

const NAV_LINKS = [
  ["Home", "/"],
  ["Shop", "/shop"],
  ["Collections", "/collections"],
  ["About Us", "/about"],
  ["Contact", "/contact"],
];

const CATEGORY_LINKS = [
  ["T-Shirts", "/shop?category=t-shirts"],
  ["Hoodies", "/shop?category=hoodies"],
  ["Sweatshirts", "/shop?category=sweatshirts"],
  ["Jackets", "/shop?category=jackets"],
  ["Bottoms", "/shop?category=bottoms"],
];

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
  onOpenSearch: () => void;
}

export function MobileNav({ open, onClose, onOpenSearch }: MobileNavProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { itemCount } = useCart();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    if (!open) return;
    getSession()
      .then((s) => setIsAuthenticated(s.meta?.is_authenticated ?? false))
      .catch(() => setIsAuthenticated(false));
  }, [open]);

  // Lock body scroll when mobile nav is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  function handleNavigate(dest: string) {
    onClose();
    router.push(dest);
  }

  async function handleAccountClick() {
    onClose();
    let authed = false;
    try {
      const session = await getSession();
      authed = session.meta?.is_authenticated ?? false;
    } catch {
      /* fallback */
    }
    router.push(authed ? "/account" : "/login");
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 md:hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-charcoal/80 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Navigation Menu"
        className="fixed inset-y-0 left-0 z-50 flex w-full max-w-xs flex-col bg-charcoal text-cream shadow-2xl transition-transform"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-cream/10 px-5 py-5">
          <Logo variant="gold" compact />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="flex h-9 w-9 items-center justify-center rounded-full text-cream/70 hover:bg-cream/10 hover:text-cream"
          >
            ✕
          </button>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-3 border-b border-cream/10 bg-charcoal-800 p-3 text-center text-xs">
          <button
            type="button"
            onClick={() => {
              onClose();
              onOpenSearch();
            }}
            className="flex flex-col items-center gap-1.5 p-2 text-cream/80 hover:text-gold"
          >
            <SearchIcon className="h-5 w-5" />
            <span>Search</span>
          </button>

          <button
            type="button"
            onClick={handleAccountClick}
            className="flex flex-col items-center gap-1.5 p-2 text-cream/80 hover:text-gold"
          >
            <UserIcon className="h-5 w-5" />
            <span>{isAuthenticated ? "Account" : "Sign In"}</span>
          </button>

          <button
            type="button"
            onClick={() => handleNavigate("/cart")}
            className="relative flex flex-col items-center gap-1.5 p-2 text-cream/80 hover:text-gold"
          >
            <div className="relative">
              <BagIcon className="h-5 w-5" />
              {itemCount > 0 && (
                <span className="absolute -right-2 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-gold px-1 text-[10px] font-bold text-charcoal">
                  {itemCount}
                </span>
              )}
            </div>
            <span>Cart</span>
          </button>
        </div>

        {/* Navigation Content */}
        <div className="flex-1 overflow-y-auto px-5 py-6 scroll-thin">
          <p className="eyebrow text-[10px]">Menu</p>
          <nav className="mt-3 space-y-1">
            {NAV_LINKS.map(([label, href]) => (
              <Link
                key={href}
                href={href}
                onClick={onClose}
                className={`flex items-center justify-between rounded-sm px-3 py-2.5 text-base font-medium transition ${
                  isActive(href)
                    ? "bg-gold/15 text-gold"
                    : "text-cream/90 hover:bg-cream/5 hover:text-gold"
                }`}
              >
                <span>{label}</span>
                <ArrowRight className="h-4 w-4 opacity-60" />
              </Link>
            ))}
          </nav>

          <div className="my-6 border-t border-cream/10 pt-6">
            <p className="eyebrow text-[10px]">Categories</p>
            <div className="mt-3 space-y-1">
              {CATEGORY_LINKS.map(([label, href]) => (
                <Link
                  key={label}
                  href={href}
                  onClick={onClose}
                  className="flex items-center justify-between rounded-sm px-3 py-2 text-sm text-cream/70 transition hover:bg-cream/5 hover:text-gold"
                >
                  <span>{label}</span>
                  <ArrowRight className="h-3.5 w-3.5 opacity-40" />
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Footer info inside menu */}
        <div className="border-t border-cream/10 bg-charcoal-800 px-5 py-4 text-xs text-cream/50">
          <p className="font-medium text-gold">CivicForest Clothing</p>
          <p className="mt-0.5">Elevated everyday wear.</p>
        </div>
      </div>
    </div>
  );
}
