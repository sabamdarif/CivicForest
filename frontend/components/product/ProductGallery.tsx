"use client";

import Image from "next/image";
import { useState } from "react";

import type { ProductImage } from "@/lib/api/types";

export function ProductGallery({
  images,
  name,
}: {
  images: ProductImage[];
  name: string;
}) {
  const [active, setActive] = useState(0);
  const current = images[active];

  return (
    <div className="flex flex-col-reverse gap-4 md:flex-row">
      {images.length > 1 && (
        <div className="flex gap-3 md:flex-col">
          {images.map((img, i) => (
            <button
              key={img.id}
              type="button"
              onClick={() => setActive(i)}
              className={`relative h-20 w-16 overflow-hidden rounded-sm border transition ${
                i === active ? "border-gold" : "border-black/10 hover:border-black/30"
              }`}
            >
              {img.url && (
                <Image src={img.url} alt={img.alt_text || name} fill sizes="64px" className="object-cover" />
              )}
            </button>
          ))}
        </div>
      )}

      <div className="relative aspect-[4/5] flex-1 overflow-hidden rounded-sm bg-cream-dark">
        {current?.url ? (
          <Image
            src={current.url}
            alt={current.alt_text || name}
            fill
            priority
            sizes="(max-width: 768px) 100vw, 50vw"
            className="object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center font-serif text-6xl text-charcoal/15">
            cF
          </div>
        )}
      </div>
    </div>
  );
}
