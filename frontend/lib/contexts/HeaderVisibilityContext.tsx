'use client'

import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react'

interface HeaderVisibilityContextValue {
  hidden: boolean
  show: () => void
}

const HeaderVisibilityContext = createContext<HeaderVisibilityContextValue | null>(null)

// Seuils : DOWN_THRESHOLD évite que le header se rétracte sur un micro-scroll
// juste après le haut de page (pénible sur trackpad/molette imprécise) ;
// TOP_THRESHOLD force le redéploiement dès qu'on est proche du sommet, même
// si le dernier mouvement était vers le bas (attendu : revenir en haut de
// page doit toujours redéployer la barre).
const DOWN_THRESHOLD = 24
const TOP_THRESHOLD = 48

export function HeaderVisibilityProvider({ children }: { children: ReactNode }) {
  const [hidden, setHidden] = useState(false)
  const lastY = useRef(0)

  useEffect(() => {
    lastY.current = window.scrollY

    let ticking = false
    function onScroll() {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        const y = window.scrollY
        const delta = y - lastY.current

        if (y <= TOP_THRESHOLD) {
          setHidden(false)
        } else if (delta > DOWN_THRESHOLD) {
          setHidden(true)
          lastY.current = y
        } else if (delta < -DOWN_THRESHOLD) {
          setHidden(false)
          lastY.current = y
        }
        ticking = false
      })
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const show = useCallback(() => setHidden(false), [])

  return (
    <HeaderVisibilityContext.Provider value={{ hidden, show }}>
      {children}
    </HeaderVisibilityContext.Provider>
  )
}

export function useHeaderVisibility() {
  const ctx = useContext(HeaderVisibilityContext)
  if (!ctx) throw new Error('useHeaderVisibility must be used inside HeaderVisibilityProvider')
  return ctx
}
