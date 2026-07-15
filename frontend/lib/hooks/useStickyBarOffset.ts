'use client'

import { useHeaderVisibility } from '@/lib/contexts/HeaderVisibilityContext'

/**
 * Root cause (2026-07-15) : les barres d'action sticky (ex. ArticleEditorScreen)
 * utilisaient un décalage `top-16` figé, calibré pour un Topbar toujours
 * présent à 64px. Depuis que le Topbar se rétracte au scroll
 * (HeaderVisibilityContext), cet espace disparaît mais l'offset figé
 * restait — la barre se retrouvait décalée avec un vide au-dessus.
 *
 * Ce hook centralise la classe utilitaire correcte à appliquer à toute
 * barre sticky sous le Topbar, pour que le comportement reste identique
 * partout (Articles, Historique, etc.) sans dupliquer la logique.
 * Transition alignée sur celle du Topbar (300ms ease-in-out) pour un
 * accrochage synchronisé, sans saut.
 */
export function useStickyBarOffset() {
  const { hidden } = useHeaderVisibility()
  return {
    className: `sticky ${hidden ? 'top-0' : 'top-16'} z-10 transition-[top] duration-300 ease-in-out`,
  }
}
