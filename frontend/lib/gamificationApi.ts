// Couche stub — Gamification (nouveau périmètre produit, validé
// explicitement). Aucune table de suivi de streak/achievements n'existe
// côté backend ; plutôt que d'inventer des chiffres arbitraires, ce stub
// calcule une approximation honnête à partir de données réelles déjà
// exposées (articles PUBLISHED) et TODO backend documente les vrais
// endpoints à créer.
//
// TODO backend : GET /api/gamification/streak (calcul serveur, plus fiable
// qu'une reconstruction client limitée à la page 1 des articles publiés),
// GET/POST /api/gamification/achievements (persistance des jalons vus,
// aujourd'hui simulée en localStorage donc perdue si l'utilisateur change
// de navigateur/appareil).

import { articleApi } from './api'

export interface StreakInfo { days: number }
export interface Milestone { id: string; label: string; threshold: number }

const MILESTONES: Milestone[] = [
  { id: 'first_article', label: 'Premier article publié 🎉', threshold: 1 },
  { id: 'ten_articles', label: '10 articles publiés — cap franchi !', threshold: 10 },
  { id: 'fifty_articles', label: '50 articles publiés — belle régularité !', threshold: 50 },
]

const SEEN_KEY = 'kora_achievements_seen'

function readSeen(): Set<string> {
  if (typeof window === 'undefined') return new Set()
  try {
    const raw = localStorage.getItem(SEEN_KEY)
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set()
  } catch {
    return new Set()
  }
}

function writeSeen(seen: Set<string>) {
  if (typeof window === 'undefined') return
  localStorage.setItem(SEEN_KEY, JSON.stringify([...seen]))
}

export const gamificationApi = {
  // Approximation du nombre de jours consécutifs avec au moins un article
  // publié, calculée à partir des articles PUBLISHED réels les plus
  // récents (page 1 uniquement — limitation identique à celle déjà
  // documentée sur /history, voir CDC §8.2).
  async getStreak(): Promise<StreakInfo> {
    const res = (await articleApi.list('PUBLISHED', 1)) as { items: { published_at?: string }[] }
    const dates = new Set(
      res.items.filter(a => a.published_at).map(a => new Date(a.published_at as string).toDateString())
    )
    let days = 0
    const cursor = new Date()
    while (dates.has(cursor.toDateString())) {
      days += 1
      cursor.setDate(cursor.getDate() - 1)
    }
    return { days }
  },

  // Retourne le jalon le plus élevé nouvellement franchi (au plus un par
  // appel, pour ne jamais afficher une rafale de toasts) à partir du total
  // réel d'articles publiés (res.total, pas seulement la page chargée).
  async checkNewMilestone(): Promise<Milestone | null> {
    const res = (await articleApi.list('PUBLISHED', 1)) as { total: number }
    const seen = readSeen()
    const reached = MILESTONES.filter(m => res.total >= m.threshold && !seen.has(m.id))
    if (reached.length === 0) return null
    const milestone = reached[reached.length - 1]
    seen.add(milestone.id)
    writeSeen(seen)
    return milestone
  },
}
