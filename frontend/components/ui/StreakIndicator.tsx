// Composant de gamification (nouveau périmètre produit) — traitement visuel
// discret (bordure pointillée, ton pastel lavande). Accent réservé aux
// composants de gamification, jamais réutilisé ailleurs dans l'IHM
// éditoriale, et jamais affiché sur /corbeille.

export function StreakIndicator({ days }: { days: number }) {
  if (days <= 0) return null

  return (
    <div
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-dashed border-lavender bg-lavender-pale"
      title={`${days} jour${days > 1 ? 's' : ''} consécutif${days > 1 ? 's' : ''} avec au moins un article publié`}
    >
      <span aria-hidden="true">🔥</span>
      <span className="font-heading text-[12px] font-semibold text-anthracite">
        {days} jour{days > 1 ? 's' : ''} de suite
      </span>
    </div>
  )
}
