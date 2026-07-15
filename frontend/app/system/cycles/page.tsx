'use client'

import { useEffect, useState, useCallback } from 'react'
import { cycleApi } from '@/lib/api'
import type { Cycle } from '@/lib/types'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'

const STATUS_COLOR: Record<string, string> = {
  IDLE:          '#5a5956',
  RUNNING:       '#3d6e99',
  PAUSED:        '#ecc94b',
  COMPLETED:     '#48bb78',
  FAILED:        '#fc8181',
  PARTIAL:       '#ecc94b',
}

function StatusDot({ status }: { status: string }) {
  const color = STATUS_COLOR[status] ?? '#5a5956'
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px]" style={{ color }}>
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />
      {status}
    </span>
  )
}

function fmt(dt: string | null): string {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function duration(start: string, end: string | null): string {
  if (!end) return '…'
  const s = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60), rem = s % 60
  return `${m}m ${rem}s`
}

export default function CyclesPage() {
  const [cycles, setCycles]  = useState<Cycle[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage]      = useState(0)
  // Root cause corrigée (audit 2026-07-15) : ces KPI étaient calculés
  // côté client à partir de `cycles` (page 1 seulement, cf. cycleApi.list()),
  // donc systématiquement faux dès qu'il existe plus de cycles que la
  // pagination — même piège déjà documenté dans cycle_routes.py:62-67 pour
  // /history. GET /api/cycles/stats agrège sur TOUTE la table `cycles`.
  const [stats, setStats] = useState({ total: 0, completed: 0, failed: 0, running: 0 })
  const PER_PAGE = 20

  const load = useCallback(async () => {
    try {
      const [data, statsData] = await Promise.all([cycleApi.list(), cycleApi.stats()])
      setCycles(Array.isArray(data) ? data : (data as { items: Cycle[] }).items ?? [])
      setStats({
        total: statsData.total_cycles,
        completed: statsData.total_completed,
        failed: statsData.total_failed,
        running: statsData.total_running,
      })
    } catch { /* stale */ }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const paginated = cycles.slice(page * PER_PAGE, (page + 1) * PER_PAGE)
  const totalPages = Math.ceil(cycles.length / PER_PAGE)

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-mono font-bold text-xl text-white">Cycles de rédaction</h1>
          <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>
            Historique complet des cycles KORA
          </p>
        </div>
        <button
          onClick={load}
          className="font-mono text-[11px] px-3 py-1.5 rounded border"
          style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
        >
          ↺ Actualiser
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Total',    value: stats.total,     color: SYS_TEXT },
          { label: 'Terminés', value: stats.completed, color: '#48bb78' },
          { label: 'Échoués',  value: stats.failed,    color: SYS_RED },
          { label: 'En cours', value: stats.running,   color: '#3d6e99' },
        ].map(k => (
          <div key={k.label} className="p-4 rounded-lg border" style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}>
            <div className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: SYS_MUTED }}>{k.label}</div>
            <div className="font-mono font-bold text-2xl" style={{ color: k.color }}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-xl border overflow-hidden" style={{ borderColor: SYS_BORDER }}>
        <table className="w-full">
          <thead>
            <tr style={{ background: SYS_SURFACE, borderBottom: `1px solid ${SYS_BORDER}` }}>
              {['ID', 'Statut', 'Démarré', 'Terminé', 'Durée', 'Articles sélec.', 'Publiés'].map(h => (
                <th key={h} className="text-left px-4 py-3 font-mono text-[10px] uppercase tracking-widest" style={{ color: SYS_MUTED }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center px-4 py-8 font-mono text-[12px]" style={{ color: SYS_MUTED }}>
                  Chargement…
                </td>
              </tr>
            ) : paginated.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center px-4 py-8 font-mono text-[12px]" style={{ color: SYS_MUTED }}>
                  Aucun cycle
                </td>
              </tr>
            ) : paginated.map((c, i) => (
              <tr
                key={c.id}
                style={{
                  background: i % 2 === 0 ? '#0c0c0b' : SYS_SURFACE,
                  borderBottom: `1px solid ${SYS_BORDER}`,
                }}
              >
                <td className="px-4 py-3 font-mono text-[11px]" style={{ color: SYS_MUTED }}>
                  {c.id.slice(0, 8)}…
                </td>
                <td className="px-4 py-3">
                  <StatusDot status={c.status} />
                </td>
                <td className="px-4 py-3 font-mono text-[11px]" style={{ color: SYS_TEXT }}>
                  {fmt(c.started_at ?? null)}
                </td>
                <td className="px-4 py-3 font-mono text-[11px]" style={{ color: SYS_TEXT }}>
                  {fmt(c.completed_at ?? null)}
                </td>
                <td className="px-4 py-3 font-mono text-[11px]" style={{ color: SYS_MUTED }}>
                  {c.started_at ? duration(c.started_at, c.completed_at ?? null) : '—'}
                </td>
                <td className="px-4 py-3 font-mono text-[11px] text-center" style={{ color: SYS_TEXT }}>
                  {c.articles_selected ?? '—'}
                </td>
                <td className="px-4 py-3 font-mono text-[11px] text-center" style={{ color: '#48bb78' }}>
                  {c.articles_published ?? 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="font-mono text-[11px]" style={{ color: SYS_MUTED }}>
            Page {page + 1} / {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="font-mono text-[11px] px-3 py-1.5 rounded border disabled:opacity-30"
              style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
            >
              ← Préc.
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page === totalPages - 1}
              className="font-mono text-[11px] px-3 py-1.5 rounded border disabled:opacity-30"
              style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
            >
              Suiv. →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
