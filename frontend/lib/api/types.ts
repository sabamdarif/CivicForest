// Shapes returned by the Django catalog/search API. Kept in one place so components
// never guess at server payloads.

export interface ColorOption {
  name: string;
  hex: string;
}

export interface ProductImage {
  id: string;
  url: string | null;
  alt_text: string;
  display_order: number;
}

export interface ProductVariant {
  id: string;
  size: string;
  color: string;
  color_hex: string;
  sku: string;
  price: string;
  in_stock: boolean;
}

export interface ProductListItem {
  id: string;
  name: string;
  slug: string;
  category: string;
  category_slug: string;
  price_from: string;
  is_new: boolean;
  is_bestseller: boolean;
  thumbnail: string | null;
  colors: ColorOption[];
}

export interface ProductDetail extends ProductListItem {
  description: string;
  material: string | null;
  base_price: string;
  meta_title: string;
  meta_description: string;
  images: ProductImage[];
  variants: ProductVariant[];
  sizes: string[];
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string;
  display_order: number;
  product_count?: number;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface SuggestionHit {
  id: string;
  name: string;
  slug: string;
  category: string | null;
  category_slug?: string | null;
  price_from: number | null;
  thumbnail: string | null;
}

export interface SearchResponse {
  query: string;
  results: SuggestionHit[];
  count: number;
  page: number;
  page_size: number;
  engine?: string;
}
