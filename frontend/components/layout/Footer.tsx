import Link from "next/link";

import { Logo } from "@/components/brand/Logo";
import { ArrowRight } from "@/components/ui/icons";

const COLUMNS = [
  {
    title: "Shop",
    links: [
      ["All Products", "/shop"],
      ["T-Shirts", "/shop?category=t-shirts"],
      ["Hoodies", "/shop?category=hoodies"],
      ["Sweatshirts", "/shop?category=sweatshirts"],
      ["Jackets", "/shop?category=jackets"],
      ["Bottoms", "/shop?category=bottoms"],
    ],
  },
  {
    title: "Collections",
    links: [
      ["T-Shirt Collection", "/collections"],
      ["Hoodie Collection", "/collections"],
      ["Sweatshirt Collection", "/collections"],
      ["New Arrivals", "/shop?is_new=true"],
    ],
  },
  {
    title: "Customer Care",
    links: [
      ["FAQs", "/contact"],
      ["Shipping & Delivery", "/contact"],
      ["Returns & Exchanges", "/contact"],
      ["Size Guide", "/contact"],
      ["Track Order", "/contact"],
    ],
  },
];

const SOCIAL = ["Instagram", "Facebook", "Pinterest", "YouTube"];

export function Footer() {
  return (
    <footer className="bg-charcoal text-cream/80">
      <div className="container-page grid gap-10 py-14 md:grid-cols-[1.4fr_repeat(3,1fr)_1.4fr]">
        <div className="max-w-xs">
          <Logo variant="gold" />
          <p className="mt-4 text-sm leading-relaxed">
            Elevated everyday wear crafted for comfort, designed for confidence.
          </p>
          <div className="mt-5 flex gap-3 text-[11px] uppercase tracking-wide text-cream/60">
            {SOCIAL.map((s) => (
              <span key={s} className="transition hover:text-gold">
                {s[0]}
              </span>
            ))}
          </div>
        </div>

        {COLUMNS.map((col) => (
          <div key={col.title}>
            <h3 className="text-xs font-semibold uppercase tracking-brand text-gold">
              {col.title}
            </h3>
            <ul className="mt-4 space-y-2.5 text-sm">
              {col.links.map(([label, href]) => (
                <li key={label}>
                  <Link href={href} className="transition hover:text-gold">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-brand text-gold">
            Newsletter
          </h3>
          <p className="mt-4 text-sm">Sign up and get 10% off your first order.</p>
          <form className="mt-4 flex overflow-hidden rounded-sm border border-cream/15">
            <input
              type="email"
              required
              placeholder="Enter your email"
              aria-label="Email address"
              className="w-full bg-transparent px-3 py-2.5 text-sm text-cream placeholder:text-cream/40 focus:outline-none"
              // Autofill/temp-mail browser extensions inject style + data-* attrs here
              // before React hydrates, which React reports as a mismatch.
              suppressHydrationWarning
            />
            <button
              type="submit"
              aria-label="Subscribe"
              className="flex items-center bg-gold px-3.5 text-charcoal transition hover:bg-gold-light"
            >
              <ArrowRight />
            </button>
          </form>
        </div>
      </div>

      <div className="border-t border-cream/10">
        <div className="container-page flex flex-col items-center justify-between gap-2 py-5 text-xs text-cream/50 sm:flex-row">
          <span>© {new Date().getFullYear()} CivicForest Clothing. All Rights Reserved.</span>
          <div className="flex gap-5">
            <Link href="/contact" className="transition hover:text-gold">
              Privacy Policy
            </Link>
            <Link href="/contact" className="transition hover:text-gold">
              Terms &amp; Conditions
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
