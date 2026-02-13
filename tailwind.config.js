/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./generate_tw_focus.py"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'mi-orange': '#ff6900',
        'mi-black': '#191919',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(-5px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', maxHeight: '0' },
          '100%': { opacity: '1', maxHeight: '600px' },
        },
        appear: {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-down': 'slideDown 0.3s ease-out forwards',
        'appear': 'appear 0.3s ease-out forwards',
      }
    },
  },
  plugins: [],
}
