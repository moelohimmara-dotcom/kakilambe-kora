'use client'

import { useSidebar } from '@/lib/contexts/SidebarContext'
import { Badge } from '@/components/ui/Badge'

interface TopbarProps {
  title?: string
  children?: React.ReactNode
}

export function Topbar({ title, children }: TopbarProps) {
  const { toggle, openMobile, collapsed } = useSidebar()

  return (
    <header
      className={
        `fixed top-0 right-0 z-20 h-16 bg-white/90 backdrop-blur-sm border-b border-gray-light ` +
        `flex items-center px-5 gap-4 transition-[left] duration-200 left-0 ` +
        `${collapsed ? 'md:left-16' : 'md:left-60'}`
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
        aria-expanded="false"
      >
        <HamburgerIcon />
      </button>

      {/* Logo mobile */}
      <span className="md:hidden font-heading font-extrabold text-lg text-anthracite">
        <span className="text-orange">/</span>KORA
      </span>

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
  )
}

function HamburgerIcon() {
  return (
    <svg width="18" height="14" viewBox="0 0 18 14" fill="none" aria-hidden="true">
      <path d="M1 1h16M1 7h16M1 13h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}
