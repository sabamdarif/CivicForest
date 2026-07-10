"use client";

import { useState } from "react";

const FAQS: [string, string][] = [
  ["How can I track my order?", "Once your order ships, we email you a tracking link. You can also use Track Order in the footer."],
  ["What payment methods do you accept?", "We accept UPI, all major cards, and net banking through our secure Razorpay checkout."],
  ["What is your return policy?", "Hassle-free returns and exchanges within 7 days of delivery on unworn items with tags."],
  ["How long does delivery take?", "Metros typically receive orders in 2–4 business days; the rest of India in 4–7 days."],
  ["Do you offer international shipping?", "Not yet — we currently ship across India. International shipping is coming soon."],
  ["Still have a question?", "Reach us at hello@civicforest.com and we'll reply as soon as possible."],
];

export function FaqAccordion() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {FAQS.map(([q, a], i) => (
        <div key={q} className="rounded-sm border border-black/10 bg-cream">
          <button
            type="button"
            onClick={() => setOpen(open === i ? null : i)}
            className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left text-sm font-medium text-ink"
            aria-expanded={open === i}
          >
            {q}
            <span className="text-gold">{open === i ? "−" : "+"}</span>
          </button>
          {open === i && <p className="px-5 pb-4 text-sm text-ink/60">{a}</p>}
        </div>
      ))}
    </div>
  );
}
