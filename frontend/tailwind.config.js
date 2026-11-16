/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        gray: {
          50: "#f8faf6", 100: "#edf1eb", 200: "#dce4dc", 300: "#c5d0c7",
          400: "#aab8ad", 500: "#899b8e", 600: "#75877a", 700: "#354239",
          800: "#232d27", 900: "#151d18", 950: "#0c110e",
        },
        indigo: {
          300: "#ddf9b1", 400: "#c9f77d", 500: "#aadd67", 600: "#779e43",
          700: "#425b2c", 800: "#304426", 900: "#1e2e1b",
        },
      },
    },
  },
  plugins: [],
};
