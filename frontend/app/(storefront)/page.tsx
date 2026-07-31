import Image from "next/image";
import Link from "next/link";

import { ProductCard } from "@/components/product/ProductCard";
import { FeatureStrip, type Feature } from "@/components/layout/FeatureStrip";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { ArrowRight, LeafIcon } from "@/components/ui/icons";
import { Monogram } from "@/components/brand/Monogram";
import { getCategories, getProducts, safe } from "@/lib/api/catalog";
import { categoryImage } from "@/lib/brand/categoryImages";
import type { Category, Paginated, ProductListItem } from "@/lib/api/types";

const HOME_FEATURES: Feature[] = [
  { icon: <LeafIcon className="h-7 w-7" />, title: "Premium Fabric", body: "Superior comfort and durability" },
  { icon: <ShieldIcon />, title: "Quality Assured", body: "Crafted with attention to detail" },
  { icon: <TruckIcon />, title: "Fast Delivery", body: "Quick delivery to your doorstep" },
  { icon: <ReturnIcon />, title: "Easy Returns", body: "Hassle-free returns and exchanges" },
];

export default async function HomePage() {
  const [categories, newArrivals] = await Promise.all([
    safe<Category[]>(getCategories(), []),
    safe<Paginated<ProductListItem>>(
      getProducts({ is_new: true, page_size: 4 }),
      { count: 0, next: null, previous: null, results: [] },
    ),
  ]);

  const tiles = categories.slice(0, 4);

  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-charcoal text-cream">
        <div className="container-page grid items-center gap-8 py-12 sm:py-16 md:grid-cols-2 md:py-0 md:min-h-[560px]">
          <div className="relative z-10 animate-fade-in">
            <p className="eyebrow">Premium Quality</p>
            <h1 className="mt-4 font-serif text-4xl leading-[1.1] sm:text-6xl sm:leading-[1.05]">
              STYLE THAT
              <br />
              <span className="text-gold">SPEAKS</span>
            </h1>
            <div className="rule-leaf my-5 sm:my-6">
              <LeafIcon className="h-4 w-4" />
            </div>
            <p className="max-w-md text-sm sm:text-base text-cream/70">
              Elevated everyday wear crafted for comfort, designed for confidence.
            </p>
            <Link href="/shop" className="btn-gold mt-6 sm:mt-8">
              Shop Now <ArrowRight />
            </Link>
          </div>
        </div>
        <div className="absolute inset-y-0 right-0 hidden w-1/2 md:block">
          <Image
            src="/brand/hero-black-tee.png"
            alt="CivicForest signature tee"
            fill
            priority
            sizes="50vw"
            className="object-cover object-center"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-charcoal via-charcoal/40 to-transparent" />
        </div>
        {/* Subtle decorative gold glow background on mobile */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-gold/10 blur-3xl md:hidden" />
      </section>

      <FeatureStrip features={HOME_FEATURES} />

      {/* ── Shop by category ─────────────────────────────────── */}
      <section className="container-page py-12 sm:py-16">
        <SectionHeading eyebrow="Shop by Category" title="Find Your Style" />
        <div className="mt-8 sm:mt-10 grid grid-cols-2 gap-3.5 sm:gap-5 lg:grid-cols-4">
          {tiles.map((cat) => (
            <Link
              key={cat.id}
              href={`/shop?category=${cat.slug}`}
              className="group relative aspect-[3/4] overflow-hidden rounded-sm bg-charcoal"
            >
              <Image
                src={categoryImage(cat.slug)}
                alt={cat.name}
                fill
                sizes="(max-width: 640px) 50vw, 25vw"
                className="object-cover opacity-90 transition duration-500 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-charcoal/90 via-charcoal/10 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 p-3.5 sm:p-5 text-cream">
                <h3 className="font-serif text-lg sm:text-xl uppercase tracking-wide">{cat.name}</h3>
                <span className="mt-1 inline-flex items-center gap-1.5 text-[10px] sm:text-xs font-semibold uppercase tracking-brand text-gold">
                  Explore <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Just Landed ──────────────────────────────────────── */}
      {newArrivals.results.length > 0 && (
        <section className="container-page pb-12 sm:pb-16">
          <div className="flex items-end justify-between">
            <div>
              <p className="eyebrow">New Arrivals</p>
              <h2 className="mt-1 font-serif text-2xl text-ink sm:text-4xl">Just Landed</h2>
            </div>
            <Link
              href="/shop?is_new=true"
              className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-semibold uppercase tracking-brand text-ink transition hover:text-gold"
            >
              View All <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="mt-6 sm:mt-8 grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4 sm:gap-5">
            {newArrivals.results.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}

      {/* ── Brand values band ────────────────────────────────── */}
      <section className="bg-charcoal text-cream">
        <div className="container-page grid gap-6 py-10 sm:py-12 md:grid-cols-3">
          {[
            ["Sustainable Fashion", "Better for you, better for the planet"],
            ["Made for Everyday", "Timeless pieces for every occasion"],
            ["Join the CivicForest Family", "Be part of a community that values style & quality"],
          ].map(([title, body], i) => (
            <div
              key={title}
              className={`flex items-start gap-4 pb-6 last:pb-0 md:pb-0 ${
                i < 2 ? "border-b border-cream/10 md:border-b-0 md:border-r md:pr-8" : ""
              }`}
            >
              <Monogram className="h-7 w-7 sm:h-8 sm:w-8 flex-shrink-0 text-gold" />
              <div>
                <h3 className="text-xs sm:text-sm font-semibold uppercase tracking-brand text-gold">
                  {title}
                </h3>
                <p className="mt-1 text-xs sm:text-sm text-cream/70">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function ShieldIcon() {
  return (
    <svg className="h-7 w-7 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="1.5">
      <path d="M12 3l7 3v5c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6l7-3z" strokeLinejoin="round" />
      <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TruckIcon() {
  return (
    <svg className="h-7 w-7 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="1.5">
      <path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z" strokeLinejoin="round" />
      <circle cx="7" cy="18" r="1.6" />
      <circle cx="17" cy="18" r="1.6" />
    </svg>
  );
}

function ReturnIcon() {
  return (
    <svg className="h-7 w-7 stroke-current" viewBox="0 0 24 24" fill="none" strokeWidth="1.5">
      <path d="M4 12a8 8 0 018-8c3 0 5.6 1.7 7 4.2" strokeLinecap="round" />
      <path d="M20 4v4h-4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M20 12a8 8 0 01-8 8c-3 0-5.6-1.7-7-4.2" strokeLinecap="round" />
      <path d="M4 20v-4h4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
