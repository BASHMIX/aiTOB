/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        appDark: '#12161E',
        cardDark: '#1A202C',
        accentYellow: '#E2B714',
        textLight: '#E2E8F0',
        textDim: '#94A3B8',
        btnActive: '#2C3A4F',
        statusGreen: '#4ADE80',
        statusRed: '#EF4444',
        matchProgress: '#22C55E',
        matchCalled: '#EAB308',
        matchNotStarted: '#4F46E5',
        matchComplete: '#4B5563',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      }
    },
  },
  plugins: [],
}

