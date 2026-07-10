import type { Metadata } from "next";
import Image from "next/image";

import { LoginForm } from "@/components/account/LoginForm";
import { Monogram } from "@/components/brand/Monogram";
import { FeatureStrip, type Feature } from "@/components/layout/FeatureStrip";
import { LeafIcon } from "@/components/ui/icons";

export const metadata: Metadata = {
  title: "Login",
  description: "Login to your CivicForest account.",
};

const LOGIN_FEATURES: Feature[] = [
  { icon: <LeafIcon className="h-6 w-6" />, title: "Secure Login", body: "Your data is 100% safe with us." },
  { icon: <LeafIcon className="h-6 w-6" />, title: "Easy Returns", body: "Hassle-free returns within 7 days." },
  { icon: <LeafIcon className="h-6 w-6" />, title: "Premium Quality", body: "Finest fabrics and timeless designs." },
  { icon: <LeafIcon className="h-6 w-6" />, title: "Support 24/7", body: "We're here to help you anytime." },
];

export default function LoginPage() {
  return (
    <>
      <div className="grid md:grid-cols-2">
        {/* Left: brand hero */}
        <div className="relative hidden overflow-hidden bg-charcoal text-cream md:block">
          <Image
            src="/brand/hero-black-tee.png"
            alt="CivicForest"
            fill
            sizes="50vw"
            className="object-cover opacity-40"
          />
          <div className="relative z-10 flex h-full flex-col items-center justify-center px-10 text-center">
            <Monogram className="h-12 w-12 text-gold" />
            <h2 className="mt-5 font-serif text-4xl">Welcome Back</h2>
            <p className="mt-1 font-serif text-2xl text-gold">Good to see you again.</p>
            <div className="rule-leaf my-5">
              <LeafIcon className="h-4 w-4" />
            </div>
            <p className="max-w-xs text-sm text-cream/70">
              Login to your account and continue exploring timeless style and premium quality.
            </p>
          </div>
        </div>

        {/* Right: form */}
        <div className="flex items-center justify-center bg-cream-dark/40 px-6 py-16">
          <LoginForm />
        </div>
      </div>

      <FeatureStrip features={LOGIN_FEATURES} />
    </>
  );
}
