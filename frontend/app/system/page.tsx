'use client'

import { useEffect, useState, useCallback } from 'react'
import { BASE_URL, providerApi } from '@/lib/api'
import type { Provider } from '@/lib/types'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'

interface AggregatedHealth {
  status: string
  version: string
  db: boolean
  redis: boolean
  wordpress: boolean
}

// Reconstruit à partir des vrais endpoints existants (GET /health,
// GET /health/redis, GET /api/providers) — GET /health/system n'existe pas
// dans le backend (grep négatif sur main.py), donc cet écran affichait
// auparavant en PERMANENCE les données de repli codées en dur (jamais de
// vraie donnée), alors que le CDC les présentait comme un filet de sécurité
// occasionnel pour une panne réelle. Pas de source réelle pour l'uptime
// process — affiché honnêtement "—" plutôt qu'inventé.
function ProviderGauge({ provider }: { provider: Provider }) {
  const available = provider.status === 'ACTIVE'
  const usagePct = provider.usage_pct ?? (
    provider.daily_token_limit ? (provider.tokens_used_today / provider.daily_token_limit) * 100 : null
  )
  const barColor = !available ? SYS_RED : (usagePct ?? 0) > 80 ? '#ecc94b' : '#48bb78'

  return (
    <div
      className="p-4 rounded-lg border"
      style={{ background: SYS_SURFACE, borderColor: available ? SYS_BORDER : 'rgba(229,62,62,.35)' }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="font-mono font-bold text-[13px] text-white capitalize">{provider.name}</div>
          <div className="font-mono text-[10px] mt-0.5 truncate max-w-[160px]" style={{ color: SYS_MUTED }}>
            {provider.model}
          </div>
        </div>
        <span
          className="font-mono text-[10px] px-2 py-0.5 rounded border shrink-0"
          style={{
            color: available ? '#48bb78' : SYS_RED,
            borderColor: available ? 'rgba(72,187,120,.3)' : 'rgba(229,62,62,.3)',
            background: available ? 'rgba(72,187,120,.08)' : 'rgba(229,62,62,.08)',
          }}
        >
          {provider.status}
        </span>
      </div>
      <div className="mb-1">
        <div className="flex justify-between mb-1">
          <span className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>Tokens / jour</span>
          <span className="font-mono text-[11px]" style={{ color: barColor }}>
            {usagePct !== null ? `${usagePct.toFixed(0)}%` : '—'}
          </span>
        </div>
        <div className="h-1 rounded-full overflow-hidden" style={{ background: '#1e1e1c' }}>
          <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(usagePct ?? 0, 100)}%`, background: barColor }} />
        </div>
      </div>
      <div className="font-mono text-[10px] mt-2" style={{ color: SYS_MUTED }}>{provider.requests_today} requêtes aujourd&apos;hui</div>
    </div>
  )
}

function ServiceBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-md border" style={{ borderColor: SYS_BORDER, background: SYS_SURFACE }}>
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: ok ? '#48bb78' : SYS_RED }} />
      <span className="font-mono text-[12px]" style={{ color: SYS_TEXT }}>{label}</span>
      <span className="ml-auto font-mono text-[10px]" style={{ color: ok ? '#48bb78' : SYS_RED }}>{ok ? 'OK' : 'KO'}</span>
    </div>
  )
}

export default function SystemDashboardPage() {
  const [health, setHealth] = useState<AggregatedHealth | null>(null)
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    const [healthRes, redisRes, providersRes] = await Promise.allSettled([
      fetch(`${BASE_URL}/health`, { cache: 'no-store' }).then(r => r.json()),
      fetch(`${BASE_URL}/health/redis`, { cache: 'no-store' }).then(r => r.json()),
      providerApi.list(),
    ])

    if (healthRes.status === 'fulfilled') {
      const h = healthRes.value as { status: string; version: string; services?: Record<string, string> }
      setHealth({
        status: h.status,
        version: h.version,
        db: h.services?.db === 'ok',
        wordpress: h.services?.wordpress === 'ok',
        redis: redisRes.status === 'fulfilled' ? redisRes.value.status === 'ok' : false,
      })
    } else {
      setHealth(null)
    }

    setProviders(providersRes.status === 'fulfilled' ? providersRes.value : [])
    setLoading(false)
  }, [])

  useEffect(() => { load(); const id = setInterval(load, 30_000); return () => clearInterval(id) }, [load])

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-mono font-bold text-xl text-white">Dashboard système</h1>
          <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>État en temps réel de l&apos;infrastructure KORA</p>
        </div>
        <button onClick={load} className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors" style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}>
          ↺ Actualiser
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
        {[
          { label: 'Statut global', value: health ? (health.status === 'ok' ? 'OPÉRATIONNEL' : 'DÉGRADÉ') : loading ? '…' : 'INJOIGNABLE', accent: health?.status === 'ok' ? '#48bb78' : SYS_RED },
          { label: 'Version', value: health?.version ?? '—', accent: SYS_TEXT },
          { label: 'Providers UP', value: loading ? '…' : `${providers.filter(p => p.status === 'ACTIVE').length}/${providers.length}`, accent: SYS_TEXT },
        ].map(k => (
          <div key={k.label} className="p-4 rounded-lg border" style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}>
            <div className="font-mono text-[10px] uppercase tracking-widest mb-2" style={{ color: SYS_MUTED }}>{k.label}</div>
            <div className="font-mono font-bold text-[18px]" style={{ color: k.accent }}>{k.value}</div>
          </div>
        ))}
      </div>
      <h2 className="font-mono text-[11px] uppercase tracking-widest mb-3" style={{ color: SYS_MUTED }}>Services</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-8">
        <ServiceBadge label="Redis"     ok={health?.redis     ?? false} />
        <ServiceBadge label="Supabase"  ok={health?.db        ?? false} />
        <ServiceBadge label="WordPress" ok={health?.wordpress ?? false} />
        <ServiceBadge label="API KORA"  ok={health !== null} />
      </div>
      <h2 className="font-mono text-[11px] uppercase tracking-widest mb-3" style={{ color: SYS_MUTED }}>Fournisseurs LLM — chaîne de fallback</h2>
      {loading ? (
        <div className="font-mono text-[12px] py-8 text-center" style={{ color: SYS_MUTED }}>Chargement…</div>
      ) : providers.length === 0 ? (
        <div className="font-mono text-[12px] py-8 text-center" style={{ color: SYS_MUTED }}>Providers injoignables</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {providers.map(p => <ProviderGauge key={p.name} provider={p} />)}
        </div>
      )}
    </div>
  )
}
