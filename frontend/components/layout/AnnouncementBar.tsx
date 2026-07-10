import { ArrowRight } from "@/components/ui/icons";

/** Top strip from the mockups: "FREE SHIPPING ON ALL ORDERS ABOVE ₹999". */
export function AnnouncementBar() {
  return (
    <div className="bg-charcoal text-cream">
      <div className="container-page flex h-9 items-center justify-center gap-2 text-[11px] font-semibold uppercase tracking-brand text-gold">
        <ArrowRight className="h-3.5 w-3.5" />
        Free shipping on all orders above ₹999
      </div>
    </div>
  );
}
