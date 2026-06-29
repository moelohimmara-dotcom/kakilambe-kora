'use client'

import { useState, useCallback } from 'react'
import { BASE_URL } from '@/lib/api'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'

type ServiceStatus = 'unknown' | 'checking' | 'ok' | 'error'

interface Service {
  id: string
  label: string
  description: string
  endpoint: string
  status: ServiceStatus
  latency_ms: number | null
  detail: string
}

const INITIAL_SERVICES: Service[] = [
  {
    id: 'wordpress',
    label: 'WordPress',
    description: 'Publication des articles via l\'API REST WP',
    endpoint: '/health/wordpress',
    status: 'unknown',
    latency_ms: null,
    detail: '',
  },
  {
    id: 'redis',
    label: 'Redis',
    description: 'Pub/sub pour SSE + cache sessions LangGraph',
    endpoint: '/health/redis',
    status: 'unknown',
    latency_ms: null,
    detail: '',
  },
  {
    id: 'supabase',
    label: 'Supabase (PostgreSQL)',
    description: 'Base de données principale — articles, cycles, sources',
    endpoint: '/health/database',
    status: 'unknown',
    latency_ms: null,
    detail: '',
  },
  {
    id: 'groq',
    label: 'Groq API',
    description: 'LLM principal — llama-3.3-70b-versatile',
    endpoint: '/health/providers/groq',
    status: 'unknown',
    latency_ms: null,
    detail: '',
  },
  {
    id: 'gemini',
    label: 'Gemini API',
    description: 'LLM fallback #2 — gemini-2.0-flash',
    endpoint: '/health/providers/gemini',
    status: 'unknown',
    latency_ms: null,
    detail: '',
  },
  {
    id: 'tavily',
    label: 'Tavily Search',
    description: 'Moteur de recherche actualités africaines',
    endpoint: '/health/tavily',
    status: 'unknown',
    latency_ms: null,
    detail: '',
  },
  {
    id: 'fal',
    label: 'Fal.ai (Flux)',
    description: 'Génération d\'images d\'illustration',
    endpoint: '/health/fal',
    status: 'unknown',
    latency_ms: null,
    detail: '',
  },
]

const STATUS_PROPS: Record<ServiceStatus, { color: string; label: string; dotColor: string }> = {
  unknown:  { color: SYS_MUTED,   label: 'Non testé',    dotColor: SYS_MUTED },
  checking: { color: '#3d6e99',   label: 'Test en cours…', dotColor: '#3d6e99' },
  ok:       { color: '#48bb78',   label: 'Connecté',     dotColor: '#48bb78' },
  error:    { color: '#fc8181',   label: 'Erreur',        dotColor: SYS_RED },
}

export default function ConnectionsPage() {
  const [services, setServices] = useState<Service[]>(INITIAL_SERVICES)
  const [checkingAll, setCheckingAll] = useState(false)

  const checkService = useCallback(async (id: string) => {
    setServices(prev => prev.map(s => s.id === id ? { ...s, status: 'checking', latency_ms: null, detail: '' } : s))

    const svc = INITIAL_SERVICES.find(s => s.id === id)!
    const t0 = Date.now()
    try {
      const r = await fetch(`${BASE_URL}${svc.endpoint}`, { cache: 'no-store' })
      const latency_ms = Date.now() - t0
      const body = await r.json().catch(() => ({}))
      setServices(prev => prev.map(s => s.id === id ? {
        ...s,
        status:     r.ok ? 'ok' : 'error',
        latency_ms,
        detail:     r.ok ? (body.detail ?? '') : (body.detail ?? body.error ?? `HTTP ${r.status}`),
      } : s))
    } catch (e: unknown) {
      setServices(prev => prev.map(s => s.id === id ? {
        ...s,
        status:     'error',
        latency_ms: Date.now() - t0,
        detail:     e instanceof Error ? e.message : 'Connexion échouée',
      } : s))
    }
  }, [])

  async function checkAll() {
    setCheckingAll(true)
    await Promise.all(INITIAL_SERVICES.map(s => checkService(s.id)))
    setCheckingAll(false)
  }

  const okCount = services.filter(s => s.status === 'ok').length
  const errCount = services.filter(s => s.status === 'error').length

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-mono font-bold text-xl text-white">Connexions</h1>
          <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>
            Vérification des services externes
          </p>
        </div>
        <div className="flex items-center gap-3">
          {(okCount > 0 || errCount > 0) && (
            <div className="font-mono text-[11px]">
              <span style={{ color: '#48bb78' }}>{okCount} OK</span>
              {errCount > 0 && <span style={{ color: SYS_RED }}> · {errCount} KO</span>}
            </div>
          )}
          <button
            onClick={checkAll}
            disabled={checkingAll}
            className="font-mono text-[11px] px-4 py-2 rounded border transition-colors disabled:opacity-40"
            style={{ color: SYS_TEXT, borderColor: SYS_BORDER, background: SYS_SURFACE }}
          >
            {checkingAll ? 'Test en cours…' : 'Tester tout'}
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {services.map(svc => {
          const props = STATUS_PROPS[svc.status]
          return (
            <div
              key={svc.id}
              className="flex items-center gap-4 p-4 rounded-xl border"
              style={{
                background:   SYS_SURFACE,
                borderColor:  svc.status === 'error' ? 'rgba(229,62,62,.35)' : svc.status === 'ok' ? 'rgba(72,187,120,.2)' : SYS_BORDER,
              }}
            >
              {/* Status dot */}
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{
                  background:  props.dotColor,
                  boxShadow:   svc.status === 'ok' ? '0 0 6px rgba(72,187,120,.5)' : svc.status === 'error' ? '0 0 6px rgba(229,62,62,.5)' : 'none',
                  animation:   svc.status === 'checking' ? 'kora-pulse 1s ease-in-out infinite' : 'none',
                }}
              />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="font-mono font-bold text-[13px] text-white">{svc.label}</div>
                <div className="font-mono text-[11px] mt-0.5" style={{ color: SYS_MUTED }}>
                  {svc.description}
                </div>
                {svc.detail && (
                  <div className="font-mono text-[10px] mt-1" style={{ color: svc.status === 'error' ? '#fc8181' : SYS_MUTED }}>
                    {svc.detail}
                  </div>
                )}
              </div>

              {/* Latency */}
              {svc.latency_ms !== null && (
                <div className="text-right shrink-0">
                  <div className="font-mono text-[12px]" style={{ color: svc.latency_ms < 300 ? '#48bb78' : svc.latency_ms < 1000 ? '#ecc94b' : '#fc8181' }}>
                    {svc.latency_ms} ms
                  </div>
                </div>
              )}

              {/* Status label */}
              <div
                className="font-mono text-[11px] shrink-0 text-right"
                style={{ color: props.color, minWidth: '90px' }}
              >
                {props.label}
              </div>

              {/* Test button */}
              <button
                onClick={() => checkService(svc.id)}
                disabled={svc.status === 'checking'}
                className="font-mono text-[10px] px-2.5 py-1.5 rounded border shrink-0 transition-colors disabled:opacity-30"
                style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
                onMouseEnter={e => (e.currentTarget.style.color = SYS_TEXT)}
                onMouseLeave={e => (e.currentTarget.style.color = SYS_MUTED)}
              >
                Tester
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
