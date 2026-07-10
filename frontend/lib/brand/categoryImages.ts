// Maps category slugs to the brand photography used as tile/hero backgrounds.
// Falls back to a neutral image when a category has no dedicated shot.

const MAP: Record<string, string> = {
  "t-shirts": "/brand/tee-black-back.png",
  hoodies: "/brand/hoodie-green.png",
  sweatshirts: "/brand/sweatshirt-grey.png",
  jackets: "/brand/rack-new-arrivals.png",
  bottoms: "/brand/polo-navy.png",
};

export function categoryImage(slug: string): string {
  return MAP[slug] ?? "/brand/rack-new-arrivals.png";
}
