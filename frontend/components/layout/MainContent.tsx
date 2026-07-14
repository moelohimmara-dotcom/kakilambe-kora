'use client'

import { ReactNode } from 'react'
import { useSidebar } from '@/lib/contexts/SidebarContext'
import { useHeaderVisibility } from '@/lib/contexts/HeaderVisibilityContext'

export function MainContent({ children }: { children: ReactNode }) {
  const { collapsed } = useSidebar()
  const { hidden } = useHeaderVisibility()

  return (
    <main
      className={
        // pt-16/pt-0 en phase avec la translation du Topbar (même durée/
        // easing) : le contenu remonte réellement dans l'espace libéré par
        // le header rétracté, plutôt que de laisser un vide "fantôme" de la
        // hauteur du header sous le point où il se serait trouvé.
        `${hidden ? 'pt-0' : 'pt-16'} pb-[62px] md:pb-0 transition-[margin,padding] duration-300 ease-in-out ` +
        `${collapsed ? 'md:ml-16' : 'md:ml-60'}`
      }
      id="main-content"
    >
      <div className="page-enter">{children}</div>
    </main>
  )
}
