"""The asset budgets from decision P11, in bytes rather than by eye.

A page loads the four shared sheets plus at most one page sheet, so that sum is what the
60 KB ceiling applies to. For JS the budget is per page (50 KB); the whole storefront module
set is summed as a conservative upper bound, since no page loads all of it, and the staff-only
admin and back-office modules are excluded because they never load on a storefront page.
"""

from pathlib import Path

from django.conf import settings

CSS_BUDGET = 60 * 1024
JS_BUDGET = 50 * 1024
SHARED_SHEETS = ("tokens.css", "base.css", "components.css", "layout.css")
# Loaded only inside the admin or the back office, never on a storefront page, so they do not
# count against a storefront page's JS budget.
STAFF_ONLY_JS = {"admin-dashboard.js", "backoffice-reorder.js"}


def _sizes(subdir, pattern):
    directory = Path(settings.BASE_DIR) / "static" / subdir
    return {p.name: p.stat().st_size for p in directory.glob(pattern)}


def test_the_heaviest_page_stays_inside_the_css_budget():
    sheets = _sizes("css", "*.css")
    missing = set(SHARED_SHEETS) - set(sheets)
    assert not missing, f"shared stylesheet renamed or removed: {missing}"

    shared = sum(size for name, size in sheets.items() if name in SHARED_SHEETS)
    page_sheets = {name: size for name, size in sheets.items() if name not in SHARED_SHEETS}
    heaviest, heaviest_size = max(
        page_sheets.items(), key=lambda item: item[1], default=("none", 0)
    )

    total = shared + heaviest_size
    assert total <= CSS_BUDGET, (
        f"{total} bytes for the shared sheets ({shared}) plus {heaviest} ({heaviest_size}) "
        f"exceeds the {CSS_BUDGET} byte budget"
    )


def test_the_javascript_stays_inside_its_budget():
    modules = _sizes("js", "*.js")
    total = sum(size for name, size in modules.items() if name not in STAFF_ONLY_JS)

    assert total <= JS_BUDGET, (
        f"{total} bytes of storefront JavaScript exceeds the {JS_BUDGET} byte budget"
    )
