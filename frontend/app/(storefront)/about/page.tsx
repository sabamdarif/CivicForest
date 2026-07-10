import type { Metadata } from "next";
import Image from "next/image";

import { LeafIcon, ArrowRight } from "@/components/ui/icons";

export const metadata: Metadata = {
  title: "About Us",
  description:
    "More than clothing, it's a mindset. CivicForest crafts timeless pieces inspired by nature and driven by purpose.",
};

const VALUES = [
  ["Sustainable", "We choose eco-friendly materials and ethical practices."],
  ["Quality First", "Premium fabrics, fine craftsmanship and attention to every detail."],
  ["Made for Everyone", "Timeless designs that fit every style, every body, every person."],
  ["Community Driven", "We're more than a brand. We're a community that cares."],
];

const TIMELINE = [
  ["2021", "The Beginning", "Started with a vision to create sustainable, timeless clothing."],
  ["2022", "First Collection", "Launched our first collection focused on quality and comfort."],
  ["2024 & Beyond", "Growing Together", "Expanding our community while staying true to our values."],
];

const TEAM = [
  ["Arjun Mehta", "Founder & CEO"],
  ["Neha Sharma", "Design Lead"],
  ["Rohit Verma", "Product Director"],
  ["Simran Kaur", "Community Manager"],
];

export default function AboutPage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-charcoal text-cream">
        <div className="container-page grid items-center gap-6 py-16 md:grid-cols-2 md:min-h-[440px]">
          <div>
            <p className="eyebrow">Who We Are</p>
            <h1 className="mt-4 font-serif text-4xl leading-tight sm:text-5xl">
              MORE THAN CLOTHING,
              <br />
              <span className="text-gold">IT&apos;S A MINDSET.</span>
            </h1>
            <div className="rule-leaf my-5">
              <LeafIcon className="h-4 w-4" />
            </div>
            <p className="max-w-md text-cream/70">
              At CivicForest, we believe that what you wear is a reflection of who you are
              and what you stand for. We create timeless pieces that blend comfort, quality
              and style — made for everyday life, inspired by nature and driven by purpose.
            </p>
          </div>
        </div>
        <div className="absolute inset-y-0 right-0 hidden w-1/2 md:block">
          <Image src="/brand/tee-black-back.png" alt="CivicForest" fill sizes="50vw" className="object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-charcoal via-charcoal/30 to-transparent" />
        </div>
      </section>

      {/* Our story */}
      <section className="container-page grid gap-10 py-16 md:grid-cols-3">
        <div className="relative aspect-square overflow-hidden rounded-sm bg-cream-dark md:col-span-1">
          <Image src="/brand/sweatshirt-grey.png" alt="Crafted for life" fill sizes="33vw" className="object-cover" />
        </div>
        <div className="md:col-span-1">
          <p className="eyebrow">Our Story</p>
          <h2 className="mt-2 font-serif text-3xl text-ink">
            Built on Passion.
            <br />
            <span className="text-gold">Driven by Purpose.</span>
          </h2>
          <p className="mt-5 text-sm leading-relaxed text-ink/70">
            CivicForest was born from a simple idea — to create clothing that feels good,
            looks great, and does good.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-ink/70">
            From the beginning, our mission has been to craft premium everyday wear that
            respects people and the planet. Every thread, every detail, every decision is
            made with intention.
          </p>
        </div>
        <ol className="space-y-6 md:col-span-1">
          {TIMELINE.map(([year, title, body]) => (
            <li key={year} className="border-l-2 border-gold/40 pl-4">
              <p className="text-sm font-semibold text-gold">{year}</p>
              <h3 className="mt-0.5 font-serif text-lg text-ink">{title}</h3>
              <p className="mt-1 text-sm text-ink/60">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Values band */}
      <section className="bg-charcoal text-cream">
        <div className="container-page py-14">
          <div className="text-center">
            <p className="eyebrow">Our Values</p>
          </div>
          <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map(([title, body], i) => (
              <div
                key={title}
                className={`text-center ${i < 3 ? "lg:border-r lg:border-cream/10" : ""}`}
              >
                <LeafIcon className="mx-auto h-7 w-7 text-gold" />
                <h3 className="mt-3 text-sm font-semibold uppercase tracking-brand text-gold">
                  {title}
                </h3>
                <p className="mx-auto mt-2 max-w-[16rem] text-sm text-cream/60">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="container-page py-16">
        <div className="text-center">
          <p className="eyebrow">The People Behind CivicForest</p>
          <h2 className="mt-2 font-serif text-3xl text-ink">A Team That Cares</h2>
        </div>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {TEAM.map(([name, role]) => (
            <div key={name} className="relative aspect-[4/5] overflow-hidden rounded-sm bg-charcoal">
              <div className="absolute inset-0 flex items-center justify-center font-serif text-5xl text-cream/10">
                {name.split(" ").map((n) => n[0]).join("")}
              </div>
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-charcoal to-transparent p-4 text-center text-cream">
                <p className="font-serif text-lg">{name}</p>
                <p className="text-xs uppercase tracking-brand text-gold">{role}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
