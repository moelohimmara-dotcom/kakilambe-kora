'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useToast } from '@/lib/contexts/ToastContext'
import { agentApi, articleApi } from '@/lib/api'
import { useAsync, useMutation, useInterval } from '@/lib/hooks'

// Extrait de AgentScreen.tsx (mécaniquement, sans réécriture) pour que
// /dashboard puisse déclencher le même vrai lancement de cycle que /agent
// (CDC §3.4.1 : "même flux, pas une implémentation dupliquée divergente"),
// au lieu de se contenter de naviguer vers /agent. Toute la logique et les
// commentaires historiques des bugs corrigés sont conservés à l'identique —
// seule la rotation des micro-messages d'attente reste dans
// CycleLaunchOverlay.tsx (détail d'affichage, pas de la logique de cycle).

export interface CycleState {
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

export function useLaunchCycle() {
  const router = useRouter()
  // Verrouillé en semi-automatique — spécification explicite : la validation
  // humaine (HITL) avant publication n'est plus contournable depuis l'IHM,
  // aucun état ni interrupteur ne permet de basculer en mode auto ici.
  const mode = 'semi' as const
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
    //
    // Bug corrigé : cette vérification se basait sur `cycle` (polling en
    // arrière-plan via setInterval), qui reste figé à sa dernière valeur
    // reçue tant qu'un onglet est en arrière-plan (les navigateurs throttlent
    // les timers des onglets inactifs) ou si une requête de polling échoue
    // silencieusement (useAsync ne réinitialise pas `data` sur erreur). Un
    // utilisateur revenant sur un onglet resté longtemps en arrière-plan
    // pouvait ainsi déclencher ce toast sur la base d'un statut PAUSED
    // obsolète alors que le cycle était réellement terminé depuis longtemps.
    // On revérifie donc l'état réel côté serveur juste avant d'agir, plutôt
    // que de faire confiance à la valeur potentiellement périmée du polling.
    const elapsed = Date.now() - (pendingSinceRef.current ?? Date.now())
    if (!pendingArticle && elapsed > PENDING_ARTICLE_RESOLUTION_TIMEOUT_MS) {
      const idToVerify = cycle?.cycle_id ?? currentCycleId ?? undefined
      agentApi.status(idToVerify).then((fresh) => {
        const freshStatus = (fresh as unknown as CycleState)?.status
        if (freshStatus === 'PAUSED') {
          show("Article prêt mais introuvable automatiquement — consulte l'onglet Articles.", 'warning')
        }
        // Sinon (COMPLETED/FAILED/CANCELLED) : le cycle s'est déjà résolu,
        // le polling normal va rattraper l'état réel — aucun toast à tort.
        localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
        setCurrentCycleId(null)
        refetchStatus()
      }).catch(() => {
        // Vérification impossible (réseau) : ne pas affirmer un problème
        // qu'on n'a pas pu confirmer.
        localStorage.removeItem(CYCLE_ID_STORAGE_KEY)
        setCurrentCycleId(null)
      })
      pendingSinceRef.current = null
    }
  }, [isPaused, pendingArticle, show, cycle?.cycle_id, currentCycleId, refetchStatus])

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
        // Ne devrait plus arriver en pratique : le backend ne marque PAUSED
        // que si LangGraph a réellement atteint l'interruption HITL (vérifié
        // via aget_state().next), ce qui garantit un article_id. Gardé en
        // filet de sécurité pour un cas limite non anticipé.
        show("Article prêt mais introuvable automatiquement — consulte l'onglet Articles.", 'warning')
      } else if (result.status === 'COMPLETED') {
        if (mode === 'semi' && (result.published_count ?? 0) === 0) {
          // Root cause corrigée côté backend : le graphe peut terminer
          // normalement (END) sans jamais produire d'article — 0 candidat
          // retenu par le sélecteur, ou échec de rédaction sur tous les
          // articles sélectionnés. Message honnête plutôt que le "0
          // article(s) publié(s)" trompeur (qui laissait croire à un succès
          // partiel alors que rien n'a été rédigé).
          show("Cycle terminé sans article produit — aucune actualité pertinente retenue cette fois. Réessayez plus tard.", 'warning')
        } else {
          show(`Cycle terminé — ${result.published_count ?? 0} article(s) publié(s)`, 'success')
        }
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
  // isBusy gate aussi le bouton "Lancer le cycle" — corrigé après clarification
  // explicite : un cycle PAUSED (article en attente de validation) ne doit
  // JAMAIS bloquer le lancement d'un nouveau cycle indépendant. La production
  // réelle fait déjà tourner plusieurs cycles en parallèle (plusieurs articles
  // "en attente" simultanés observés), le backend le supporte nativement
  // (chaque cycle a son propre cycle_id / thread_id LangGraph, aucun état
  // partagé entre eux) — seul un verrou UI-only avait été ajouté par erreur
  // ici lors d'une itération précédente, sans base réelle. Seul un cycle
  // RUNNING dans CETTE session (isBusy) bloque un nouveau lancement, pour
  // éviter un double appel concurrent depuis le même onglet.
  const isBusy = running || isRunning

  return {
    cycle, currentCycleId,
    isRunning, isPaused, isFailed, isBusy,
    pendingArticle,
    runCycle, running,
    cancelCycle, cancelling,
  }
}
