import type { Metadata } from "next";
import Image from "next/image";

import { FaqAccordion } from "@/components/contact/FaqAccordion";
import { LeafIcon, ArrowRight } from "@/components/ui/icons";
import { SectionHeading } from "@/components/ui/SectionHeading";

export const metadata: Metadata = {
  title: "Contact",
  description: "We'd love to hear from you. Questions about products or your order? Reach out anytime.",
};

const CARDS = [
  ["Visit Us", ["Civicforest Clothing Pvt. Ltd.", "301, Greenway Plaza,", "SG Highway, Ahmedabad,", "Gujarat – 380051, India"]],
  ["Email Us", ["hello@civicforest.com", "support@civicforest.com", "", "We'll reply as soon as possible."]],
  ["Call Us", ["+91 98765 43210", "+91 98765 43211", "", "Mon – Sat: 10AM – 7PM"]],
  ["Store Hours", ["Monday – Saturday", "10:00 AM – 7:00 PM", "Sunday: Closed"]],
];

export default function ContactPage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-charcoal text-cream">
        <div className="container-page grid items-center gap-6 py-16 md:grid-cols-2 md:min-h-[380px]">
          <div>
            <p className="eyebrow">Get in Touch</p>
            <h1 className="mt-4 font-serif text-4xl leading-tight sm:text-5xl">
              We&apos;d Love to <span className="text-gold">Hear</span> From You
            </h1>
            <div className="rule-leaf my-5">
              <LeafIcon className="h-4 w-4" />
            </div>
            <p className="max-w-md text-cream/70">
              Have a question about our products, your order, or anything else? We&apos;re
              here to help. Reach out to us anytime!
            </p>
          </div>
        </div>
        <div className="absolute inset-y-0 right-0 hidden w-1/2 md:block">
          <Image src="/brand/tee-black-back.png" alt="CivicForest" fill sizes="50vw" className="object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-charcoal via-charcoal/30 to-transparent" />
        </div>
      </section>

      {/* Contact cards */}
      <section className="container-page py-12">
        <div className="grid gap-6 rounded-sm bg-cream-dark/50 p-8 sm:grid-cols-2 lg:grid-cols-4">
          {CARDS.map(([title, lines]) => (
            <div key={title as string}>
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-gold/15 text-gold">
                <LeafIcon className="h-5 w-5" />
              </div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-ink">{title}</h3>
              <div className="mt-2 space-y-0.5 text-sm text-ink/60">
                {(lines as string[]).map((l, i) => (l ? <p key={i}>{l}</p> : <br key={i} />))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Message form */}
      <section className="container-page grid gap-10 pb-16 md:grid-cols-2">
        <div>
          <p className="eyebrow">Send Us a Message</p>
          <h2 className="mt-2 font-serif text-3xl text-ink">We&apos;re Here to Help</h2>
          <form className="mt-6 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <input className="input-field" placeholder="Your Name" aria-label="Your name" />
              <input className="input-field" type="email" placeholder="Your Email" aria-label="Your email" />
            </div>
            <input className="input-field" placeholder="Order Number (Optional)" aria-label="Order number" />
            <input className="input-field" placeholder="Subject" aria-label="Subject" />
            <textarea className="input-field min-h-32" placeholder="Your Message" aria-label="Your message" />
            <button type="button" className="btn-dark">
              Send Message <ArrowRight />
            </button>
            <p className="text-xs text-ink/50">
              We respect your privacy. Your information is safe with us.
            </p>
          </form>
        </div>
        <div className="relative min-h-[360px] overflow-hidden rounded-sm bg-charcoal">
          <Image src="/brand/hero-black-tee.png" alt="CivicForest craftsmanship" fill sizes="50vw" className="object-cover opacity-80" />
          <div className="absolute inset-0 bg-gradient-to-t from-charcoal/90 to-transparent" />
          <p className="absolute bottom-6 left-6 right-6 font-serif text-lg text-cream">
            Every thread, every detail, crafted with purpose.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-black/5 bg-cream">
        <div className="container-page py-14">
          <SectionHeading eyebrow="FAQs" title="Frequently Asked Questions" />
          <div className="mt-10">
            <FaqAccordion />
          </div>
        </div>
      </section>
    </>
  );
}
