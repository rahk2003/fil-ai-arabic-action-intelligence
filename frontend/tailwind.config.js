/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["IBM Plex Sans Arabic", "Noto Sans Arabic", "system-ui", "sans-serif"] },
      colors: {
        ink: "#07111f",
        electric: "#5de4c7",
        iris: "#7767e8"
      },
      boxShadow: { panel: "0 18px 60px -28px rgba(15, 23, 42, .38)" }
    },
  },
  plugins: [],
};
