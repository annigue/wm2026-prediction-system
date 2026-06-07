/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        wm: {
          dark: "#0a0e1a",
          card: "#131a2e",
          border: "#243049",
          muted: "#8b95a9",
          gold: "#f5c518",
        },
      },
    },
  },
  plugins: [],
};
