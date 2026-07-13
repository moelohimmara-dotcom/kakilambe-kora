'use client'

import { useState, useRef, useEffect } from 'react'
import { Spinner } from './Spinner'
import { Button } from './Button'

// Extrait de AgentScreen.tsx — écran de transition plein écran affiché
// pendant le lancement d'un cycle, réutilisable par /dashboard (CDC §3.4.1 :
// le raccourci du Dashboard doit déclencher exactement le même flux que
// /agent, pas une implémentation divergente).

const _LOADING_MESSAGES = [
  "KORA scanne les dernières actus de Guinée pour vous…",
  "Extraction des meilleures sources en cours, un instant…",
  "Sélection de l'article le plus pertinent du moment…",
  "KORA affine la plume journalistique de votre article…",
  "Structuration en pyramide inversée, façon BBC Afrique…",
  "Génération de l'image d'illustration…",
  "Presque prêt ! Dernière vérification stylistique…",
]

export function CycleLaunchOverlay({
  isBusy, isRunning, cancelling, onCancel,
}: {
  isBusy: boolean
  isRunning: boolean
  cancelling: boolean
  onCancel: () => void
}) {
  // Rotation des micro-messages d'attente — fade-out (250ms) puis changement
  // de message puis fade-in, toutes les ~1.3s tant que l'écran de transition
  // est affiché. Se réinitialise proprement dès la fin du cycle (isBusy
  // redevient false) pour repartir du premier message au prochain lancement.
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0)
  const [loadingMsgFading, setLoadingMsgFading] = useState(false)
  const loadingMsgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!isBusy) {
      setLoadingMsgIndex(0)
      setLoadingMsgFading(false)
      return
    }
    const interval = setInterval(() => {
      setLoadingMsgFading(true)
      loadingMsgTimerRef.current = setTimeout(() => {
        setLoadingMsgIndex(i => (i + 1) % _LOADING_MESSAGES.length)
        setLoadingMsgFading(false)
      }, 250)
    }, 1300)
    return () => {
      clearInterval(interval)
      if (loadingMsgTimerRef.current) clearTimeout(loadingMsgTimerRef.current)
    }
  }, [isBusy])

  if (!isBusy) return null

  return (
    <div className="page-enter fixed inset-0 z-50 flex items-center justify-center bg-cream/95 backdrop-blur-sm">
      <div className="flex flex-col items-center text-center px-6 max-w-md">
        <Spinner size="lg" />
        <h2
          className={`font-heading font-semibold text-[16px] text-anthracite mt-6 mb-2 transition-opacity duration-300 ${isRunning && loadingMsgFading ? 'opacity-0' : 'opacity-100'}`}
        >
          {isRunning
            ? _LOADING_MESSAGES[loadingMsgIndex]
            : "Article rédigé — préparation de la page de validation…"}
        </h2>
        <p className="font-heading text-[13px] text-gray-dk mb-6">
          Vous serez redirigé automatiquement dès que l'article sera prêt à être relu.
        </p>
        <Button variant="ghost" size="sm" loading={cancelling} onClick={onCancel}>
          Annuler le cycle
        </Button>
      </div>
    </div>
  )
}
