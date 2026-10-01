#!/usr/bin/env python3
"""Local load check for the two hot read endpoints (M10.4): search-suggest and shop-list.

Not a CI gate: GitHub runners are too noisy for a p95 assertion to mean anything. Run it against
a local or preview server to confirm P11's "p95 under 500 ms under sustained concurrency" holds.

Usage:
  uv run python scripts/loadtest.py                        # localhost, defaults
  uv run python scripts/loadtest.py --base-url https://preview.example.com --concurrency 50
Exits non-zero if either endpoint's p95 exceeds the threshold, so it can gate a manual run.
"""

from __future__ import annotations

import argparse
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError

ENDPOINTS = {
    "search-suggest": "/api/v1/search/suggest/?q=tee",
    "shop-list": "/shop/",
}


def _one_request(url: str) -> tuple[float, bool]:
    """Return (elapsed_ms, ok). A non-2xx or a transport error counts as not ok."""
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - operator-supplied URL
            response.read()
            ok = 200 <= response.status < 300
    except HTTPError as exc:
        ok = 200 <= exc.code < 300
    except (URLError, TimeoutError):
        ok = False
    return (time.perf_counter() - start) * 1000, ok


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered)) - 1))
    return ordered[k]


def _run(name: str, url: str, total: int, concurrency: int, threshold_ms: float) -> bool:
    latencies: list[float] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for elapsed, ok in pool.map(lambda _: _one_request(url), range(total)):
            latencies.append(elapsed)
            failures += not ok

    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    passed = p95 <= threshold_ms and failures == 0
    mark = "ok" if passed else "FAIL"
    print(
        f"[{mark}] {name:<16} n={total} c={concurrency} "
        f"p50={p50:6.1f}ms p95={p95:6.1f}ms p99={p99:6.1f}ms "
        f"mean={statistics.mean(latencies):6.1f}ms failures={failures}"
    )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=400, help="requests per endpoint")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--threshold-ms", type=float, default=500.0)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    results = [
        _run(name, base + path, args.requests, args.concurrency, args.threshold_ms)
        for name, path in ENDPOINTS.items()
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
