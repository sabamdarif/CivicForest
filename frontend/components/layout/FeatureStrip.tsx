import type { ReactNode } from "react";

export interface Feature {
  icon: ReactNode;
  title: string;
  body: string;
}

/** The 4-up assurance strip (Premium Fabric / Quality Assured / …) seen on several
 * pages. Rendered on a cream band with gold line-icons. */
export function FeatureStrip({ features }: { features: Feature[] }) {
  return (
    <section className="border-y border-black/5 bg-cream">
      <div className="container-page grid gap-6 py-8 sm:grid-cols-2 lg:grid-cols-4">
        {features.map((f, i) => (
          <div
            key={f.title}
            className={`flex items-start gap-3 ${
              i < features.length - 1 ? "lg:border-r lg:border-black/10 lg:pr-6" : ""
            }`}
          >
            <span className="mt-0.5 text-gold">{f.icon}</span>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-ink">
                {f.title}
              </h3>
              <p className="mt-0.5 text-sm text-ink/60">{f.body}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
