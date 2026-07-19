"""Shared factory_boy factories for tests (plan.md §12 — testing breadth).

One place for object-graph construction so new tests don't re-write the same
Category→Product→Variant boilerplate. Import from any app's tests:

    from apps.common.factories import UserFactory, ProductVariantFactory
"""

from __future__ import annotations

from decimal import Decimal

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.cart.models import Cart, CartItem, Coupon
from apps.catalog.models import Category, Product, ProductVariant
from apps.orders.models import Order, OrderItem


class UserFactory(DjangoModelFactory):
    class Meta:
        model = get_user_model()
        django_get_or_create = ["email"]

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.django.Password("pw-1234567!")


class StaffUserFactory(UserFactory):
    email = factory.Sequence(lambda n: f"staff{n}@example.com")
    is_staff = True


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ["slug"]

    name = "T-Shirts"
    slug = "t-shirts"


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product
        django_get_or_create = ["slug"]

    name = factory.Sequence(lambda n: f"Tee {n}")
    slug = factory.Sequence(lambda n: f"tee-{n}")
    category = factory.SubFactory(CategoryFactory)
    base_price = Decimal("800.00")
    is_active = True


class ProductVariantFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    size = "M"
    color = "Black"
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    stock_quantity = 5
    is_active = True


class CouponFactory(DjangoModelFactory):
    class Meta:
        model = Coupon
        django_get_or_create = ["code"]

    code = factory.Sequence(lambda n: f"SAVE{n}")
    discount_type = Coupon.DiscountType.PERCENT
    value = Decimal("10")
    is_active = True


class CartFactory(DjangoModelFactory):
    class Meta:
        model = Cart

    user = factory.SubFactory(UserFactory)


class GuestCartFactory(DjangoModelFactory):
    class Meta:
        model = Cart

    user = None
    session_key = factory.Sequence(lambda n: f"sess-{n:06d}")


class CartItemFactory(DjangoModelFactory):
    class Meta:
        model = CartItem

    cart = factory.SubFactory(CartFactory)
    variant = factory.SubFactory(ProductVariantFactory)
    quantity = 1


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    status = Order.Status.PAYMENT_PENDING
    email = factory.LazyAttribute(lambda o: o.user.email)
    ship_full_name = "Test Buyer"
    ship_line1 = "1 MG Road"
    ship_city = "Bengaluru"
    ship_state = "Karnataka"
    ship_postal_code = "560001"
    subtotal = Decimal("800.00")
    discount = Decimal("0.00")
    shipping_fee = Decimal("59.00")
    total = Decimal("859.00")


class OrderItemFactory(DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    variant = factory.SubFactory(ProductVariantFactory)
    product_name = factory.LazyAttribute(lambda o: o.variant.product.name)
    variant_sku = factory.LazyAttribute(lambda o: o.variant.sku)
    size = factory.LazyAttribute(lambda o: o.variant.size)
    color = factory.LazyAttribute(lambda o: o.variant.color)
    unit_price = Decimal("800.00")
    quantity = 1
    line_total = Decimal("800.00")
