// Design tokens TypeScript — source unique de vérité pour tous les composants
// Référence : KORA V3 Section 4

export const colors = {
  cream:       '#faf9f5',
  white:       '#ffffff',
  anthracite:  '#141413',
  grayLight:   '#e8e6dc',
  grayPale:    '#f3f2ee',
  grayMed:     '#b0aea5',
  grayDk:      '#6b6963',
  orange:      '#d97757',
  orangeDk:    '#c46844',
  orangeLt:    'rgba(217,119,87,0.10)',
  blue:        '#6a9bcc',
  blueTxt:     '#3d6e99',
  blueLt:      'rgba(106,155,204,0.12)',
  sage:        '#788c5d',
  sageLt:      'rgba(120,140,93,0.12)',
  danger:      '#c0392b',
  dangerLt:    'rgba(192,57,43,0.10)',
  warning:     '#e67e22',
} as const

export const fonts = {
  heading: "'Poppins', Arial, sans-serif",
  body:    "'Lora', Georgia, serif",
  mono:    "'JetBrains Mono', monospace",
} as const

export const radii = {
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
} as const

export const shadows = {
  card:    '0 1px 3px rgba(20,20,19,.06), 0 4px 12px rgba(20,20,19,.04)',
  cardMd:  '0 4px 16px rgba(20,20,19,.08), 0 1px 4px rgba(20,20,19,.04)',
  lg:      '0 8px 32px rgba(20,20,19,.14)',
} as const

export type ColorKey  = keyof typeof colors
export type FontKey   = keyof typeof fonts
export type ShadowKey = keyof typeof shadows
