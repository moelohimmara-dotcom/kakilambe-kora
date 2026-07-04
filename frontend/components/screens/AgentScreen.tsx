'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { Spinner } from '@/components/ui/Spinner'
import { useToast } from '@/lib/contexts/ToastContext'
import { agentApi, articleApi } from '@/lib/api'
import { useAsync, useMutation, useInterval } from '@/lib/hooks'

interface CycleState {
  cycle_id: string
  status: string
  mode: string
  published_count?: number
  errors?: string[]
  active_cycles?: number
}

const CYCLE_ID_STORAGE_KEY = 'kora_current_cycle_id'

// Combien de temps on tolère un cycle PAUSED sans parvenir à résoudre
// l'article concret associé (cas limite : redémarrage backend pile à ce
// moment) avant d'abandonner l'attente plutôt que de bloquer l'utilisateur
// indéfiniment sur l'écran de chargement.
const PENDING_ARTICLE_RESOLUTION_TIMEOUT_MS = 15000

export function AgentScreen() {
  const router = useRouter()
  const [mode, setMode] = useState<'semi' | 'auto'>('semi')
  const [currentCycleId, setCurrentCycleId] = useState<string | null>(null)
  const { show } = useToast()
  // Garde anti-double-clic : `loading` du hook useMutation ne se répercute
  // sur le DOM (bouton disabled) qu'après le prochain rendu — un double-clic
  // très rapide peut donc déclencher deux appels avant que le bouton ne se
  // désactive visuellement.
  const hitlActionInFlight = useRef(false)
  // Évite de relancer une redirection si l'utilisateur revient sur /agent
  // après avoir déjà été redirigé pour ce même cycle (ex: navigation
  // arrière), et se réinitialise à chaque nouveau lancement de cycle.
  const redirectedForCycleRef = useRef<string | null>(null)
  const pendingSinceRef = useRef<number | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem(CYCLE_ID_STORAGE_KEY)
    if (saved) setCurrentCycleId(saved)
  }, [])

  // Polling status — reste la source de vérité unique. Un flux synchrone
  // (attendre la réponse HTTP de /run jusqu'à la pause HITL) exposerait une
  // requête ouverte de 1 à 3 minutes à la moindre coupure réseau ou fermeture
  // d'onglet, sans aucun moyen de reprendre le fil ensuite. Le polling
  // conserve cette résilience tout en offrant la même expérience visuelle
  // (écran de chargement plein écran, sans logs bruts, jusqu'à la
  // redirection automatique).
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

  // Refresh pendant un cycle actif — cadence resserrée en PAUSED puisque
  // c'est l'instant où on doit détecter et résoudre l'article au plus vite
  // pour déclencher la redirection.
  useInterval(
    refetchStatus,
    cycle?.status === 'RUNNING' ? 2000 : cycle?.status === 'PAUSED' ? 1500 : null
  )

  const isRunning = cycle?.status === 'RUNNING'
  const isPaused = cycle?.status === 'PAUSED'
  const isFailed = cycle?.status === 'FAILED'

  // Article réellement en attente pour ce cycle — c'est la cible de la
  // redirection automatique. Résolu par cycle_id plutôt que par simple
  // présomption du premier PENDING_REVIEW pour éviter d'atterrir sur
  // l'article d'un autre cycle en cas de croisement.
  const fetchPendingArticle = useCallback(async () => {
    if (!isPaused) return null
    const list = await articleApi.list('PENDING_REVIEW')
    return list.items.find(a => a.cycle_id === (cycle?.cycle_id ?? currentCycleId)) ?? list.items[0] ?? null
  }, [isPaused, cycle?.cycle_id, currentCycleId])
  const { data: pendingArticle } = useAsync(fetchPendingArticle, [isPaused, cycle?.cycle_id])

  // Bug corrigé : cet effet redirigeait AUTOMATIQUEMENT vers l'article dès
  // qu'il détectait isPaused+pendingArticle — y compris quand l'utilisateur
  // arrivait sur /agent par une navigation VOLONTAIRE (clic sur le menu)
  // alors qu'un cycle d'une session précédente était encore en PAUSED avec
  // son article toujours PENDING_REVIEW (rien n'ayant changé son statut
  // entretemps). Résultat : impossible de revenir sur le tableau de bord
  // tant que l'article n'était pas traité — l'utilisateur était renvoyé de
  // force vers l'article à chaque tentative. La redirection instantanée
  // voulue par le parcours "on-demand" reste gérée directement dans
  // runCycle() ci-dessous (déclenchée UNIQUEMENT par l'action de LANCER un
  // cycle, jamais par une simple visite de /agent). Cet effet se contente
  // désormais d'informer sans jamais naviguer de force.
  useEffect(() => {
    if (!isPaused) {
      pendingSinceRef.current = null
      return
    }
    if (pendingSinceRef.current === null) pendingSinceRef.current = Date.now()

    // Cas limite : PAUSED confirmé mais aucun article résolu après un délai
    // raisonnable (ex. redémarrage backend pile à ce moment) — on informe
    // plutôt que de laisser un état incohérent silencieux.
    if (!pendingArticle && Date.now() - (pendingSinceRef.current ?? Date.now()) > PENDING_ARTICLE_RESOLUTION_TIMEOUT_MS) {
      show("Article prêt mais introuvable automatiquement — consulte l'onglet Articles.", 'warning')
      localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
      setCurrentCycleId(null)
      pendingSinceRef.current = null
    }
  }, [isPaused, pendingArticle, show])

  useEffect(() => {
    if (isFailed) {
      const errs = cycle?.errors ?? []
      show(errs.length ? `Cycle échoué : ${errs[0]}` : 'Cycle échoué', 'error')
      localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
    }
  }, [isFailed]) // eslint-disable-line react-hooks/exhaustive-deps

  // crypto.randomUUID() exige un contexte sécurisé (HTTPS/localhost) — le
  // site tourne encore en HTTP simple (pas de domaine/Certbot à ce jour),
  // donc indisponible dans le vrai navigateur de production. Repli manuel,
  // suffisant pour un simple identifiant de corrélation côté client.
  function _generateCycleId(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = (Math.random() * 16) | 0
      const v = c === 'x' ? r : (r & 0x3) | 0x8
      return v.toString(16)
    })
  }

  function _isLostSessionError(e: unknown): boolean {
    const msg = e instanceof Error ? e.message : String(e)
    return msg.includes('404') || msg.includes('409') || msg.toLowerCase().includes('non trouvé')
  }

  // Bug trouvé en testant l'annulation d'un cycle réellement en cours (pas
  // déjà en pause) : la requête bloquante POST /run se termine alors avec
  // une 409 "Cycle annulé" — _isLostSessionError() la classait à tort comme
  // une session perdue, affichant un toast d'erreur contradictoire en plus
  // de celui, correct, déjà émis par cancelCycle(). Un clic volontaire sur
  // "Annuler" ne doit jamais produire de message d'erreur.
  function _isUserCancelled(e: unknown): boolean {
    const msg = e instanceof Error ? e.message : String(e)
    return msg.toLowerCase().includes('annulé')
  }

  function _friendlyError(e: unknown): string {
    const msg = e instanceof Error ? e.message : String(e)
    if (_isLostSessionError(e)) {
      return "Ce cycle n'est plus actif en mémoire (le backend a probablement redémarré). Utilise la page Articles pour approuver/rejeter directement l'article en attente."
    }
    return msg
  }

  // Le POST /api/agent/run est désormais bloquant côté backend : la réponse
  // n'arrive qu'une fois le graphe LangGraph à la pause HITL (mode semi) ou
  // terminé (mode auto). cycle_id généré ici, AVANT l'appel, pour que le
  // bouton "Annuler" reste fonctionnel pendant l'attente (appel HTTP séparé
  // sur /cancel/{cycleId}) sans dépendre de cette réponse encore en vol.
  const { mutate: runCycle, loading: running } = useMutation(async () => {
    const newCycleId = _generateCycleId()
    redirectedForCycleRef.current = null
    pendingSinceRef.current = null
    setCurrentCycleId(newCycleId)
    localStorage.setItem(CYCLE_ID_STORAGE_KEY, newCycleId)
    try {
      const result = await agentApi.run(mode, newCycleId)
      if (result.status === 'PAUSED' && result.article_id) {
        redirectedForCycleRef.current = newCycleId
        localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
        router.push(`/articles/${result.article_id}`)
        return
      }
      if (result.status === 'PAUSED') {
        show("Article prêt mais introuvable automatiquement — consulte l'onglet Articles.", 'warning')
      } else if (result.status === 'COMPLETED') {
        show(`Cycle terminé — ${result.published_count ?? 0} article(s) publié(s)`, 'success')
      }
      localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
      setCurrentCycleId(null)
    } catch (e) {
      if (!_isUserCancelled(e)) {
        show(_friendlyError(e), 'error')
      }
      localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
      setCurrentCycleId(null)
    }
  })

  const { mutate: cancelCycle, loading: cancelling } = useMutation(async () => {
    if (!currentCycleId || hitlActionInFlight.current) return
    hitlActionInFlight.current = true
    try {
      await agentApi.cancel(currentCycleId)
      show('Cycle annulé', 'warning')
      localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
      setCurrentCycleId(null)
      await refetchStatus()
    } catch (e) {
      show(_friendlyError(e), 'error')
    } finally {
      hitlActionInFlight.current = false
    }
  })

  // Root cause du clignotement au clic sur "Retour" (rapport d'incident) :
  // isBusy incluait `isPaused && !pendingArticle`, vrai de façon transitoire
  // à CHAQUE montage de /agent tant qu'un cycle réel reste en pause en base
  // — le temps que fetchPendingArticle() résolve (un aller-retour réseau),
  // l'overlay plein écran s'affichait avant de disparaître dès que
  // l'article était trouvé. Reproductible à volonté avec un cycle PAUSED
  // ambiant (ex. un article laissé en attente). Aucun état global mal
  // nettoyé, aucun effet orphelin — useInterval() nettoie déjà correctement
  // via clearInterval au démontage (vérifié) ; la vraie cause était cette
  // condition composite. L'overlay plein écran ne doit représenter QUE le
  // travail actif de CETTE session (lancement en cours ou cycle RUNNING) —
  // jamais un cycle PAUSED ambiant découvert passivement en arrivant sur la
  // page, qui n'est plus qu'une information passive (bannière ci-dessous).
  const isBusy = running || isRunning
  // Distinct de isBusy : bloque le lancement d'un nouveau cycle tant qu'un
  // autre (RUNNING ou PAUSED, y compris ambiant) est déjà actif, sans pour
  // autant déclencher l'overlay plein écran pour ce dernier cas.
  const isCycleActive = isBusy || isPaused

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-heading font-bold text-2xl text-anthracite">Agent KORA</h1>
        <p className="font-heading text-[13px] text-gray-dk mt-0.5">
          Contrôle du cycle IA · Validation humaine intégrée
        </p>
      </div>

      {/* Contrôles */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
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
                disabled={isCycleActive}
                onClick={() => runCycle(undefined as unknown as void)}
                className="flex-1"
              >
                {isCycleActive ? 'Cycle en cours…' : 'Lancer le cycle'}
              </Button>
              {mode === 'semi' && !running && !isCycleActive && (
                <Badge variant="orange">HITL</Badge>
              )}
            </div>
          </div>
        </Card>

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
            </div>
          )}
        </Card>
      </div>

      {/* Bannière passive — jamais de navigation forcée : contrairement à la
          redirection instantanée de runCycle() (déclenchée par l'action de
          l'utilisateur), ceci ne fait qu'informer si un cycle d'une session
          précédente est toujours en pause en arrivant sur cette page. */}
      {!isBusy && isPaused && pendingArticle && (
        <Card className="mb-6 border-orange/30 bg-orange/5">
          <div className="flex items-center justify-between gap-4">
            <p className="font-heading text-[13px] text-anthracite">
              Un article rédigé lors d'un cycle précédent attend toujours votre validation.
            </p>
            <Button href={`/articles/${pendingArticle.id}`} variant="outline" size="sm">
              Lire l'article →
            </Button>
          </div>
        </Card>
      )}

      {/* Écran de transition plein écran — remplace la console de logs.
          Reste affiché tant qu'on n'a pas pu rediriger vers l'article concret,
          pour ne jamais laisser entrevoir un état intermédiaire incomplet. */}
      {isBusy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-cream/95 backdrop-blur-sm">
          <div className="flex flex-col items-center text-center px-6 max-w-md">
            <Spinner size="lg" />
            <h2 className="font-heading font-semibold text-[16px] text-anthracite mt-6 mb-2">
              {isRunning
                ? 'KORA explore les sources et rédige votre prochain article…'
                : "Article rédigé — préparation de la page de validation…"}
            </h2>
            <p className="font-heading text-[13px] text-gray-dk mb-6">
              Vous serez redirigé automatiquement dès que l'article sera prêt à être relu.
            </p>
            <Button
              variant="ghost"
              size="sm"
              loading={cancelling}
              onClick={() => cancelCycle(undefined as unknown as void)}
            >
              Annuler le cycle
            </Button>
          </div>
        </div>
      )}
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
