import type { ArticleStatus, BadgeVariant } from './types'

export function formatDate(iso: string, opts?: Intl.DateTimeFormatOptions): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'short', year: 'numeric', ...opts,
  })
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return "À l'instant"
  if (m < 60) return `Il y a ${m} min`
  const h = Math.floor(m / 60)
  if (h < 24) return `Il y a ${h}h`
  return formatDate(iso)
}

export function statusLabel(status: ArticleStatus): string {
  const labels: Record<ArticleStatus, string> = {
    DRAFT: 'Brouillon',
    PENDING_REVIEW: 'En attente',
    PUBLISHED: 'Publié',
    REJECTED: 'Rejeté',
    FAILED: 'Échoué',
  }
  return labels[status] ?? status
}

export function statusVariant(status: ArticleStatus): BadgeVariant {
  const map: Record<ArticleStatus, BadgeVariant> = {
    DRAFT: 'gray',
    PENDING_REVIEW: 'orange',
    PUBLISHED: 'sage',
    REJECTED: 'gray',
    FAILED: 'danger',
  }
  return map[status] ?? 'gray'
}

export function truncate(text: string, max: number): string {
  return text.length <= max ? text : text.slice(0, max) + '…'
}

export function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

// Fix Next.js import — BadgeVariant re-export
export type { BadgeVariant } from './types'
