'use client'

import { useState } from 'react'
import { BASE_URL } from '@/lib/api'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'

interface Provider {
  id: string
  name: string
  model: string
  priority: number
  enabled: boolean
  latency_ms: number | null
  cost_per_1k: number
  tokens_used_today: number
  tokens_limit: number
}

const INITIAL: Provider[] = [
  { id: 'groq',        name: 'Groq',       model: 'llama-3.3-70b-versatile', priority: 1, enabled: true,  latency_ms: 320,  cost_per_1k: 0.00027, tokens_used_today: 48200,  tokens_limit: 500000 },
  { id: 'gemini',      name: 'Gemini',     model: 'gemini-2.0-flash',         priority: 2, enabled: true,  latency_ms: 780,  cost_per_1k: 0.00010, tokens_used_today: 21000,  tokens_limit: 1000000 },
  { id: 'cerebras',    name: 'Cerebras',   model: 'llama3.1-70b',             priority: 3, enabled: false, latency_ms: null, cost_per_1k: 0.00060, tokens_used_today: 0,       tokens_limit: 200000 },
  { id: 'openrouter',  name: 'OpenRouter', model: 'mistralai/mistral-7b',     priority: 4, enabled: true,  latency_ms: 1250, cost_per_1k: 0.00055, tokens_used_today: 6100,   tokens_limit: 300000 },
]

export default function ProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>(INITIAL)
  const [saving, setSaving]       = useState<string | null>(null)

  async function toggleProvider(id: string) {
    setSaving(id)
    setProviders(prev => prev.map(p => p.id === id ? { ...p, enabled: !p.enabled } : p))
    try {
      const p = providers.find(x => x.id === id)!
      await fetch(`${BASE_URL}/settings/providers/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !p.enabled }),
      })
    } catch { /* ignore */ }
    setSaving(null)
  }

  async function movePriority(id: string, dir: -1 | 1) {
    setProviders(prev => {
      const arr = [...prev].sort((a, b) => a.priority - b.priority)
      const idx = arr.findIndex(p => p.id === id)
      const swapIdx = idx + dir
      if (swapIdx < 0 || swapIdx >= arr.length) return prev
      const newArr = [...arr]
      const tmp = newArr[idx].priority
      newArr[idx]     = { ...newArr[idx],     priority: newArr[swapIdx].priority }
      newArr[swapIdx] = { ...newArr[swapIdx], priority: tmp }
      return newArr
    })
  }

  const sorted = [...providers].sort((a, b) => a.priority - b.priority)

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="font-mono font-bold text-xl text-white">Fournisseurs LLM</h1>
        <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>
          Chaîne de fallback — réordonnez par priorité, activez ou désactivez
        </p>
      </div>

      <div className="space-y-3">
        {sorted.map((p, idx) => {
          const usagePct = p.tokens_limit > 0 ? (p.tokens_used_today / p.tokens_limit) * 100 : 0
          const usageColor = usagePct > 80 ? SYS_RED : usagePct > 50 ? '#ecc94b' : '#48bb78'
          const latencyColor =
            !p.enabled || p.latency_ms === null ? SYS_MUTED :
            p.latency_ms < 1000 ? '#48bb78' :
            p.latency_ms < 3000 ? '#ecc94b' : '#fc8181'

          return (
            <div
              key={p.id}
              className="p-5 rounded-xl border"
              style={{
                background: SYS_SURFACE,
                borderColor: p.enabled ? SYS_BORDER : 'rgba(229,62,62,.2)',
                opacity: p.enabled ? 1 : 0.65,
              }}
            >
              <div className="flex items-center gap-4 flex-wrap">
                {/* Priority badge */}
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center font-mono font-bold text-[12px] shrink-0"
                  style={{ background: p.enabled ? '#1e1e1c' : '#1e1e1c', color: p.enabled ? SYS_TEXT : SYS_MUTED, border: `1px solid ${SYS_BORDER}` }}
                >
                  {p.priority}
                </div>

                {/* Name + model */}
                <div className="flex-1 min-w-0">
                  <div className="font-mono font-bold text-[14px] text-white">{p.name}</div>
                  <div className="font-mono text-[11px] mt-0.5 truncate" style={{ color: SYS_MUTED }}>{p.model}</div>
                </div>

                {/* Latency */}
                <div className="text-right">
                  <div className="font-mono text-[11px]" style={{ color: latencyColor }}>
                    {p.latency_ms !== null ? `${p.latency_ms} ms` : '—'}
                  </div>
                  <div className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>latence</div>
                </div>

                {/* Cost */}
                <div className="text-right">
                  <div className="font-mono text-[11px]" style={{ color: SYS_TEXT }}>
                    ${p.cost_per_1k.toFixed(5)}
                  </div>
                  <div className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>/ 1k tokens</div>
                </div>

                {/* Priority arrows */}
                <div className="flex flex-col gap-0.5">
                  <button
                    onClick={() => movePriority(p.id, -1)}
                    disabled={idx === 0}
                    className="font-mono text-[11px] px-1.5 py-0.5 rounded disabled:opacity-20"
                    style={{ color: SYS_MUTED, background: '#1e1e1c' }}
                    aria-label="Monter"
                  >
                    ↑
                  </button>
                  <button
                    onClick={() => movePriority(p.id, 1)}
                    disabled={idx === sorted.length - 1}
                    className="font-mono text-[11px] px-1.5 py-0.5 rounded disabled:opacity-20"
                    style={{ color: SYS_MUTED, background: '#1e1e1c' }}
                    aria-label="Descendre"
                  >
                    ↓
                  </button>
                </div>

                {/* Toggle */}
                <button
                  onClick={() => toggleProvider(p.id)}
                  disabled={saving === p.id}
                  className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors"
                  style={{
                    color:        p.enabled ? '#48bb78' : SYS_RED,
                    borderColor:  p.enabled ? 'rgba(72,187,120,.3)' : 'rgba(229,62,62,.3)',
                    background:   p.enabled ? 'rgba(72,187,120,.08)' : 'rgba(229,62,62,.08)',
                  }}
                >
                  {saving === p.id ? '…' : p.enabled ? 'Actif' : 'Inactif'}
                </button>
              </div>

              {/* Usage bar */}
              <div className="mt-4">
                <div className="flex justify-between mb-1">
                  <span className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>
                    Tokens aujourd'hui
                  </span>
                  <span className="font-mono text-[10px]" style={{ color: usageColor }}>
                    {p.tokens_used_today.toLocaleString('fr-FR')} / {p.tokens_limit.toLocaleString('fr-FR')}
                    &nbsp;({usagePct.toFixed(1)}%)
                  </span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#1e1e1c' }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${usagePct}%`, background: usageColor }}
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
