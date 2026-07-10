import Link from "next/link";

/** Server-rendered pager. Builds hrefs by cloning the current query and swapping
 * the page param, so filters/sort carry across pages. */
export function Pagination({
  page,
  pageSize,
  count,
  searchParams,
  basePath = "/shop",
}: {
  page: number;
  pageSize: number;
  count: number;
  searchParams: Record<string, string | undefined>;
  basePath?: string;
}) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  if (totalPages <= 1) return null;

  const hrefFor = (p: number) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(searchParams)) {
      if (v && k !== "page") params.set(k, v);
    }
    if (p > 1) params.set("page", String(p));
    const qs = params.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  };

  const pages = Array.from({ length: totalPages }, (_, i) => i + 1).filter(
    (p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1,
  );

  return (
    <nav className="mt-12 flex items-center justify-center gap-2" aria-label="Pagination">
      {page > 1 && (
        <PageLink href={hrefFor(page - 1)} label="Prev" />
      )}
      {pages.map((p, idx) => {
        const prev = pages[idx - 1];
        const gap = prev && p - prev > 1;
        return (
          <span key={p} className="flex items-center gap-2">
            {gap && <span className="text-ink/40">…</span>}
            <Link
              href={hrefFor(p)}
              aria-current={p === page ? "page" : undefined}
              className={`flex h-9 min-w-9 items-center justify-center rounded-sm px-3 text-sm transition ${
                p === page
                  ? "bg-charcoal text-cream"
                  : "border border-black/15 text-ink hover:border-charcoal"
              }`}
            >
              {p}
            </Link>
          </span>
        );
      })}
      {page < totalPages && <PageLink href={hrefFor(page + 1)} label="Next" />}
    </nav>
  );
}

function PageLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="flex h-9 items-center rounded-sm border border-black/15 px-3 text-sm text-ink transition hover:border-charcoal"
    >
      {label}
    </Link>
  );
}
