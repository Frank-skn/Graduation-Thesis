/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        primary: {
          50: '#f0f4f8',
          100: '#d9e6f2',
          200: '#b3cde5',
          300: '#7ba7d4',
          400: '#4a7fa7',
          500: '#1a3a52',
          600: '#152e41',
          700: '#102331',
          800: '#0a1720',
          900: '#050b10',
        },
        accent: {
          50: '#faf8f5',
          100: '#f5eee3',
          200: '#ecddc7',
          300: '#dfc39e',
          400: '#d2ad82',
          500: '#c5a572',
          600: '#a88856',
          700: '#866843',
          800: '#644e32',
          900: '#423421',
        },
      },
    },
  },
  plugins: [],
}
