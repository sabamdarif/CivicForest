import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { LeafIcon, ArrowRight } from "@/components/ui/icons";
import { getCategories, safe } from "@/lib/api/catalog";
import { categoryImage } from "@/lib/brand/categoryImages";
import type { Category } from "@/lib/api/types";

export const metadata: Metadata = {
  title: "Collections",
  description: "Timeless styles. Premium fabrics. Collections crafted for every version of you.",
};

const BLURBS: Record<string, [string, string]> = {
  "t-shirts": ["Everyday Essentials", "Minimal. Comfortable. Made for every day."],
  hoodies: ["Cozy & Stylish", "Warmth meets style. Perfect for all seasons."],
  sweatshirts: ["Comfort Redefined", "Soft, durable & made to last."],
  jackets: ["Layered Looks", "Structured pieces for cooler days."],
  bottoms: ["Smart Casuals", "Tailored comfort from waist to hem."],
};

const VALUES = [
  ["Premium Quality", "Carefully selected fabrics"],
  ["Made to Last", "Durable designs for everyday wear"],
  ["Perfect Fit", "Tailored to give you the best fit"],
  ["Loved by All", "Trusted by thousands of happy customers"],
];

export default async function CollectionsPage() {
  const categories = await safe<Category[]>(getCategories(), []);
  const featured = categories.slice(0, 4);

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-charcoal text-cream">
        <div className="container-page grid items-center gap-6 py-16 md:grid-cols-2 md:min-h-[420px]">
          <div>
            <p className="text-xs text-cream/50">
              Home <span className="mx-1">›</span> Collections
            </p>
            <h1 className="mt-3 font-serif text-5xl">Our Collections</h1>
            <div className="rule-leaf my-5">
              <LeafIcon className="h-4 w-4" />
            </div>
            <p className="max-w-md text-cream/70">
              Timeless styles. Premium fabrics. Collections crafted for every version of you.
            </p>
          </div>
        </div>
        <div className="absolute inset-y-0 right-0 hidden w-1/2 md:block">
          <Image src="/brand/tee-black-back.png" alt="CivicForest" fill sizes="50vw" className="object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-charcoal via-charcoal/30 to-transparent" />
        </div>
      </section>

      {/* Collection cards */}
      <section className="container-page py-14">
        <div className="grid gap-6 md:grid-cols-2">
          {featured.map((cat) => {
            const [eyebrow, blurb] = BLURBS[cat.slug] ?? ["Collection", cat.description];
            return (
              <div key={cat.id} className="relative overflow-hidden rounded-sm bg-charcoal-800">
                <div className="grid grid-cols-2">
                  <div className="p-8">
                    <p className="eyebrow">{eyebrow}</p>
                    <h2 className="mt-3 font-serif text-2xl uppercase leading-tight text-cream">
                      {cat.name}
                      <br />Collection
                    </h2>
                    <span className="my-4 block h-px w-16 bg-gold" />
                    <p className="text-sm text-cream/60">{blurb}</p>
                    <Link href={`/shop?category=${cat.slug}`} className="btn-gold mt-6 text-xs">
                      Shop {cat.name} <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                  <div className="relative min-h-[280px]">
                    <Image
                      src={categoryImage(cat.slug)}
                      alt={cat.name}
                      fill
                      sizes="(max-width: 768px) 50vw, 25vw"
                      className="object-cover"
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* New arrivals banner */}
        <Link
          href="/shop?is_new=true"
          className="group relative mt-6 flex min-h-[220px] items-center overflow-hidden rounded-sm bg-charcoal"
        >
          <Image
            src="/brand/rack-new-arrivals.png"
            alt="New arrivals"
            fill
            sizes="100vw"
            className="object-cover opacity-60 transition duration-500 group-hover:scale-105"
          />
          <div className="relative z-10 p-10 text-cream">
            <p className="eyebrow">New In</p>
            <h2 className="mt-2 font-serif text-3xl uppercase">New Arrivals</h2>
            <p className="mt-2 max-w-sm text-sm text-cream/70">
              Discover the latest styles just added.
            </p>
            <span className="btn-gold mt-5 text-xs">
              Explore Now <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </Link>
      </section>

      {/* Values */}
      <section className="border-t border-black/5 bg-cream">
        <div className="container-page grid gap-6 py-10 sm:grid-cols-2 lg:grid-cols-4">
          {VALUES.map(([title, body], i) => (
            <div
              key={title}
              className={`flex items-start gap-3 ${i < 3 ? "lg:border-r lg:border-black/10 lg:pr-6" : ""}`}
            >
              <LeafIcon className="mt-0.5 h-6 w-6 text-gold" />
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-ink">{title}</h3>
                <p className="mt-0.5 text-sm text-ink/60">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
