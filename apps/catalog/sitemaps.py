"""Sitemap entries for the catalogue (L4).

Only what a customer can reach: `active_*` everywhere, so a product taken off sale drops out of
the sitemap on the next fetch rather than sending search engines to a 404.
"""

from django.contrib.sitemaps import Sitemap

from . import services


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        # No prefetches: a sitemap reads a slug and a timestamp and nothing else.
        return services._listable().only("slug", "updated_at")

    def lastmod(self, product):
        return product.updated_at


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return services.active_categories().only("slug", "updated_at")

    def lastmod(self, category):
        return category.updated_at


class CollectionSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return services.active_collections().only("slug", "updated_at")

    def lastmod(self, collection):
        return collection.updated_at
