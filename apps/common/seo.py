"""JSON-LD and canonical URLs, in one place because L4 lists them together.

Two rules hold here. Every URL is absolute, because a relative one in JSON-LD is ignored. And
nothing is asserted that the site cannot back: no `aggregateRating` until `apps/reviews` exists
in M9, because an invented one is both a Google manual action and the sort of fabrication J9
forbids everywhere else on the page.
"""

SCHEMA = "https://schema.org"


def absolute(request, path: str) -> str:
    return request.build_absolute_uri(path)


def breadcrumb_list(request, trail: list[tuple[str, str]], current: str) -> dict:
    """E10's `BreadcrumbList`. ``trail`` is the (label, href) ancestors; ``current`` is the page
    you are on, which has no href because it is not a link."""
    items = [*trail, (current, request.path)]
    return {
        "@context": SCHEMA,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": label,
                "item": absolute(request, href),
            }
            for position, (label, href) in enumerate(items, start=1)
        ],
    }


def organisation(request) -> dict:
    return {
        "@context": SCHEMA,
        "@type": "Organization",
        "name": "CivicForest Clothing",
        "url": absolute(request, "/"),
        "description": "Premium menswear made in India.",
    }


def website(request) -> dict:
    """The `WebSite` node, with the search action M3 mounts /search/ for."""
    return {
        "@context": SCHEMA,
        "@type": "WebSite",
        "name": "CivicForest Clothing",
        "url": absolute(request, "/"),
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": absolute(request, "/search/?q={search_term_string}"),
            },
            "query-input": "required name=search_term_string",
        },
    }


def product_offer(request, product, panel: dict, currency: str) -> dict:
    """`Product` plus one `Offer`, and deliberately no `aggregateRating` (see the module note).

    The price is the one the panel resolved, so the markup and the page can never quote
    different numbers.
    """
    url = absolute(request, product.get_absolute_url())
    availability = "InStock" if panel["in_stock"] else "OutOfStock"
    data = {
        "@context": SCHEMA,
        "@type": "Product",
        "name": product.name,
        "description": product.meta_description or product.description,
        "url": url,
        "image": [absolute(request, image.image.url) for image in panel["images"] if image.image],
        "brand": {"@type": "Brand", "name": "CivicForest Clothing"},
        "countryOfOrigin": product.country_of_origin,
        "category": product.category.name if product.category else "",
        "offers": {
            "@type": "Offer",
            "url": url,
            "price": f"{panel['price']:.2f}",
            "priceCurrency": currency,
            "availability": f"{SCHEMA}/{availability}",
            "itemCondition": f"{SCHEMA}/NewCondition",
        },
    }
    variant = panel["variant"]
    if variant and variant.sku:
        data["sku"] = variant.sku
    if product.material:
        data["material"] = product.material.name
    if panel["mrp"]:
        data["offers"]["priceSpecification"] = {
            "@type": "PriceSpecification",
            "price": f"{panel['mrp']:.2f}",
            "priceCurrency": currency,
            "valueAddedTaxIncluded": True,
        }
    return {key: value for key, value in data.items() if value not in ("", [], None)}
