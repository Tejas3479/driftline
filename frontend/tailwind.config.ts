import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      /* ── Semantic Color Tokens ── */
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        // Surface depth layers
        surface: {
          0: "#030712",
          1: "#0f172a",
          2: "#1e293b",
          3: "#334155",
        },
        // Accent spectrum
        accent: {
          cyan: "#22d3ee",
          "cyan-dim": "#06b6d4",
          indigo: "#818cf8",
          "indigo-dim": "#6366f1",
          violet: "#a78bfa",
          "violet-dim": "#8b5cf6",
        },
        // Status semantics
        status: {
          warning: "#f59e0b",
          "warning-dim": "#d97706",
          danger: "#f43f5e",
          "danger-dim": "#e11d48",
          success: "#10b981",
          "success-dim": "#059669",
        },
      },

      /* ── Typography ── */
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },

      /* ── Animations ── */
      animation: {
        float: "float 6s ease-in-out infinite",
        "float-slow": "float 10s ease-in-out infinite",
        "float-delayed": "float 8s ease-in-out 2s infinite",
        shimmer: "shimmer 2s linear infinite",
        "glow-pulse": "glow-pulse 3s ease-in-out infinite",
        grain: "grain 0.5s steps(4) infinite",
        meteor: "meteor 3s linear infinite",
        "gradient-shift": "gradient-shift 20s ease infinite",
        "spin-slow": "spin 8s linear infinite",
        "fade-up": "fade-up 0.6s ease-out",
        "slide-up": "slide-up 0.5s cubic-bezier(0.16, 1, 0.3, 1)",
        "border-spin": "border-spin 4s linear infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-20px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "glow-pulse": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        grain: {
          "0%, 100%": { transform: "translate(0, 0)" },
          "25%": { transform: "translate(-2%, -2%)" },
          "50%": { transform: "translate(2%, 0)" },
          "75%": { transform: "translate(0, 2%)" },
        },
        meteor: {
          "0%": { transform: "rotate(215deg) translateX(0)", opacity: "1" },
          "70%": { opacity: "1" },
          "100%": { transform: "rotate(215deg) translateX(-600px)", opacity: "0" },
        },
        "gradient-shift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "25%": { backgroundPosition: "50% 0%" },
          "50%": { backgroundPosition: "100% 50%" },
          "75%": { backgroundPosition: "50% 100%" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(24px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "border-spin": {
          "0%": { "--border-angle": "0deg" },
          "100%": { "--border-angle": "360deg" },
        },
      },

      /* ── Backdrop Blur Levels ── */
      backdropBlur: {
        xs: "2px",
        sm: "4px",
        md: "12px",
        lg: "16px",
        xl: "24px",
        "2xl": "40px",
      },

      /* ── Glow Box Shadows ── */
      boxShadow: {
        "glow-cyan-sm": "0 0 15px -3px rgba(6, 182, 212, 0.2)",
        "glow-cyan": "0 0 25px -4px rgba(6, 182, 212, 0.25)",
        "glow-cyan-lg": "0 0 40px -4px rgba(6, 182, 212, 0.3)",
        "glow-indigo-sm": "0 0 15px -3px rgba(99, 102, 241, 0.2)",
        "glow-indigo": "0 0 25px -4px rgba(99, 102, 241, 0.25)",
        "glow-indigo-lg": "0 0 40px -4px rgba(99, 102, 241, 0.3)",
        "glow-violet-sm": "0 0 15px -3px rgba(139, 92, 246, 0.2)",
        "glow-violet": "0 0 25px -4px rgba(139, 92, 246, 0.25)",
        "glow-violet-lg": "0 0 40px -4px rgba(139, 92, 246, 0.3)",
        "glow-amber-sm": "0 0 15px -3px rgba(245, 158, 11, 0.2)",
        "glow-amber": "0 0 25px -4px rgba(245, 158, 11, 0.25)",
        "glow-rose-sm": "0 0 15px -3px rgba(244, 63, 94, 0.2)",
        "glow-rose": "0 0 25px -4px rgba(244, 63, 94, 0.25)",
      },

      /* ── Transition Timing ── */
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
export default config;
