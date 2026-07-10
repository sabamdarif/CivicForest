// Display formatting only — never used for any server-side money math (plan.md §10).

const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

/** Format a rupee amount from a string or number, e.g. "799.00" -> "₹799". */
export function formatPrice(value: string | number): string {
  const n = typeof value === "string" ? Number.parseFloat(value) : value;
  if (Number.isNaN(n)) return "";
  return inr.format(n);
}
