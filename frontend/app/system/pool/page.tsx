'use client'

import { useCallback, useState } from 'react'
import { useAsync, useMutation } from '@/lib/hooks'
import { poolApi } from '@/lib/api'
import type { PoolStatus } from '@/lib/api'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'
const SYS_GREEN   = '#48bb78'
const SYS_YELLOW  = '#ecc94b'

// Vraies données (GET /api/pool/status) — supervision du système de veille
// passive (migration 011, agent/pool.py) : état du pool par source,
// historique des jobs, réglages, et actions de contrôle (déclenchement
// manuel, modification des paramètres, reset complet) — sans jamais
// nécessiter d'accès direct à la base de données.
export default function PoolPage() {
  const fetchStatus = useCallback(() => poolApi.status(), [])
  const { data: status, loading, refetch } = useAsync<PoolStatus>(fetchStatus)

  const [intervalInput, setIntervalInput] = useState<string>('')
  const [thresholdInput, setThresholdInput] = useState<string>('')
  const [confirmReset, setConfirmReset] = useState(false)

  const { mutate: runNow, loading: running } = useMutation(async () => {
    await poolApi.runNow()
    await refetch()
  })

  const { mutate: saveSettings, loading: saving } = useMutation(async () => {
    const payload: { pool_interval_hours?: number; pool_dedup_threshold?: number } = {}
    if (intervalInput) payload.pool_interval_hours = Number(intervalInput)
    if (thresholdInput) payload.pool_dedup_threshold = Number(thresholdInput)
    await poolApi.updateSettings(payload)
    setIntervalInput('')
    setThresholdInput('')
    await refetch()
  })

  const { mutate: resetPool, loading: resetting } = useMutation(async () => {
    const result = await poolApi.reset()
    setConfirmReset(false)
    await refetch()
    return result
  })

  if (loading || !status) {
    return (
      <div className="font-mono text-[12px] py-8 text-center" style={{ color: SYS_MUTED }}>
        Chargement…
      </div>
    )
  }

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="font-mono font-bold text-xl text-white">Veille passive</h1>
        <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>
          Pool de contenu pré-collecté — supervision, réglages et reset, sans accès base directe
        </p>
      </div>

      {/* Totaux */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Disponibles', value: status.total_available, color: SYS_GREEN },
          { label: 'Utilisés', value: status.total_used, color: SYS_TEXT },
          { label: 'Expirés', value: status.total_expired, color: SYS_MUTED },
        ].map(t => (
          <div key={t.label} className="p-4 rounded-xl border" style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}>
            <div className="font-mono font-bold text-2xl" style={{ color: t.color }}>{t.value}</div>
            <div className="font-mono text-[11px] mt-1" style={{ color: SYS_MUTED }}>{t.label} (aujourd&apos;hui)</div>
          </div>
        ))}
      </div>

      {/* Par source */}
      <div>
        <h2 className="font-mono font-bold text-[13px] text-white mb-3">État par source</h2>
        <div className="space-y-2">
          {status.sources.length === 0 && (
            <p className="font-mono text-[12px]" style={{ color: SYS_MUTED }}>Aucune donnée pour aujourd&apos;hui.</p>
          )}
          {status.sources.map(s => (
            <div
              key={s.source_name}
              className="flex items-center justify-between gap-4 px-4 py-2.5 rounded-lg border"
              style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}
            >
              <span className="font-mono text-[12px] text-white truncate">{s.source_name}</span>
              <div className="flex gap-4 font-mono text-[11px] shrink-0">
                <span style={{ color: SYS_GREEN }}>{s.available} dispo.</span>
                <span style={{ color: SYS_TEXT }}>{s.used} utilisés</span>
                <span style={{ color: SYS_MUTED }}>{s.expired} expirés</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dernier job + déclenchement manuel */}
      <div className="p-5 rounded-xl border" style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-mono font-bold text-[13px] text-white">Dernier job de veille</h2>
          <button
            onClick={() => runNow(undefined as unknown as void)}
            disabled={running}
            className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors disabled:opacity-40"
            style={{ color: SYS_GREEN, borderColor: 'rgba(72,187,120,.3)', background: 'rgba(72,187,120,.08)' }}
          >
            {running ? 'Veille en cours…' : 'Déclencher maintenant'}
          </button>
        </div>
        {status.last_job ? (
          <div className="font-mono text-[11px] space-y-1" style={{ color: SYS_TEXT }}>
            <div>Déclencheur : <span style={{ color: SYS_MUTED }}>{status.last_job.trigger}</span></div>
            <div>Statut : <span style={{ color: status.last_job.status === 'completed' ? SYS_GREEN : status.last_job.status === 'failed' ? SYS_RED : SYS_YELLOW }}>{status.last_job.status}</span></div>
            <div>Sources balayées : {status.last_job.sources_scanned} · Éléments collectés : {status.last_job.items_collected} · Doublons liés : {status.last_job.duplicates_linked}</div>
            {status.last_job.error && <div style={{ color: SYS_RED }}>Erreur : {status.last_job.error}</div>}
          </div>
        ) : (
          <p className="font-mono text-[12px]" style={{ color: SYS_MUTED }}>Aucun job exécuté pour l&apos;instant.</p>
        )}
      </div>

      {/* Réglages */}
      <div className="p-5 rounded-xl border" style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}>
        <h2 className="font-mono font-bold text-[13px] text-white mb-3">Paramètres</h2>
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block font-mono text-[10px] mb-1" style={{ color: SYS_MUTED }}>
              Fréquence de veille (heures) — actuel : {status.settings.pool_interval_hours}
            </label>
            <input
              type="number" min={1}
              value={intervalInput}
              onChange={e => setIntervalInput(e.target.value)}
              placeholder={String(status.settings.pool_interval_hours)}
              className="font-mono text-[12px] px-3 py-1.5 rounded border w-24"
              style={{ background: '#1e1e1c', borderColor: SYS_BORDER, color: SYS_TEXT }}
            />
          </div>
          <div>
            <label className="block font-mono text-[10px] mb-1" style={{ color: SYS_MUTED }}>
              Seuil de déduplication (0-1) — actuel : {status.settings.pool_dedup_threshold}
            </label>
            <input
              type="number" min={0.01} max={1} step={0.05}
              value={thresholdInput}
              onChange={e => setThresholdInput(e.target.value)}
              placeholder={String(status.settings.pool_dedup_threshold)}
              className="font-mono text-[12px] px-3 py-1.5 rounded border w-24"
              style={{ background: '#1e1e1c', borderColor: SYS_BORDER, color: SYS_TEXT }}
            />
          </div>
          <button
            onClick={() => saveSettings(undefined as unknown as void)}
            disabled={saving || (!intervalInput && !thresholdInput)}
            className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors disabled:opacity-40"
            style={{ color: SYS_TEXT, borderColor: SYS_BORDER, background: '#1e1e1c' }}
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </div>

      {/* Reset complet */}
      <div className="p-5 rounded-xl border" style={{ background: SYS_SURFACE, borderColor: 'rgba(229,62,62,.3)' }}>
        <h2 className="font-mono font-bold text-[13px] mb-2" style={{ color: SYS_RED }}>Zone dangereuse</h2>
        <p className="font-mono text-[11px] mb-3" style={{ color: SYS_MUTED }}>
          Vide entièrement le pool et l&apos;historique de jobs. Le prochain balayage planifié repartira sur une base saine.
        </p>
        {!confirmReset ? (
          <button
            onClick={() => setConfirmReset(true)}
            className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors"
            style={{ color: SYS_RED, borderColor: 'rgba(229,62,62,.3)', background: 'rgba(229,62,62,.08)' }}
          >
            Réinitialiser le pool
          </button>
        ) : (
          <div className="flex gap-3 items-center">
            <span className="font-mono text-[11px]" style={{ color: SYS_RED }}>Confirmer la suppression complète ?</span>
            <button
              onClick={() => resetPool(undefined as unknown as void)}
              disabled={resetting}
              className="font-mono text-[11px] px-3 py-1.5 rounded border disabled:opacity-40"
              style={{ color: '#fff', borderColor: SYS_RED, background: SYS_RED }}
            >
              {resetting ? 'Suppression…' : 'Confirmer'}
            </button>
            <button
              onClick={() => setConfirmReset(false)}
              className="font-mono text-[11px] px-3 py-1.5 rounded border"
              style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
            >
              Annuler
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
