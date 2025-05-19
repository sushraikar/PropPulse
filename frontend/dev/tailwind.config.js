/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#e6edff',
          100: '#ccdaff',
          200: '#99b6ff',
          300: '#6691ff',
          400: '#336dff',
          500: '#1F4AFF', // Brand color
          600: '#193bcc',
          700: '#132c99',
          800: '#0c1e66',
          900: '#060f33',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
