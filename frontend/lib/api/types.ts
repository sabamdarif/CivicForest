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

// ─── Cart & wishlist ─────────────────────────────────────────────────────────

export interface CartLine {
  variant_id: string;
  product_name: string;
  product_slug: string;
  size: string;
  color: string;
  sku: string;
  thumbnail: string | null;
  unit_price: string;
  quantity: number;
  line_total: string;
  available_stock: number;
}

export interface Cart {
  lines: CartLine[];
  subtotal: string;
  discount: string;
  shipping: string;
  total: string;
  coupon_code: string | null;
  item_count: number;
}

export interface WishlistEntry {
  id: string;
  product_id: string;
  name: string;
  slug: string;
  price_from: string;
  thumbnail: string | null;
}

// ─── Orders & checkout ───────────────────────────────────────────────────────

export interface OrderItem {
  id: string;
  product_name: string;
  variant_sku: string;
  size: string;
  color: string;
  unit_price: string;
  quantity: number;
  line_total: string;
  is_custom: boolean;
}

export interface Order {
  order_number: string;
  status: string;
  status_display: string;
  email: string;
  phone: string;
  ship_full_name: string;
  ship_line1: string;
  ship_line2: string;
  ship_city: string;
  ship_state: string;
  ship_postal_code: string;
  ship_country: string;
  currency: string;
  subtotal: string;
  discount: string;
  shipping_fee: string;
  total: string;
  coupon_code: string | null;
  has_custom_items: boolean;
  items: OrderItem[];
  created_at: string;
}

export interface ShippingAddressInput {
  full_name: string;
  phone: string;
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postal_code: string;
  country?: string;
}

export interface CheckoutResponse {
  order_number: string;
  razorpay_order_id: string;
  razorpay_key_id: string;
  amount: string;
  amount_paise: number;
  currency: string;
}

// ─── Account ─────────────────────────────────────────────────────────────────

export interface Address {
  id: string;
  kind: "shipping" | "billing";
  full_name: string;
  phone: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  is_default: boolean;
  created_at: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  marketing_opt_in: boolean;
}

// ─── Custom design orders (Qikink print) ─────────────────────────────────────

export interface CustomDesignOrder {
  id: string;
  variant: string;
  print_type_id: number;
  placement_sku: string;
  width_inches: string;
  height_inches: string;
  quantity: number;
  review_status: string;
  submit_status: string;
  qikink_status: string;
  tracking_awb: string;
  tracking_link: string;
  design_url: string | null;
  created_at: string;
}
