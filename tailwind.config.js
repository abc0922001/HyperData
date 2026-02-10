/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./generate_tw_focus.py"],
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
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
      }
    },
  },
  plugins: [],
}
