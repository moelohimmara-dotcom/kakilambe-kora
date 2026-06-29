'use client'

import { useCallback } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { useAsync } from '@/lib/hooks'
import { cycleApi } from '@/lib/api'
import { formatDate, formatTime } from '@/lib/utils'
import type { Cycle } from '@/lib/types'

const STATUS_BADGE: Record<string, { label: string; variant: 'orange' | 'sage' | 'danger' | 'warning' | 'gray' }> = {
  RUNNING:   { label: 'En cours', variant: 'orange' },
  PAUSED:    { label: 'En pause', variant: 'warning' },
  COMPLETED: { label: 'Terminé', variant: 'sage' },
  FAILED:    { label: 'Échoué', variant: 'danger' },
}

export function HistoryScreen() {
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
      <div className="mb-8">
        <h1 className="font-heading font-bold text-2xl text-anthracite">Historique des cycles</h1>
        <p className="font-heading text-[13px] text-gray-dk mt-0.5">
          {loading ? '…' : `${cycles.length} cycle${cycles.length !== 1 ? 's' : ''} au total`}
        </p>
      </div>

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
