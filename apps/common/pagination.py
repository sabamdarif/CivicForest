from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    """Page-number pagination with a hard server-side ceiling.

    A client may tune ``page_size`` but can never exceed ``max_page_size`` — this is
    what stops ``?page_size=10000`` catalog scraping in a single call (plan.md §6).
    """

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 48
