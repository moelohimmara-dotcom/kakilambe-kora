// Composant de gamification (nouveau périmètre produit) — traitement visuel
// discret (accent lavande réservé à la gamification, jamais réutilisé
// ailleurs), jamais affiché sur /corbeille.

export function ProgressRing({
  value, max, size = 44, label,
}: {
  value: number
  max: number
  size?: number
  label: string
}) {
  const pct = max > 0 ? Math.min(1, value / max) : 0
  const strokeWidth = 4
  const r = (size - strokeWidth * 2) / 2
  const c = 2 * Math.PI * r
  const offset = c * (1 - pct)

  return (
    <div
      className="relative inline-flex items-center justify-center shrink-0"
      style={{ width: size, height: size }}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
      title={label}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={strokeWidth} fill="none" className="stroke-gray-pale" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          className="stroke-lavender transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <span className="absolute font-heading text-[10px] font-bold text-anthracite">
        {value}/{max}
      </span>
    </div>
  )
}
