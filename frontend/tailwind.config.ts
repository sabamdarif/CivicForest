import type { Config } from "tailwindcss";

/**
 * CivicForest design tokens, lifted from the mockups in `designs/`:
 * deep charcoal surfaces, warm gold accent, cream light sections, serif display
 * headings over a clean sans body.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        charcoal: {
          DEFAULT: "#0E0E0D",
          800: "#161513",
          700: "#1F1C18",
          600: "#2A2621",
        },
        gold: {
          DEFAULT: "#C89B4A",
          light: "#DDB973",
          dark: "#A87E33",
        },
        cream: {
          DEFAULT: "#F4F1EA",
          dark: "#EAE5DA",
        },
        ink: "#1A1713",
      },
      fontFamily: {
        // Wired to next/font in app/layout.tsx via CSS variables.
        serif: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      letterSpacing: {
        brand: "0.18em",
      },
      maxWidth: {
        content: "1280px",
      },
      boxShadow: {
        card: "0 8px 30px rgba(0,0,0,0.08)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
