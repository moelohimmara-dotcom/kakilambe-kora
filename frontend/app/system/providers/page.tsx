'use client'

import { useCallback, useState } from 'react'
import { useAsync, useMutation } from '@/lib/hooks'
import { providerApi } from '@/lib/api'
import type { Provider } from '@/lib/types'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'

// Vraies données (GET /api/providers, même endpoint réel que /settings →
// onglet "Fournisseurs LLM") — cet écran affichait auparavant un tableau
// INITIAL 100% statique et fictif (latences/coûts/tokens jamais rafraîchis),
// et un réordonnancement de priorité qui ne persistait nulle part. La
// priorité de fallback (PROVIDER_ORDER) est fixe dans core/llm_router.py,
// pas reconfigurable via API — affichée ici en lecture seule plutôt que
// comme un contrôle éditable qui ne faisait rien de réel.
export default function ProvidersPage() {
  const fetchProviders = useCallback(() => providerApi.list(), [])
  const { data: providers, loading, refetch } = useAsync<Provider[]>(fetchProviders)
  const [saving, setSaving] = useState<string | null>(null)

  const { mutate: setStatus } = useMutation(async ({ name, status }: { name: string; status: string }) => {
    setSaving(name)
    try {
      await providerApi.override(name, status)
      await refetch()
    } finally {
      setSaving(null)
    }
  })

  const list = providers ?? []

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="font-mono font-bold text-xl text-white">Fournisseurs LLM</h1>
        <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>
          Chaîne de fallback (ordre fixe) — santé temps réel et bascule manuelle
        </p>
      </div>

      {loading ? (
        <div className="font-mono text-[12px] py-8 text-center" style={{ color: SYS_MUTED }}>
          Chargement…
        </div>
      ) : (
        <div className="space-y-3">
          {list.map((p, idx) => {
            const enabled = p.status === 'ACTIVE'
            const usagePct = p.usage_pct ?? (p.daily_token_limit ? (p.tokens_used_today / p.daily_token_limit) * 100 : 0)
            const usageColor = usagePct > 80 ? SYS_RED : usagePct > 50 ? '#ecc94b' : '#48bb78'

            return (
              <div
                key={p.name}
                className="p-5 rounded-xl border"
                style={{
                  background: SYS_SURFACE,
                  borderColor: enabled ? SYS_BORDER : 'rgba(229,62,62,.2)',
                  opacity: enabled ? 1 : 0.65,
                }}
              >
                <div className="flex items-center gap-4 flex-wrap">
                  {/* Position dans la chaîne de fallback — fixe, lecture seule */}
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center font-mono font-bold text-[12px] shrink-0"
                    style={{ background: '#1e1e1c', color: SYS_TEXT, border: `1px solid ${SYS_BORDER}` }}
                    title="Ordre de fallback — fixe, non reconfigurable"
                  >
                    {idx + 1}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="font-mono font-bold text-[14px] text-white capitalize">{p.name}</div>
                    <div className="font-mono text-[11px] mt-0.5 truncate" style={{ color: SYS_MUTED }}>{p.model}</div>
                  </div>

                  <div className="text-right">
                    <div className="font-mono text-[11px]" style={{ color: SYS_TEXT }}>
                      {p.requests_today}
                    </div>
                    <div className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>requêtes aujourd&apos;hui</div>
                  </div>

                  <button
                    onClick={() => setStatus({ name: p.name, status: enabled ? 'OFFLINE' : 'ACTIVE' })}
                    disabled={saving === p.name}
                    className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors disabled:opacity-40"
                    style={{
                      color:        enabled ? '#48bb78' : SYS_RED,
                      borderColor:  enabled ? 'rgba(72,187,120,.3)' : 'rgba(229,62,62,.3)',
                      background:   enabled ? 'rgba(72,187,120,.08)' : 'rgba(229,62,62,.08)',
                    }}
                  >
                    {saving === p.name ? '…' : p.status}
                  </button>
                </div>

                <div className="mt-4">
                  <div className="flex justify-between mb-1">
                    <span className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>
                      Tokens aujourd&apos;hui
                    </span>
                    <span className="font-mono text-[10px]" style={{ color: usageColor }}>
                      {p.tokens_used_today.toLocaleString('fr-FR')}
                      {p.daily_token_limit ? ` / ${p.daily_token_limit.toLocaleString('fr-FR')}` : ''}
                      &nbsp;({usagePct.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#1e1e1c' }}>
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(usagePct, 100)}%`, background: usageColor }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
