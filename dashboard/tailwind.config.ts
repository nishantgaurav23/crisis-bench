import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        crisis: {
          red: "#dc2626",
          orange: "#ea580c",
          yellow: "#ca8a04",
          green: "#16a34a",
          blue: "#2563eb",
        },
      },
    },
  },
  plugins: [],
};

export default config;
