import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        ink: {
          950: "#070b12",
          900: "#0b1119",
          850: "#0f1620",
          800: "#141d2b",
          700: "#1e293b",
          600: "#334155",
        },
        aq: {
          good: "#4ade80",
          moderate: "#facc15",
          poor: "#fb923c",
          bad: "#f87171",
          severe: "#c084fc",
        },
        brand: {
          DEFAULT: "#38bdf8",
          soft: "#7dd3fc",
          deep: "#0ea5e9",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(56,189,248,0.15), 0 20px 60px -20px rgba(56,189,248,0.25)",
        card: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 40px -24px rgba(0,0,0,0.7)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseDot: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s ease-out both",
        "pulse-dot": "pulseDot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
