import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ProductGallery } from "@/components/product/ProductGallery";
import { ProductPurchasePanel } from "@/components/product/ProductPurchasePanel";
import { getProduct } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";
import type { ProductDetail } from "@/lib/api/types";

async function fetchProduct(slug: string): Promise<ProductDetail | null> {
  try {
    return await getProduct(slug);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const product = await fetchProduct(slug);
  if (!product) return { title: "Product not found" };
  return {
    title: product.meta_title || product.name,
    description: product.meta_description || product.description.slice(0, 160),
    openGraph: {
      title: product.meta_title || product.name,
      images: product.thumbnail ? [product.thumbnail] : [],
    },
  };
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = await fetchProduct(slug);
  if (!product) notFound();

  return (
    <div className="container-page py-10">
      <nav className="text-xs text-ink/50">
        <Link href="/" className="hover:text-gold">Home</Link>
        <span className="mx-1">›</span>
        <Link href={`/shop?category=${product.category_slug}`} className="hover:text-gold">
          {product.category}
        </Link>
        <span className="mx-1">›</span>
        <span className="text-ink/70">{product.name}</span>
      </nav>

      <div className="mt-6 grid gap-10 md:grid-cols-2">
        <ProductGallery images={product.images} name={product.name} />
        <ProductPurchasePanel product={product} />
      </div>
    </div>
  );
}
