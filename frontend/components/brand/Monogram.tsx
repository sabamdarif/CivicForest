/**
 * The CivicForest "cF" leaf monogram, approximated in SVG so it scales cleanly and
 * inherits `currentColor`. Swap for the final brand asset when available — the API
 * shape (className + title) stays the same.
 */
export function Monogram({
  className = "h-10 w-10",
  title = "CivicForest",
}: {
  className?: string;
  title?: string;
}) {
  return (
    <svg
      viewBox="0 0 100 100"
      role="img"
      aria-label={title}
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* cursive c */}
      <path
        d="M56 30c-8-6-22-5-29 4-8 10-6 27 4 34 7 5 17 5 24 1"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      {/* stem + arms of the F */}
      <path
        d="M55 20v58"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      <path
        d="M55 30h22M55 50h16"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      {/* leaf sprouting from the crossbar */}
      <path
        d="M71 33c6-2 12 0 15 5-6 3-12 2-16-2z"
        fill="currentColor"
      />
      <path
        d="M71 33c4 2 6 5 7 9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
