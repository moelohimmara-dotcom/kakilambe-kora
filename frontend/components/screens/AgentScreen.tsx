'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { useToast } from '@/lib/contexts/ToastContext'
import { agentApi, articleApi } from '@/lib/api'
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

const CYCLE_ID_STORAGE_KEY = 'kora_current_cycle_id'

export function AgentScreen() {
  const [mode, setMode] = useState<'semi' | 'auto'>('semi')
  const [logs, setLogs] = useState<LogEntry[]>([])
  // Persisté en localStorage : évite de perdre le fil du cycle en cours si
  // l'utilisateur rafraîchit la page (le backend garde son propre état tant
  // qu'il n'a pas redémarré — /api/agent/status retombe sur la DB sinon).
  const [currentCycleId, setCurrentCycleId] = useState<string | null>(null)
  const [logsFading, setLogsFading] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const logsFadeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const logsClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const prevCycleStatusRef = useRef<string | undefined>(undefined)
  const { show } = useToast()

  function _clearLogsResetTimers() {
    if (logsFadeTimerRef.current) clearTimeout(logsFadeTimerRef.current)
    if (logsClearTimerRef.current) clearTimeout(logsClearTimerRef.current)
    setLogsFading(false)
    setLogs([])
  }
  // Garde anti-double-clic : `loading` du hook useMutation ne se répercute
  // sur le DOM (bouton disabled) qu'après le prochain rendu — un double-clic
  // très rapide peut donc déclencher deux appels avant que le bouton ne se
  // désactive visuellement, d'où le message d'erreur affiché deux fois.
  const hitlActionInFlight = useRef(false)

  useEffect(() => {
    const saved = localStorage.getItem(CYCLE_ID_STORAGE_KEY)
    if (saved) setCurrentCycleId(saved)
  }, [])

  // Polling status
  const fetchStatus = useCallback(
    async () => agentApi.status(currentCycleId ?? undefined) as unknown as CycleState,
    [currentCycleId]
  )
  const { data: cycle, refetch: refetchStatus } = useAsync<CycleState>(fetchStatus)

  // Reprise de session : si aucun cycle_id local mais que le backend en
  // retrouve un actif (via la DB — cf. _get_active_cycle_from_db), on
  // l'adopte automatiquement plutôt que de rester bloqué sur "Inactif".
  useEffect(() => {
    if (!currentCycleId && cycle?.cycle_id && (cycle.status === 'RUNNING' || cycle.status === 'PAUSED')) {
      setCurrentCycleId(cycle.cycle_id)
    }
  }, [currentCycleId, cycle])

  // Persiste / nettoie le cycle_id courant selon son statut
  useEffect(() => {
    if (!currentCycleId) return
    if (cycle?.status && ['COMPLETED', 'FAILED', 'CANCELLED'].includes(cycle.status)) {
      localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
    } else {
      localStorage.setItem(CYCLE_ID_STORAGE_KEY, currentCycleId)
    }
  }, [currentCycleId, cycle?.status])

  // Nettoyage automatique de la console de logs à la clôture réussie d'un
  // cycle (mode autonome) : laisse le temps de lire la confirmation, puis
  // fait un fade-out avant de vider — sans toucher à la connexion SSE
  // (effet séparé ci-dessous, gardé actif tant que currentCycleId ne change
  // pas).
  useEffect(() => {
    const prevStatus = prevCycleStatusRef.current
    const currentStatus = cycle?.status
    prevCycleStatusRef.current = currentStatus

    if (prevStatus !== 'COMPLETED' && currentStatus === 'COMPLETED') {
      logsFadeTimerRef.current = setTimeout(() => {
        setLogsFading(true)
        logsClearTimerRef.current = setTimeout(() => {
          setLogs([])
          setLogsFading(false)
        }, 500)
      }, 7000)
    }

    return () => {
      if (logsFadeTimerRef.current) clearTimeout(logsFadeTimerRef.current)
      if (logsClearTimerRef.current) clearTimeout(logsClearTimerRef.current)
    }
  }, [cycle?.status])

  // Refresh pendant un cycle actif
  useInterval(
    refetchStatus,
    cycle?.status === 'RUNNING' ? 3000 : cycle?.status === 'PAUSED' ? 5000 : null
  )

  // Article réellement en attente pour ce cycle — sans ça, "Lire l'article"
  // pointait vers une liste filtrée générique qui, en pratique, montrait
  // surtout des articles déjà publiés/supprimés (le filtre par status n'était
  // même pas appliqué côté page Articles). On résout ici l'article concret et
  // on pointe directement dessus.
  const fetchPendingArticle = useCallback(async () => {
    if (cycle?.status !== 'PAUSED') return null
    const list = await articleApi.list('PENDING_REVIEW')
    return list.items.find(a => a.cycle_id === (cycle?.cycle_id ?? currentCycleId)) ?? list.items[0] ?? null
  }, [cycle?.status, cycle?.cycle_id, currentCycleId])
  const { data: pendingArticle } = useAsync(fetchPendingArticle, [cycle?.status, cycle?.cycle_id])

  // SSE logs — rejoue l'historique DB (event replay) puis bascule en direct
  useEffect(() => {
    if (!currentCycleId) return
    const url = agentApi.streamUrl(currentCycleId)
    const es = new EventSource(url)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (['heartbeat', 'connected', 'done', 'history_end'].includes(data.event)) return
        setLogs(prev => [...prev.slice(-199), data as LogEntry])
      } catch { /* ignore */ }
    }
    return () => es.close()
  }, [currentCycleId])

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // useMutation avale les erreurs en silence (les stocke dans son `error`
  // interne sans les afficher) — sans try/catch explicite ici, un échec
  // réseau ou un 404 ne produit AUCUN retour visible : ni succès, ni erreur,
  // le clic semble juste "ne rien faire". C'était le vrai bug derrière
  // "les boutons ne s'exécutent pas jusqu'au bout".
  function _isLostSessionError(e: unknown): boolean {
    const msg = e instanceof Error ? e.message : String(e)
    return msg.includes('404') || msg.includes('409') || msg.toLowerCase().includes('non trouvé')
  }

  // Repli quand le cycle LangGraph n'est plus résumable (session perdue au
  // redémarrage du backend) : le résultat pratique voulu par l'utilisateur —
  // publier ou rejeter l'article — reste atteignable directement au niveau
  // de l'article, sans dépendre du checkpoint en mémoire. Avant, le bouton
  // se contentait d'afficher un message renvoyant vers la page Articles ;
  // maintenant il fait le travail lui-même.
  async function _fallbackToArticleAction(action: 'approve' | 'reject'): Promise<boolean> {
    const list = await articleApi.list('PENDING_REVIEW')
    const article = list.items.find(a => a.cycle_id === currentCycleId) ?? list.items[0]
    if (!article) return false
    if (action === 'approve') {
      await articleApi.approve(article.id)
    } else {
      await articleApi.reject(article.id)
    }
    return true
  }

  function _friendlyError(e: unknown): string {
    const msg = e instanceof Error ? e.message : String(e)
    if (_isLostSessionError(e)) {
      return "Ce cycle n'est plus actif en mémoire (le backend a probablement redémarré depuis sa mise en pause). Utilise la page Articles pour approuver/rejeter directement l'article en attente."
    }
    return msg
  }

  const { mutate: runCycle, loading: running } = useMutation(async () => {
    try {
      _clearLogsResetTimers()
      const result = await agentApi.run(mode)
      const r = result as { cycle_id: string }
      setCurrentCycleId(r.cycle_id)
      addLog({ level: 'INFO', event: `Cycle ${mode.toUpperCase()} démarré — ID: ${r.cycle_id.slice(0, 8)}` })
      show(`Cycle ${mode} lancé`, 'success')
      await refetchStatus()
    } catch (e) {
      show(_friendlyError(e), 'error')
    }
  })

  const { mutate: resumeCycle, loading: resuming } = useMutation(async () => {
    if (!currentCycleId || hitlActionInFlight.current) return
    hitlActionInFlight.current = true
    try {
      await agentApi.resume(currentCycleId)
      addLog({ level: 'HITL', event: 'Validation accordée — reprise de la publication' })
      show('Cycle repris', 'success')
      await refetchStatus()
    } catch (e) {
      if (_isLostSessionError(e)) {
        try {
          const handled = await _fallbackToArticleAction('approve')
          if (handled) {
            addLog({ level: 'HITL', event: 'Session perdue — article approuvé directement' })
            show('Article approuvé et envoyé en publication', 'success')
            localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
            setCurrentCycleId(null)
            await refetchStatus()
            return
          }
        } catch (fallbackErr) {
          show(_friendlyError(fallbackErr), 'error')
          return
        } finally {
          hitlActionInFlight.current = false
        }
      }
      show(_friendlyError(e), 'error')
    } finally {
      hitlActionInFlight.current = false
    }
  })

  const { mutate: rejectCycle } = useMutation(async () => {
    if (!currentCycleId || hitlActionInFlight.current) return
    hitlActionInFlight.current = true
    try {
      await agentApi.reject(currentCycleId)
      addLog({ level: 'HITL', event: 'Article rejeté — passage au suivant' })
      show('Article rejeté', 'warning')
      await refetchStatus()
    } catch (e) {
      if (_isLostSessionError(e)) {
        try {
          const handled = await _fallbackToArticleAction('reject')
          if (handled) {
            addLog({ level: 'HITL', event: 'Session perdue — article rejeté directement' })
            show('Article rejeté', 'warning')
            localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
            setCurrentCycleId(null)
            await refetchStatus()
            return
          }
        } catch (fallbackErr) {
          show(_friendlyError(fallbackErr), 'error')
          return
        } finally {
          hitlActionInFlight.current = false
        }
      }
      show(_friendlyError(e), 'error')
    } finally {
      hitlActionInFlight.current = false
    }
  })

  const { mutate: cancelCycle, loading: cancelling } = useMutation(async () => {
    if (!currentCycleId) return
    try {
      await agentApi.cancel(currentCycleId)
      addLog({ level: 'WARN', event: 'Annulation demandée par l\'utilisateur' })
      show('Cycle annulé', 'warning')
      await refetchStatus()
    } catch (e) {
      show(_friendlyError(e), 'error')
    }
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

            {(isRunning || isPaused) && (
              <Button
                variant="danger"
                size="sm"
                loading={cancelling}
                onClick={() => cancelCycle(undefined as unknown as void)}
                className="w-full"
              >
                ⏹ Annuler le cycle
              </Button>
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
                <Button
                  href={pendingArticle ? `/articles/${pendingArticle.id}` : '/articles?status=PENDING_REVIEW'}
                  variant="outline"
                  size="sm"
                >
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
            onClick={_clearLogsResetTimers}
            className="font-heading text-[11px] text-gray-dk hover:text-danger transition-colors"
          >
            Effacer
          </button>
        </div>
        <div
          className={`terminal h-72 overflow-y-auto transition-opacity duration-500 ${logsFading ? 'opacity-0' : 'opacity-100'}`}
          role="log"
          aria-label="Logs KORA"
          aria-live="off"
        >
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
    CANCELLED: { label: 'Annulé', variant: 'gray' },
    IDLE:      { label: 'Inactif', variant: 'gray' },
  }
  const { label, variant } = map[status] ?? { label: status, variant: 'gray' as const }
  return <Badge variant={variant} dot={status === 'RUNNING'} pulse={status === 'RUNNING'}>{label}</Badge>
}

function logClass(level: string): string {
  const map: Record<string, string> = {
    INFO: 'log-info', OK: 'log-ok', WARN: 'log-warn', ERROR: 'log-err', HITL: 'log-hitl',
  }
  return map[(level || '').toUpperCase()] ?? 'text-gray-400'
}
