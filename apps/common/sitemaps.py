"""The sitemap registry (L4), and the fixed routes that have no model behind them.

`STATIC_ROUTES` lists only paths that are actually mounted: a sitemap that promises a page a
milestone has not built yet sends search engines to a 404. The content pages come from
`ContentPageSitemap`, which lists only published pages whose slug has a mounted route, so
unpublishing a page also drops it from the sitemap.
"""

from django.contrib.sitemaps import Sitemap

from apps.catalog.sitemaps import CategorySitemap, CollectionSitemap, ProductSitemap
from apps.content.urls import MOUNTED_PAGE_SLUGS

STATIC_ROUTES = ["/", "/shop/", "/collections/", "/faq/"]


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1.0

    def items(self):
        return STATIC_ROUTES

    def location(self, item):
        return item


class ContentPageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        from apps.content.models import Page

        return list(Page.objects.filter(is_published=True, slug__in=MOUNTED_PAGE_SLUGS))

    def location(self, page):
        return f"/{page.slug}/"

    def lastmod(self, page):
        return page.updated_at


SITEMAPS = {
    "static": StaticViewSitemap,
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "collections": CollectionSitemap,
    "pages": ContentPageSitemap,
}
