'use client'

import { useState, useCallback } from 'react'
import { useAsync, useMutation } from '@/lib/hooks'
import { integrationsApi } from '@/lib/api'
import type { Integration } from '@/lib/api'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_TEXT    = '#d4d3ce'
const SYS_MUTED   = '#5a5956'
const SYS_RED     = '#e53e3e'

const STATUS_PROPS: Record<string, { color: string; label: string }> = {
  ok:       { color: '#48bb78', label: 'Connecté' },
  error:    { color: '#fc8181', label: 'Erreur' },
  not_used: { color: SYS_MUTED, label: 'Non utilisé' },
}

const KIND_LABEL: Record<string, string> = {
  llm: 'LLM', api: 'API', mcp: 'MCP', other: 'Autre',
}

// Root cause corrigée (audit 2026-07-15) : le tableau INITIAL_SERVICES
// était codé en dur ici (y compris "Gemini", abandonné depuis longtemps de
// la vraie chaîne de fallback LLM — cf. core/llm_router.py PROVIDER_ORDER)
// sans aucun lien programmatique avec les vraies routes /health/* de
// main.py. Toute donnée vient désormais de GET /api/integrations
// (migration 012, table `integrations`) — source déclarative unique,
// vérifiée en direct côté backend à chaque chargement. Ajouter une future
// intégration (MCP server, API) se fait par le formulaire ci-dessous, sans
// toucher un seul fichier de code existant.
export default function ConnectionsPage() {
  const fetchIntegrations = useCallback(() => integrationsApi.list(), [])
  const { data, loading, refetch } = useAsync<{ integrations: Integration[] }>(fetchIntegrations)
  const integrations = data?.integrations ?? []

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ key: '', label: '', kind: 'api', description: '', health_endpoint: '' })

  const { mutate: createIntegration, loading: creating, error: createError } = useMutation(
    async () => {
      await integrationsApi.create(form)
      setForm({ key: '', label: '', kind: 'api', description: '', health_endpoint: '' })
      setShowForm(false)
      await refetch()
    }
  )

  const { mutate: removeIntegration } = useMutation(async (id: string) => {
    await integrationsApi.remove(id)
    await refetch()
  })

  const okCount = integrations.filter(s => s.status === 'ok').length
  const errCount = integrations.filter(s => s.status === 'error').length

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-mono font-bold text-xl text-white">Connexions</h1>
          <p className="font-mono text-[12px] mt-1" style={{ color: SYS_MUTED }}>
            Registre d&apos;intégrations — vérification en direct
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
            onClick={() => refetch()}
            disabled={loading}
            className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors disabled:opacity-40"
            style={{ color: SYS_TEXT, borderColor: SYS_BORDER, background: SYS_SURFACE }}
          >
            {loading ? 'Vérification…' : '↺ Tester tout'}
          </button>
          <button
            onClick={() => setShowForm(v => !v)}
            className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors"
            style={{ color: '#48bb78', borderColor: 'rgba(72,187,120,.3)', background: 'rgba(72,187,120,.08)' }}
          >
            + Ajouter
          </button>
        </div>
      </div>

      {showForm && (
        <div className="mb-6 p-4 rounded-xl border space-y-3" style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="clé (ex. mon_mcp_server)"
              value={form.key}
              onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
              className="font-mono text-[12px] px-3 py-1.5 rounded border"
              style={{ background: '#1e1e1c', borderColor: SYS_BORDER, color: SYS_TEXT }}
            />
            <input
              placeholder="Libellé affiché"
              value={form.label}
              onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
              className="font-mono text-[12px] px-3 py-1.5 rounded border"
              style={{ background: '#1e1e1c', borderColor: SYS_BORDER, color: SYS_TEXT }}
            />
            <select
              value={form.kind}
              onChange={e => setForm(f => ({ ...f, kind: e.target.value }))}
              className="font-mono text-[12px] px-3 py-1.5 rounded border"
              style={{ background: '#1e1e1c', borderColor: SYS_BORDER, color: SYS_TEXT }}
            >
              {Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
            <input
              placeholder="/health/mon-endpoint"
              value={form.health_endpoint}
              onChange={e => setForm(f => ({ ...f, health_endpoint: e.target.value }))}
              className="font-mono text-[12px] px-3 py-1.5 rounded border"
              style={{ background: '#1e1e1c', borderColor: SYS_BORDER, color: SYS_TEXT }}
            />
            <input
              placeholder="Description (optionnel)"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              className="font-mono text-[12px] px-3 py-1.5 rounded border col-span-2"
              style={{ background: '#1e1e1c', borderColor: SYS_BORDER, color: SYS_TEXT }}
            />
          </div>
          {createError && <p className="font-mono text-[11px]" style={{ color: SYS_RED }}>{createError}</p>}
          <button
            onClick={() => createIntegration(undefined as unknown as void)}
            disabled={creating || !form.key || !form.label || !form.health_endpoint}
            className="font-mono text-[11px] px-3 py-1.5 rounded border disabled:opacity-40"
            style={{ color: '#48bb78', borderColor: 'rgba(72,187,120,.3)', background: 'rgba(72,187,120,.08)' }}
          >
            {creating ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      )}

      <div className="space-y-2">
        {integrations.map(svc => {
          const props = STATUS_PROPS[svc.status] ?? STATUS_PROPS.error
          return (
            <div
              key={svc.id}
              className="flex items-center gap-4 p-4 rounded-xl border"
              style={{
                background:  SYS_SURFACE,
                borderColor: svc.status === 'error' ? 'rgba(229,62,62,.35)' : svc.status === 'ok' ? 'rgba(72,187,120,.2)' : SYS_BORDER,
              }}
            >
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{
                  background: props.color,
                  boxShadow: svc.status === 'ok' ? '0 0 6px rgba(72,187,120,.5)' : svc.status === 'error' ? '0 0 6px rgba(229,62,62,.5)' : 'none',
                }}
              />

              <div className="flex-1 min-w-0">
                <div className="font-mono font-bold text-[13px] text-white">
                  {svc.label}
                  <span className="ml-2 font-mono text-[9px] px-1.5 py-0.5 rounded" style={{ color: SYS_MUTED, border: `1px solid ${SYS_BORDER}` }}>
                    {KIND_LABEL[svc.kind] ?? svc.kind}
                  </span>
                </div>
                <div className="font-mono text-[11px] mt-0.5" style={{ color: SYS_MUTED }}>
                  {svc.description}
                </div>
                {svc.detail && (
                  <div className="font-mono text-[10px] mt-1" style={{ color: svc.status === 'error' ? '#fc8181' : SYS_MUTED }}>
                    {svc.detail}
                  </div>
                )}
              </div>

              <div className="font-mono text-[11px] shrink-0 text-right" style={{ color: props.color, minWidth: '90px' }}>
                {props.label}
              </div>

              <button
                onClick={() => removeIntegration(svc.id)}
                className="font-mono text-[10px] px-2.5 py-1.5 rounded border shrink-0 transition-colors"
                style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
                title="Retirer du registre"
              >
                Retirer
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
