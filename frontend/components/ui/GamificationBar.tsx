'use client'

import { useCallback } from 'react'
import { useAsync } from '@/lib/hooks'
import { articleApi } from '@/lib/api'
import { settingsApi } from '@/lib/api'
import { gamificationApi } from '@/lib/gamificationApi'
import { StreakIndicator } from './StreakIndicator'
import { ProgressRing } from './ProgressRing'

// Barre de gamification (nouveau périmètre produit) — discrète, ne modifie
// aucune logique existante du Dashboard. Auto-suffisante : ses propres
// appels réseau, indépendants de fetchDashboard() (volontairement non
// touché, cf. historique de bugs documenté sur cet écran).

// app_settings renvoie tout en TEXT côté backend (voir SettingsScreen.tsx) —
// coercion minimale dupliquée ici pour éviter de coupler ce composant à un
// écran non lié.
function asNumber(v: unknown, fallback: number): number {
  const n = Number(v)
  return Number.isFinite(n) && v !== undefined && v !== null && v !== '' ? n : fallback
}

export function GamificationBar() {
  const fetchStreak = useCallback(() => gamificationApi.getStreak(), [])
  const { data: streak } = useAsync(fetchStreak)

  const fetchQuota = useCallback(async () => {
    const [settingsRes, publishedRes] = await Promise.allSettled([
      settingsApi.get(),
      articleApi.list('PUBLISHED', 1),
    ])
    const limit = settingsRes.status === 'fulfilled'
      ? asNumber((settingsRes.value as Record<string, unknown>).daily_article_limit, 3)
      : 3
    const publishedToday = publishedRes.status === 'fulfilled'
      ? (publishedRes.value as { items: { published_at?: string }[] }).items.filter(
          a => a.published_at && new Date(a.published_at).toDateString() === new Date().toDateString()
        ).length
      : 0
    return { limit, publishedToday }
  }, [])
  const { data: quota } = useAsync(fetchQuota)

  if (!streak && !quota) return null

  return (
    <div className="flex items-center gap-3">
      {streak && <StreakIndicator days={streak.days} />}
      {quota && (
        <ProgressRing
          value={quota.publishedToday}
          max={quota.limit}
          label={`${quota.publishedToday} article(s) publié(s) aujourd'hui sur ${quota.limit}`}
        />
      )}
    </div>
  )
}
