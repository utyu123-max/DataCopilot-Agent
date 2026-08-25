/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: '#1a1b23', light: '#22232d', lighter: '#2a2b37' },
        accent: { DEFAULT: '#6366f1', light: '#818cf8' },
        border: { DEFAULT: '#2d2e3a' }
      }
    }
  },
  plugins: []
}
