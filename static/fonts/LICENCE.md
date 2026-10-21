# Fonts

Two self-hosted faces, both under the SIL Open Font License 1.1, whose full text is
`OFL.txt` in this directory. Nothing is fetched from a third-party font host at runtime
(decision P2).

| File | Family | Axis | Upstream | Version |
|---|---|---|---|---|
| `playfair-display-latin.woff2` | Playfair Display | `wght` 400 to 900 | `google/fonts`, `ofl/playfairdisplay` | 1.203 |
| `source-sans-3-latin.woff2` | Source Sans 3 | `wght` 200 to 900 | `google/fonts`, `ofl/sourcesans3` | 3.052 |

## Copyright notices

Copyright 2017 The Playfair Display Project Authors
(https://github.com/clauseggers/Playfair-Display), with Reserved Font Name
"Playfair Display".

Copyright 2010-2020 Adobe (http://www.adobe.com/), with Reserved Font Name 'Source'.
All Rights Reserved. Source is a trademark of Adobe in the United States and/or other
countries.

## How the subsets were built

Each file is the upstream variable TTF, subset to Latin plus the rupee sign, arrows and
typographic punctuation, then compressed to woff2. U+20B9 is listed explicitly because
Google's own `latin` slice leaves it out and every price on this site needs it.

```
uvx --from "fonttools[woff]" pyftsubset "PlayfairDisplay[wght].ttf" \
  --unicodes="U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20B9,U+2122,U+2190-2193,U+2212,U+2215,U+FEFF,U+FFFD" \
  --layout-features+=tnum --flavor=woff2 \
  --output-file=static/fonts/playfair-display-latin.woff2
```

The same command produces `source-sans-3-latin.woff2` from `SourceSans3[wght].ttf`.
