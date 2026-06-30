'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { useToast } from '@/lib/contexts/ToastContext'
import { agentApi } from '@/lib/api'
import { useAsync, useMutation, useInterval } from '@/lib/hooks'
import { formatRelative } from '@/lib/utils'

interface LogEntry {
  level: string
  event: string
  cycle_id?: string
  ts?: string
}

interface CycleState {
  cycle_id: string
  status: string
  mode: string
  published_count?: number
  errors?: string[]
  active_cycles?: number
}

export function AgentScreen() {
  const [mode, setMode] = useState<'semi' | 'auto'>('semi')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [currentCycleId, setCurrentCycleId] = useState<string | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const { show } = useToast()

  // Polling status
  const fetchStatus = useCallback(
    async () => agentApi.status(currentCycleId ?? undefined) as unknown as CycleState,
    [currentCycleId]
  )
  const { data: cycle, refetch: refetchStatus } = useAsync<CycleState>(fetchStatus)

  // Refresh pendant un cycle actif
  useInterval(
    refetchStatus,
    cycle?.status === 'RUNNING' ? 3000 : cycle?.status === 'PAUSED' ? 5000 : null
  )

  // SSE logs
  useEffect(() => {
    if (!currentCycleId) return
    const url = agentApi.streamUrl(currentCycleId)
    const es = new EventSource(url)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.event === 'heartbeat' || data.event === 'connected') return
        setLogs(prev => [...prev.slice(-199), data as LogEntry])
      } catch { /* ignore */ }
    }
    return () => es.close()
  }, [currentCycleId])

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const { mutate: runCycle, loading: running } = useMutation(async () => {
    setLogs([])
    const result = await agentApi.run(mode)
    const r = result as { cycle_id: string }
    setCurrentCycleId(r.cycle_id)
    addLog({ level: 'INFO', event: `Cycle ${mode.toUpperCase()} démarré — ID: ${r.cycle_id.slice(0, 8)}` })
    show(`Cycle ${mode} lancé`, 'success')
    await refetchStatus()
  })

  const { mutate: resumeCycle, loading: resuming } = useMutation(async () => {
    if (!currentCycleId) return
    await agentApi.resume(currentCycleId)
    addLog({ level: 'HITL', event: 'Validation accordée — reprise de la publication' })
    show('Cycle repris', 'success')
    await refetchStatus()
  })

  const { mutate: rejectCycle } = useMutation(async () => {
    if (!currentCycleId) return
    await agentApi.reject(currentCycleId)
    addLog({ level: 'HITL', event: 'Article rejeté — passage au suivant' })
    show('Article rejeté', 'warning')
    await refetchStatus()
  })

  function addLog(entry: LogEntry) {
    setLogs(prev => [...prev.slice(-199), { ...entry, ts: new Date().toISOString() }])
  }

  const isRunning = cycle?.status === 'RUNNING'
  const isPaused  = cycle?.status === 'PAUSED'

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-heading font-bold text-2xl text-anthracite">Agent KORA</h1>
        <p className="font-heading text-[13px] text-gray-dk mt-0.5">
          Contrôle du cycle IA · HITL · Logs temps réel
        </p>
      </div>

      {/* Contrôles */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        {/* Lancement */}
        <Card>
          <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
            Lancer un cycle
          </h2>
          <div className="space-y-4">
            <Toggle
              checked={mode === 'semi'}
              onChange={v => setMode(v ? 'semi' : 'auto')}
              label="Mode semi-automatique"
              description="Pause avant chaque publication pour validation manuelle"
            />

            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                size="md"
                loading={running}
                disabled={isRunning || isPaused}
                onClick={() => runCycle(undefined as unknown as void)}
                className="flex-1"
              >
                {isRunning ? 'Cycle en cours…' : 'Lancer le cycle'}
              </Button>
              {mode === 'semi' && !running && !isRunning && !isPaused && (
                <Badge variant="orange">HITL</Badge>
              )}
            </div>

            {isRunning && (
              <div className="flex items-center gap-2 text-orange">
                <span className="w-2 h-2 rounded-full bg-orange animate-[kora-pulse_2s_ease-in-out_infinite]" aria-hidden="true"/>
                <span className="font-heading text-[12px]">Cycle en cours d'exécution…</span>
              </div>
            )}
          </div>
        </Card>

        {/* Statut */}
        <Card>
          <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
            Statut du cycle
          </h2>
          {!cycle || cycle.status === 'IDLE' ? (
            <div className="empty-state py-4">
              <p className="font-heading text-[13px] text-gray-dk">Aucun cycle actif</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-heading text-[12px] text-gray-dk">Statut</span>
                <CycleStatusBadge status={cycle.status} />
              </div>
              <div className="flex items-center justify-between">
                <span className="font-heading text-[12px] text-gray-dk">Mode</span>
                <span className="font-heading text-[12px] font-medium text-anthracite capitalize">{cycle.mode}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-heading text-[12px] text-gray-dk">Publiés</span>
                <span className="font-heading text-[12px] font-bold text-sage">{cycle.published_count ?? 0}</span>
              </div>
              {cycle.cycle_id && (
                <div className="flex items-center justify-between">
                  <span className="font-heading text-[12px] text-gray-dk">ID</span>
                  <span className="font-mono text-[10px] text-gray-med">{cycle.cycle_id.slice(0, 8)}…</span>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* HITL validation */}
      {isPaused && (
        <Card className="mb-6 border-orange/30 bg-orange/5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-orange/20 flex items-center justify-center shrink-0">
              <span className="text-orange font-heading font-bold text-lg">!</span>
            </div>
            <div className="flex-1">
              <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-1">
                Article en attente de validation
              </h2>
              <p className="font-heading text-[13px] text-gray-dk mb-4">
                KORA a rédigé un article et attend votre validation avant de le publier sur WordPress.
                Consultez l'onglet Articles pour lire le contenu.
              </p>
              <div className="flex gap-3">
                <Button
                  variant="primary"
                  size="sm"
                  loading={resuming}
                  onClick={() => resumeCycle(undefined as unknown as void)}
                >
                  ✓ Valider et publier
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => rejectCycle(undefined as unknown as void)}
                >
                  Rejeter et passer
                </Button>
                <Button href="/articles?status=PENDING_REVIEW" variant="outline" size="sm">
                  Lire l'article →
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Terminal de logs */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-heading font-semibold text-[14px] text-anthracite">
            Logs temps réel
          </h2>
          <button
            onClick={() => setLogs([])}
            className="font-heading text-[11px] text-gray-dk hover:text-danger transition-colors"
          >
            Effacer
          </button>
        </div>
        <div className="terminal h-72 overflow-y-auto" role="log" aria-label="Logs KORA" aria-live="off">
          {logs.length === 0 ? (
            <p className="log-ts">// En attente des logs…</p>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex gap-3">
                <span className="log-ts shrink-0">
                  {log.ts ? new Date(log.ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                </span>
                <span className={logClass(log.level)}>[{log.level}]</span>
                <span className="text-gray-400 flex-1">{log.event}</span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  )
}

function CycleStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; variant: 'orange' | 'sage' | 'danger' | 'warning' | 'gray' }> = {
    RUNNING:   { label: 'En cours', variant: 'orange' },
    PAUSED:    { label: 'En pause', variant: 'warning' },
    COMPLETED: { label: 'Terminé', variant: 'sage' },
    FAILED:    { label: 'Échoué', variant: 'danger' },
    IDLE:      { label: 'Inactif', variant: 'gray' },
  }
  const { label, variant } = map[status] ?? { label: status, variant: 'gray' as const }
  return <Badge variant={variant} dot={status === 'RUNNING'} pulse={status === 'RUNNING'}>{label}</Badge>
}

function logClass(level: string): string {
  const map: Record<string, string> = {
    INFO: 'log-info', OK: 'log-ok', WARN: 'log-warn', ERROR: 'log-err', HITL: 'log-hitl',
  }
  return map[level.toUpperCase()] ?? 'text-gray-400'
}
