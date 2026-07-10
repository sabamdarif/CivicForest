import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";

import "./globals.css";

const display = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const body = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "CivicForest — Elevated Everyday Wear",
    template: "%s · CivicForest",
  },
  description:
    "Premium everyday clothing crafted for comfort, designed for confidence. Inspired by nature, driven by purpose.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "https://civicforest.local",
  ),
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
