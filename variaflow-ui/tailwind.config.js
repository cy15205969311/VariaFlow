/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        varia: {
          bg: "#f4f5f7",
          panel: "#ffffff",
          line: "#e5e7eb",
          text: "#18181b",
          mute: "#71717a",
          soft: "#f9fafb",
        },
      },
      boxShadow: {
        "varia-sm": "0 1px 3px rgba(0, 0, 0, 0.05)",
        "varia-card": "0 2px 8px -4px rgba(0, 0, 0, 0.05)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "PingFang SC",
          "HarmonyOS Sans SC",
          "Microsoft YaHei UI",
          "Segoe UI",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
