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
        <div className="container-page grid items-center gap-8 py-16 md:grid-cols-2 md:py-0 md:min-h-[560px]">
          <div className="relative z-10 animate-fade-in">
            <p className="eyebrow">Premium Quality</p>
            <h1 className="mt-4 font-serif text-5xl leading-[1.05] sm:text-6xl">
              STYLE THAT
              <br />
              <span className="text-gold">SPEAKS</span>
            </h1>
            <div className="rule-leaf my-6">
              <LeafIcon className="h-4 w-4" />
            </div>
            <p className="max-w-md text-cream/70">
              Elevated everyday wear crafted for comfort, designed for confidence.
            </p>
            <Link href="/shop" className="btn-gold mt-8">
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
      </section>

      <FeatureStrip features={HOME_FEATURES} />

      {/* ── Shop by category ─────────────────────────────────── */}
      <section className="container-page py-16">
        <SectionHeading eyebrow="Shop by Category" title="Find Your Style" />
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
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
                sizes="(max-width: 768px) 50vw, 25vw"
                className="object-cover opacity-90 transition duration-500 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-charcoal/90 via-charcoal/10 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 p-5 text-cream">
                <h3 className="font-serif text-xl uppercase tracking-wide">{cat.name}</h3>
                <span className="mt-1 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-brand text-gold">
                  Explore <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Just Landed ──────────────────────────────────────── */}
      {newArrivals.results.length > 0 && (
        <section className="container-page pb-16">
          <div className="flex items-end justify-between">
            <div>
              <p className="eyebrow">New Arrivals</p>
              <h2 className="mt-1 font-serif text-3xl text-ink sm:text-4xl">Just Landed</h2>
            </div>
            <Link
              href="/shop?is_new=true"
              className="inline-flex items-center gap-1.5 text-sm font-semibold uppercase tracking-brand text-ink transition hover:text-gold"
            >
              View All <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {newArrivals.results.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}

      {/* ── Brand values band ────────────────────────────────── */}
      <section className="bg-charcoal text-cream">
        <div className="container-page grid gap-8 py-12 md:grid-cols-3">
          {[
            ["Sustainable Fashion", "Better for you, better for the planet"],
            ["Made for Everyday", "Timeless pieces for every occasion"],
            ["Join the CivicForest Family", "Be part of a community that values style & quality"],
          ].map(([title, body], i) => (
            <div
              key={title}
              className={`flex items-start gap-4 ${
                i < 2 ? "md:border-r md:border-cream/10 md:pr-8" : ""
              }`}
            >
              <Monogram className="h-8 w-8 flex-shrink-0 text-gold" />
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-brand text-gold">
                  {title}
                </h3>
                <p className="mt-1 text-sm text-cream/70">{body}</p>
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
