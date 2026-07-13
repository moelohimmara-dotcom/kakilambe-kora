'use client'

import { useCallback, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArchiveRestore } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { useAsync, useMutation } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { cycleApi, articleApi } from '@/lib/api'
import { archiveApi } from '@/lib/archiveApi'
import { formatDate, formatTime, formatRelative } from '@/lib/utils'
import type { Cycle, Article } from '@/lib/types'

const STATUS_BADGE: Record<string, { label: string; variant: 'orange' | 'sage' | 'danger' | 'warning' | 'gray' }> = {
  RUNNING:   { label: 'En cours', variant: 'orange' },
  PAUSED:    { label: 'En pause', variant: 'warning' },
  COMPLETED: { label: 'Terminé', variant: 'sage' },
  FAILED:    { label: 'Échoué', variant: 'danger' },
}

type View = 'cycles' | 'archive'

export function HistoryScreen() {
  const [view, setView] = useState<View>('cycles')

  const fetchCycles = useCallback(() => cycleApi.list(), [])
  const { data, loading } = useAsync(fetchCycles)
  const cycles: Cycle[] = (data as { items: Cycle[] } | null)?.items ?? []

  // KPI agregés
  const totalPublished = cycles.reduce((s, c) => s + (c.articles_published ?? 0), 0)
  const totalFailed    = cycles.filter(c => c.status === 'FAILED').length
  const successRate    = cycles.length > 0
    ? Math.round((cycles.filter(c => c.status === 'COMPLETED').length / cycles.length) * 100)
    : 0

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-heading font-bold text-2xl text-anthracite">Historique</h1>
        <p className="font-heading text-[13px] text-gray-dk mt-0.5">
          {loading ? '…' : `${cycles.length} cycle${cycles.length !== 1 ? 's' : ''} au total`}
        </p>
      </div>

      {/* Onglets Cycles / Archive */}
      <div className="flex gap-1 mb-6 bg-gray-pale rounded-lg p-1 w-fit" role="tablist" aria-label="Vue de l'historique">
        {([
          { key: 'cycles' as const, label: 'Cycles' },
          { key: 'archive' as const, label: 'Archive' },
        ]).map(tab => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={view === tab.key}
            onClick={() => setView(tab.key)}
            className={
              `px-4 min-h-[44px] rounded-md font-heading text-[12px] font-semibold transition-all ` +
              `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
              `${view === tab.key ? 'bg-white text-anthracite shadow-sm' : 'text-gray-dk hover:text-anthracite'}`
            }
          >
            {tab.label}
          </button>
        ))}
      </div>

      {view === 'cycles' ? (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <Card className="text-center">
              <div className="font-heading font-bold text-3xl text-orange">{totalPublished}</div>
              <p className="font-heading text-[11px] text-gray-dk mt-1">Articles publiés</p>
            </Card>
            <Card className="text-center">
              <div className="font-heading font-bold text-3xl text-sage">{successRate}%</div>
              <p className="font-heading text-[11px] text-gray-dk mt-1">Taux de succès</p>
            </Card>
            <Card className="text-center">
              <div className="font-heading font-bold text-3xl text-danger">{totalFailed}</div>
              <p className="font-heading text-[11px] text-gray-dk mt-1">Cycles échoués</p>
            </Card>
          </div>

          {/* Tableau */}
          {loading ? (
            <div className="flex justify-center py-16"><Spinner size="lg" /></div>
          ) : cycles.length === 0 ? (
            <div className="empty-state">
              <p className="font-heading font-semibold text-[15px] text-anthracite">Aucun cycle</p>
              <p className="font-heading text-[13px] text-gray-dk">Les cycles KORA apparaîtront ici.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {cycles.map(cycle => (
                <CycleRow key={cycle.id} cycle={cycle} />
              ))}
            </div>
          )}
        </>
      ) : (
        <ArchiveSection />
      )}
    </div>
  )
}

// ── Section Archive ───────────────────────────────────────────────────────────
// Les articles archivés depuis /articles ou /articles/{id} (lib/archiveApi.ts)
// sont gardés "pour plus tard" ici plutôt que dans le flux actif de travail —
// désarchiver renvoie directement à l'article pour édition. Le backend n'a
// pas de colonne ARCHIVED ni d'endpoint de recherche par id : la liste est
// reconstruite en filtrant côté client la page 1 de tous les articles (même
// limite déjà documentée ailleurs pour la pagination).

function ArchiveSection() {
  const router = useRouter()
  const { show } = useToast()

  const fetchAll = useCallback(() => articleApi.list(undefined), [])
  const { data, loading, refetch } = useAsync(fetchAll)
  const archivedIds = archiveApi.archivedIds()
  const rawArticles = (data as { items: Article[] } | null)?.items ?? []
  const archived = rawArticles.filter(a => archivedIds.has(a.id))

  const { mutate: unarchive } = useMutation(async (article: Article) => {
    await archiveApi.unarchiveArticle(article.id)
    show('Article désarchivé', 'success')
    router.push(`/articles/${article.id}`)
  })

  if (loading) {
    return <div className="flex justify-center py-16"><Spinner size="lg" /></div>
  }

  if (archived.length === 0) {
    return (
      <div className="empty-state">
        <div className="w-16 h-16 rounded-xl bg-gray-pale flex items-center justify-center">
          <span className="font-heading text-2xl text-gray-med">🗂</span>
        </div>
        <p className="font-heading font-semibold text-[15px] text-anthracite">Aucun article archivé</p>
        <p className="font-heading text-[13px] text-gray-dk max-w-xs">
          Les articles gardés "pour plus tard" depuis /articles apparaîtront ici.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {archived.map(article => (
        <Card key={article.id} className="flex items-center gap-4">
          {article.image_url ? (
            <img src={article.image_url} alt="" className="w-14 h-14 rounded-md object-cover shrink-0 bg-gray-pale" />
          ) : (
            <div className="w-14 h-14 rounded-md bg-orange/10 flex items-center justify-center shrink-0">
              <span className="text-orange font-heading font-bold text-lg">/</span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="font-heading font-semibold text-[13px] text-anthracite truncate">{article.titre}</p>
            <p className="font-heading text-[11px] text-gray-dk mt-0.5 truncate">
              {article.source_nom ?? '—'} · {formatRelative(article.created_at)}
            </p>
          </div>
          <button
            onClick={() => unarchive(article)}
            title="Désarchiver et éditer"
            aria-label={`Désarchiver et éditer : ${article.titre}`}
            className="w-11 h-11 shrink-0 rounded-full flex items-center justify-center bg-gray-pale text-gray-med hover:bg-gray-light hover:text-anthracite transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
          >
            <ArchiveRestore size={18} aria-hidden="true" />
          </button>
        </Card>
      ))}
    </div>
  )
}

function CycleRow({ cycle }: { cycle: Cycle }) {
  const st = STATUS_BADGE[cycle.status] ?? { label: cycle.status, variant: 'gray' as const }

  const duration = cycle.completed_at && cycle.started_at
    ? Math.round((new Date(cycle.completed_at).getTime() - new Date(cycle.started_at).getTime()) / 60000)
    : null

  return (
    <Card className="flex items-center gap-4">
      {/* Mode */}
      <div className="w-12 h-12 rounded-xl bg-orange/10 flex items-center justify-center shrink-0">
        <span className="font-heading text-[11px] font-bold text-orange uppercase">
          {cycle.mode === 'auto' ? 'Auto' : 'Semi'}
        </span>
      </div>

      {/* Info principale */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="font-mono text-[11px] text-gray-med">{cycle.id.slice(0, 8)}</span>
          <Badge variant={st.variant} dot={cycle.status === 'RUNNING'} pulse={cycle.status === 'RUNNING'}>
            {st.label}
          </Badge>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-gray-dk font-heading flex-wrap">
          <span>{formatDate(cycle.started_at)} à {formatTime(cycle.started_at)}</span>
          {duration !== null && <span>Durée : {duration} min</span>}
        </div>
      </div>

      {/* Stats */}
      <div className="hidden sm:flex items-center gap-6">
        <Stat label="Collectés" value={cycle.articles_collected ?? 0} color="text-blue-txt" />
        <Stat label="Sélectionnés" value={cycle.articles_selected ?? 0} color="text-orange" />
        <Stat label="Publiés" value={cycle.articles_published ?? 0} color="text-sage" />
        <Stat label="Rejetés" value={cycle.articles_rejected ?? 0} color="text-gray-med" />
      </div>
    </Card>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="text-center">
      <div className={`font-heading font-bold text-lg ${color}`}>{value}</div>
      <div className="font-heading text-[10px] text-gray-med">{label}</div>
    </div>
  )
}
