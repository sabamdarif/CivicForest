"""The sitemap registry (L4), and the fixed routes that have no model behind them.

`STATIC_ROUTES` lists only paths that are actually mounted: a sitemap that promises a page a
milestone has not built yet sends search engines to a 404. M9 task 10 adds the content pages
here as it writes them.
"""

from django.contrib.sitemaps import Sitemap

from apps.catalog.sitemaps import CategorySitemap, CollectionSitemap, ProductSitemap

STATIC_ROUTES = ["/", "/shop/", "/collections/"]


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1.0

    def items(self):
        return STATIC_ROUTES

    def location(self, item):
        return item


SITEMAPS = {
    "static": StaticViewSitemap,
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "collections": CollectionSitemap,
}
