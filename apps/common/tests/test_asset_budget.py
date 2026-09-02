"""The asset budgets from decision P11, in bytes rather than by eye.

A page loads the four shared sheets plus at most one page sheet, so that sum is what the
60 KB ceiling applies to. M10 task 3 extends this to a per-page measurement in CI once there
are pages whose sheets could overlap.
"""

from pathlib import Path

from django.conf import settings

CSS_BUDGET = 60 * 1024
JS_BUDGET = 50 * 1024
SHARED_SHEETS = ("tokens.css", "base.css", "components.css", "layout.css")


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
    total = sum(modules.values())

    assert total <= JS_BUDGET, f"{total} bytes of JavaScript exceeds the {JS_BUDGET} byte budget"
