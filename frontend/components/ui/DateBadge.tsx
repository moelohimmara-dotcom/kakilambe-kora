import { Calendar } from 'lucide-react'

interface DateBadgeProps {
  label: string
  confirmed: boolean
  className?: string
}

// Distinct DÉLIBÉRÉMENT du composant Badge (statut éditorial : "En attente",
// "Publié"...) — style outline + icône, jamais le même remplissage coloré,
// pour qu'aucune des deux informations ne soit confondue avec l'autre au
// premier coup d'œil (cf. contrainte explicite de la tâche). "Date non
// confirmée" (source sans métadonnée fiable, cf. migration 013 backend)
// est visuellement signalée (ton warning) plutôt que traitée comme une
// date normale, sans jamais afficher created_at à sa place.
export function DateBadge({ label, confirmed, className = '' }: DateBadgeProps) {
  return (
    <span
      className={
        `inline-flex items-center gap-1 px-2 py-0.5 rounded-full border font-heading text-[10px] font-medium ` +
        `${confirmed ? 'border-gray-light text-gray-dk' : 'border-warning/50 text-warning bg-warning/5'} ` +
        className
      }
    >
      <Calendar size={10} aria-hidden="true" />
      {label}
    </span>
  )
}
