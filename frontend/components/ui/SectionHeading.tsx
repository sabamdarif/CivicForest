import { LeafIcon } from "@/components/ui/icons";

/** Centered eyebrow + serif heading with the leaf rule, used to open sections. */
export function SectionHeading({
  eyebrow,
  title,
  align = "center",
}: {
  eyebrow?: string;
  title: string;
  align?: "center" | "left";
}) {
  return (
    <div className={align === "center" ? "text-center" : "text-left"}>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h2 className="mt-2 font-serif text-3xl text-ink sm:text-4xl">{title}</h2>
      <div
        className={`mt-3 flex items-center gap-2 text-gold ${
          align === "center" ? "justify-center" : ""
        }`}
      >
        <span className="h-px w-10 bg-gold" />
        <LeafIcon className="h-4 w-4" />
        <span className="h-px w-10 bg-gold" />
      </div>
    </div>
  );
}
