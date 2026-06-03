/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui'],
        display: ['"Bricolage Grotesque"', 'ui-sans-serif', 'system-ui'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular'],
      },
      colors: {
        ink: '#0B0C10',
        carbon: '#111827',
        slate: '#1B2432',
        steel: '#2A3344',
        saffron: '#F7B32B',
        mint: '#5DE4C7',
        ember: '#FF5C5C',
        cobalt: '#3B82F6',
        lilac: '#B392F0',
        paper: '#E9EEF7',
        mist: '#94A3B8',
      },
      boxShadow: {
        'glow-saffron': '0 0 20px rgba(247, 179, 43, 0.35)',
        'glow-mint': '0 0 20px rgba(93, 228, 199, 0.35)',
        'glow-ember': '0 0 20px rgba(255, 92, 92, 0.35)',
        'glow-cobalt': '0 0 20px rgba(59, 130, 246, 0.35)',
      }
    },
  },
  plugins: [],
}
