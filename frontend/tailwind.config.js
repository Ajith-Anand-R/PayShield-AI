/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Fira Sans"', '"Geist"', 'ui-sans-serif', 'system-ui'],
        display: ['"Fira Sans"', '"Geist"', 'ui-sans-serif', 'system-ui'],
        mono: ['"Fira Code"', '"Geist Mono"', 'ui-monospace', 'SFMono-Regular'],
      },
      colors: {
        ink: '#0f172a',      // Slate-900 (Lighter, premium background)
        carbon: '#1e293b',   // Slate-800 (Refined card base)
        slate: '#334155',    // Slate-700
        steel: '#475569',    // Slate-600
        primary: '#10b981', // Emerald Primary Accent
        saffron: '#fb923c', // Orange/Amber for warning/review
        mint: '#10b981', // Emerald for success/allow
        ember: '#f43f5e', // Rose for danger/block
        cobalt: '#3b82f6', // Blue for info/total
        lilac: '#a78bfa',
        paper: '#f8fafc',    // Slate-50 (Lighter, cleaner text)
        mist: '#cbd5e1',     // Slate-300 (Lighter description text)
      },
      boxShadow: {
        'glow-primary': '0 0 20px rgba(16, 185, 129, 0.25)',
        'glow-saffron': '0 0 20px rgba(251, 146, 60, 0.25)',
        'glow-mint': '0 0 20px rgba(16, 185, 129, 0.25)',
        'glow-ember': '0 0 20px rgba(244, 63, 94, 0.25)',
        'glow-cobalt': '0 0 20px rgba(59, 130, 246, 0.25)',
      }
    },
  },
  plugins: [],
}
