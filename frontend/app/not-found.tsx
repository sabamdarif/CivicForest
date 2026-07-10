import Link from "next/link";

import { Monogram } from "@/components/brand/Monogram";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-charcoal px-6 text-center text-cream">
      <Monogram className="h-12 w-12 text-gold" />
      <h1 className="mt-6 font-serif text-5xl">404</h1>
      <p className="mt-2 text-cream/60">This page wandered off the trail.</p>
      <Link href="/" className="btn-gold mt-8">
        Back to Home
      </Link>
    </div>
  );
}
