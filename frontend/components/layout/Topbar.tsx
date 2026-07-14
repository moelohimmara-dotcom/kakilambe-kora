'use client'

import Link from 'next/link'
import { useSidebar } from '@/lib/contexts/SidebarContext'
import { useHeaderVisibility } from '@/lib/contexts/HeaderVisibilityContext'
import { Badge } from '@/components/ui/Badge'

interface TopbarProps {
  title?: string
  children?: React.ReactNode
}

export function Topbar({ title, children }: TopbarProps) {
  const { toggle, openMobile, collapsed } = useSidebar()
  const { hidden, show } = useHeaderVisibility()

  return (
    <>
      <header
        className={
          `fixed top-0 right-0 z-20 h-16 bg-white/90 backdrop-blur-sm border-b border-gray-light ` +
          `flex items-center px-5 gap-4 transition-[left,transform] duration-300 ease-in-out left-0 ` +
          `${collapsed ? 'md:left-16' : 'md:left-60'} ` +
          `${hidden ? '-translate-y-full' : 'translate-y-0'}`
        }
        role="banner"
      >
      {/* Hamburger — tablette */}
      <button
        onClick={toggle}
        className="hidden md:flex lg:hidden items-center justify-center w-9 h-9 rounded-md text-gray-dk hover:bg-gray-pale transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
        aria-label="Réduire le menu"
      >
        <HamburgerIcon />
      </button>

      {/* Hamburger — mobile */}
      <button
        onClick={openMobile}
        className="md:hidden flex items-center justify-center w-9 h-9 rounded-md text-gray-dk hover:bg-gray-pale transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
        aria-label="Ouvrir le menu"
        aria-expanded={false}
        aria-controls="mobile-sidebar"
      >
        <HamburgerIcon />
      </button>

      {/* Logo mobile — cliquable, ramène au dashboard */}
      <Link
        href="/dashboard"
        className="md:hidden font-heading font-extrabold text-lg text-anthracite focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange rounded-sm"
        aria-label="Retour au tableau de bord"
      >
        <span className="text-orange">/</span>KORA
      </Link>

      {/* Titre de page */}
      {title && (
        <h1 className="hidden md:block font-heading text-[15px] font-semibold text-anthracite flex-1">
          {title}
        </h1>
      )}

      <div className="flex-1" />

      {/* Slot actions droite */}
      {children}

      {/* Status KORA */}
      <Badge variant="sage" dot pulse className="hidden sm:inline-flex">
        KORA actif
      </Badge>
      </header>

      {/* Affordance de réouverture — le header rétracté masque totalement le
          badge de statut ; sans ce bouton, rien ne permettrait de le
          reforcer sans dépendre d'un geste de scroll précis. Toujours
          présent dans le DOM (transition d'opacité/translation fluide,
          jamais un montage/démontage brutal), inerte au clic quand le
          header est déjà déplié (opacity-0 pointer-events-none). */}
      <button
        onClick={show}
        aria-label="Afficher la barre de statut"
        title="Afficher la barre de statut"
        className={
          `fixed top-1.5 right-5 z-30 flex items-center justify-center w-8 h-6 rounded-full ` +
          `bg-white/90 backdrop-blur-sm border border-gray-light shadow-card text-gray-dk ` +
          `transition-all duration-300 ease-in-out hover:text-orange ` +
          `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
          `${hidden ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4 pointer-events-none'}`
        }
      >
        <ChevronDownIcon />
      </button>
    </>
  )
}

function HamburgerIcon() {
  return (
    <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true">
      <path d="M1 1h16M1 7h16M1 13h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

function ChevronDownIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M3 5.5L7 9.5L11 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
