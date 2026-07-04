'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useRef } from 'react'
import { useSidebar } from '@/lib/contexts/SidebarContext'
import { Badge } from '@/components/ui/Badge'

const navItems = [
  { href: '/dashboard', label: 'Tableau de bord' },
  { href: '/articles',  label: 'Articles' },
  { href: '/sources',   label: 'Sources RSS' },
  { href: '/history',   label: 'Historique' },
  { href: '/agent',     label: 'Agent KORA' },
  { href: '/settings',  label: 'Paramètres' },
]

export function MobileSidebar() {
  const { mobileOpen, closeMobile } = useSidebar()
  const pathname = usePathname()
  const drawerRef = useRef<HTMLElement>(null)

  // Ferme au changement de page
  useEffect(() => { closeMobile() }, [pathname, closeMobile])

  // Focus trap + ESC
  useEffect(() => {
    if (!mobileOpen) return
    document.body.style.overflow = 'hidden'

    // Déplace le focus vers le premier élément focusable du drawer
    const focusable = drawerRef.current?.querySelectorAll<HTMLElement>(
      'a, button, input, [tabindex]:not([tabindex="-1"])'
    )
    focusable?.[0]?.focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { closeMobile(); return }
      if (e.key !== 'Tab' || !drawerRef.current) return
      const els = Array.from(drawerRef.current.querySelectorAll<HTMLElement>(
        'a, button, input, [tabindex]:not([tabindex="-1"])'
      ))
      if (els.length === 0) return
      const first = els[0], last = els[els.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [mobileOpen, closeMobile])

  if (!mobileOpen) return null

  return (
    <div className="md:hidden fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-anthracite/40 backdrop-blur-sm animate-[fadeIn_180ms_ease-out]"
        onClick={closeMobile}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        id="mobile-sidebar"
        ref={drawerRef}
        className="absolute top-0 left-0 h-full w-72 bg-white shadow-lg flex flex-col animate-[slideUp_200ms_ease-out]"
        role="dialog"
        aria-modal="true"
        aria-label="Menu principal"
      >
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-5 border-b border-gray-light">
          <span className="font-heading font-extrabold text-lg text-anthracite">
            <span className="text-orange">/</span>KORA
          </span>
          <button
            onClick={closeMobile}
            className="w-9 h-9 flex items-center justify-center rounded-md text-gray-dk hover:bg-gray-pale focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
            aria-label="Fermer le menu"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto" aria-label="Menu éditorial">
          <ul className="space-y-0.5 px-3" role="list">
            {navItems.map(item => {
              const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={
                      `flex items-center px-4 py-3 rounded-md ` +
                      `font-heading text-[14px] font-medium transition-colors ` +
                      `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
                      `${isActive
                        ? 'bg-orange/10 text-orange'
                        : 'text-gray-dk hover:bg-gray-pale hover:text-anthracite'
                      }`
                    }
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {item.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-light">
          <Badge variant="sage" dot pulse>KORA actif</Badge>
        </div>
      </aside>
    </div>
  )
}
