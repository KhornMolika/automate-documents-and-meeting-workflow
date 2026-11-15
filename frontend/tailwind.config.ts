import type { Config } from 'tailwindcss'

export default <Partial<Config>>{
  content: [
    './components/**/*.{vue,js,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './composables/**/*.{js,ts}',
    './plugins/**/*.{js,ts}',
    './app.vue',
  ],
  theme: {
    extend: {
      colors: {
        // 60% Dominant (Canvas & Surfaces)
        ivory: {
          50: '#FAF8F2',
          100: '#F7F2E0', // Base Ivory Mist
          200: '#EDE7D1',
          300: '#DFD7BC',
          400: '#CFC3A0',
        },
        // 30% Secondary (Structure, Typography & Sidebar)
        bordeaux: {
          100: '#F8E7EA',
          200: '#ECC3C9',
          500: '#9E2E44',
          700: '#7D162B',
          800: '#690B1E',
          900: '#5B0015', // Base Night Bordeaux
          950: '#35000C',
        },
        // 10% Accent (Interactive Focal Points & Live Badges)
        horizon: {
          100: '#EAF2FC',
          200: '#D5E5F9',
          300: '#B6D3F4',
          400: '#9CBDED',
          500: '#80AEE8', // Base Cool Horizon
          600: '#5D94D8',
          700: '#3A78C5',
          800: '#2A5D9E',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
