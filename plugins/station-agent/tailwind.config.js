/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        sf: {
          dark: '#0a0d14',
          card: '#111726',
          border: '#1f293d',
          accent: '#3b82f6',
          p1: '#00f0ff',
          p1Dark: '#0369a1',
          p2: '#ff3366',
          p2Dark: '#be123c',
          drive: '#10b981',
          super: '#f59e0b',
        }
      },
      animation: {
        'pulse-glow': 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'health-shake': 'shake 0.3s ease-in-out',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '1', filter: 'drop-shadow(0 0 12px rgba(59, 130, 246, 0.6))' },
          '50%': { opacity: '0.6', filter: 'drop-shadow(0 0 4px rgba(59, 130, 246, 0.2))' },
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '20%, 60%': { transform: 'translateX(-4px)' },
          '40%, 80%': { transform: 'translateX(4px)' },
        }
      }
    },
  },
  plugins: [],
}
