/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        cream:        '#faf9f5',
        anthracite:   '#141413',
        'gray-light': '#e8e6dc',
        'gray-pale':  '#f3f2ee',
        'gray-med':   '#b0aea5',
        'gray-dk':    '#6b6963',
        orange:       '#d97757',
        'orange-dk':  '#c46844',
        'blue-txt':   '#3d6e99',
        blue:         '#6a9bcc',
        sage:         '#788c5d',
        danger:       '#c0392b',
        warning:      '#e67e22',
        // Réservé aux composants de gamification (StreakIndicator,
        // AchievementToast, ProgressRing) — jamais réutilisé ailleurs dans
        // l'IHM éditoriale (le badge HITL de /agent reste "orange").
        lavender:       '#a996c9',
        'lavender-pale': '#f1ecf8',
      },
      fontFamily: {
        heading: ['Poppins', 'Arial', 'sans-serif'],
        body:    ['Lora', 'Georgia', 'serif'],
        mono:    ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
        xl: '24px',
      },
      boxShadow: {
        card:    '0 1px 3px rgba(20,20,19,.06), 0 4px 12px rgba(20,20,19,.04)',
        'card-hover': '0 4px 16px rgba(20,20,19,.08), 0 1px 4px rgba(20,20,19,.04)',
        lg:      '0 8px 32px rgba(20,20,19,.14)',
      },
    },
  },
  plugins: [],
}
