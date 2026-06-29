'use client'

import { useEffect, useState, useCallback } from 'react'
import { BASE_URL } from '@/lib/api'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'

interface ProviderHealth {
  name: string
  available: boolean
  latency_ms: number | null
  model: string
  priority: number
}

interface SystemHealth {
  status: string
  providers: ProviderHealth[]
  redis: boolean
  database: boolean
  wordpress: boolean
  uptime_seconds: number
  version: string
}

function ProviderGauge({ provider }: { provider: ProviderHealth }) {
  const latencyColor =
    !provider.available ? SYS_RED :
    (provider.latency_ms ?? 9999) < 1000 ? '#48bb78' :
    (provider.latency_ms ?? 9999) < 3000 ? '#ecc94b' : '#fc8181'

  const latencyPct = provider.available && provider.latency_ms !== null
    ? Math.min(100, (provider.latency_ms / 5000) * 100)
    : 100

  return (
    <div
      className="p-4 rounded-lg border"
      style={{ background: SYS_SURFACE, borderColor: provider.available ? SYS_BORDER : 'rgba(229,62,62,.35)' }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="font-mono font-bold text-[13px] text-white">{provider.name}</div>
          <div className="font-mono text-[10px] mt-0.5 truncate max-w-[160px]" style={{ color: SYS_MUTED }}>
            {provider.model}
          </div>
        </div>
        <span
          className="font-mono text-[10px] px-2 py-0.5 rounded border shrink-0"
          style={{
            color: provider.available ? '#48bb78' : SYS_RED,
            borderColor: provider.available ? 'rgba(72,187,120,.3)' : 'rgba(229,62,62,.3)',
            background: provider.available ? 'rgba(72,187,120,.08)' : 'rgba(229,62,62,.08)',
          }}
        >
          {provider.available ? 'UP' : 'DOWN'}
        </span>
      </div>

      {/* Latency bar */}
      <div className="mb-1">
        <div className="flex justify-between mb-1">
          <span className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>Latence</span>
          <span className="font-mono text-[11px]" style={{ color: latencyColor }}>
            {provider.latency_ms !== null ? `${provider.latency_ms} ms` : '—'}
          </span>
        </div>
        <div className="h-1 rounded-full overflow-hidden" style={{ background: '#1e1e1c' }}>
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${100 - latencyPct}%`, background: latencyColor }}
          />
        </div>
      </div>

      <div className="font-mono text-[10px] mt-2" style={{ color: SYS_MUTED }}>
        priorité #{provider.priority}
      </div>
    </div>
  )
}

function ServiceBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-md border" style={{ borderColor: SYS_BORDER, background: SYS_SURFACE }}>
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ background: ok ? '#48bb78' : SYS_RED, boxShadow: ok ? '0 0 6px rgba(72,187,120,.5)' : '0 0 6px rgba(229,62,62,.5)' }}
      />
      <span className="font-mono text-[12px]" style={{ color: SYS_TEXT }}>{label}</span>
      <span className="ml-auto font-mono text-[10px]" style={{ color: ok ? '#48bb78' : SYS_RED }}>{ok ? 'OK' : 'KO'}</span>
    </div>
  )
}

function formatUptime(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function SystemDashboardPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${BASE_URL}/health/system`, { cache: 'no-store' })
      if (r.ok) {
        const d = await r.json()
        setHealth(d)
      }
    } catch {
      // backend unavailable — keep stale data
    } finally {
      setLoading(false)
      setLastRefresh(new Date())
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [load])

  const providers: ProviderHealth[] = health?.providers ?? [
    { name: 'Groq',        model: 'llama-3.3-70b-versatile',  available: true,  latency_ms: 320,  priority: 1 },
    { name: 'Gemini',      model: 'gemini-2.0-flash',          available: true,  latency_ms: 780,  priority: 2 },
    { name: 'Cerebras',    model: 'llama3.1-70b',              available: false, latency_ms: null, priority: 3 },
    { name: 'OpenRouter',  model: 'mistralai/mistral-7b',      available: true,  latency_ms: 1250, priority: 4 },
  ]

  return (
    <div className="max-w-5xl">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-mono font-bold text-xl text-white">Dashboard système</h1>
          <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>
            État en temps réel de l'infrastructure KORA
          </p>
        </div>
        <div className="text-right">
          <button
            onClick={load}
            className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors"
            style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
            onMouseEnter={e => (e.currentTarget.style.color = SYS_TEXT)}
            onMouseLeave={e => (e.currentTarget.style.color = SYS_MUTED)}
          >
            ↺ Actualiser
          </button>
          {lastRefresh && (
            <div className="font-mono text-[10px] mt-1" style={{ color: SYS_MUTED }}>
              {lastRefresh.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </div>
          )}
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Statut global', value: health ? (health.status === 'ok' ? 'OPÉRATIONNEL' : 'DÉGRADÉ') : '…', accent: health?.status === 'ok' ? '#48bb78' : SYS_RED },
          { label: 'Uptime', value: health ? formatUptime(health.uptime_seconds) : '…', accent: SYS_TEXT },
          { label: 'Version', value: health?.version ?? 'v0.1.0', accent: SYS_TEXT },
          { label: 'Providers UP', value: loading ? '…' : `${providers.filter(p => p.available).length}/${providers.length}`, accent: SYS_TEXT },
        ].map(k => (
          <div key={k.label} className="p-4 rounded-lg border" style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}>
            <div className="font-mono text-[10px] uppercase tracking-widest mb-2" style={{ color: SYS_MUTED }}>{k.label}</div>
            <div className="font-mono font-bold text-[18px]" style={{ color: k.accent }}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Services */}
      <h2 className="font-mono text-[11px] uppercase tracking-widest mb-3" style={{ color: SYS_MUTED }}>Services</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-8">
        <ServiceBadge label="Redis"     ok={health?.redis     ?? true} />
        <ServiceBadge label="Supabase"  ok={health?.database  ?? true} />
        <ServiceBadge label="WordPress" ok={health?.wordpress ?? false} />
        <ServiceBadge label="API KORA"  ok={!loading} />
      </div>

      {/* Provider gauges */}
      <h2 className="font-mono text-[11px] uppercase tracking-widest mb-3" style={{ color: SYS_MUTED }}>
        Fournisseurs LLM — chaîne de fallback
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {providers.map(p => <ProviderGauge key={p.name} provider={p} />)}
      </div>
    </div>
  )
}
