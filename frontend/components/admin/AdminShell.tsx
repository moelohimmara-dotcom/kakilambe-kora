'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { ReactNode } from 'react'

interface AdminNavItem {
  href: string
  label: string
  icon: ReactNode
}

const NAV_ITEMS: AdminNavItem[] = [
  {
    href: '/system',
    label: 'Dashboard',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
        <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
        <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
        <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
      </svg>
    ),
  },
  {
    href: '/system/logs',
    label: 'Logs terminal',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="1" y="2" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M4 6l2 2-2 2M8 10h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    href: '/system/providers',
    label: 'Fournisseurs LLM',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M8 4v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: '/system/cycles',
    label: 'Cycles',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M2 8a6 6 0 016-6 6 6 0 014.24 1.76M14 8a6 6 0 01-6 6 6 6 0 01-4.24-1.76" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        <path d="M12 3l2.24 2.76L12 6M4 10l-2.24 2.76L4 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    href: '/system/connections',
    label: 'Connexions',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="3" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/>
        <circle cx="13" cy="3" r="2" stroke="currentColor" strokeWidth="1.5"/>
        <circle cx="13" cy="13" r="2" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M5 8h3l2-5M5 8h3l2 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
]

const SYS_BG       = '#0c0c0b'
const SYS_SURFACE  = '#141413'
const SYS_BORDER   = '#2a2a28'
const SYS_TEXT     = '#d4d3ce'
const SYS_MUTED    = '#5a5956'
const SYS_RED      = '#e53e3e'
const SYS_RED_DIM  = 'rgba(229,62,62,.15)'

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname  = usePathname()
  const router    = useRouter()
  const [loggingOut, setLoggingOut] = useState(false)

  async function logout() {
    setLoggingOut(true)
    await fetch('/api/admin/login', { method: 'DELETE' })
    router.replace('/system/login')
  }

  return (
    <div className="min-h-screen flex" style={{ background: SYS_BG, color: SYS_TEXT }}>

      {/* Sidebar */}
      <aside
        className="fixed top-0 left-0 h-screen w-56 flex flex-col z-30 border-r"
        style={{ background: SYS_SURFACE, borderColor: SYS_BORDER }}
        aria-label="Navigation admin"
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 h-14 border-b shrink-0" style={{ borderColor: SYS_BORDER }}>
          <div className="w-6 h-6 rounded flex items-center justify-center shrink-0" style={{ background: SYS_RED }}>
            <span className="font-mono text-white font-bold text-[9px]">SYS</span>
          </div>
          <span className="font-mono font-bold text-[13px] text-white">/KORA System</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto" aria-label="Menu système">
          <ul className="space-y-0.5 px-3" role="list">
            {NAV_ITEMS.map(item => {
              const isActive = item.href === '/system'
                ? pathname === '/system'
                : pathname.startsWith(item.href)
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="flex items-center gap-3 px-3 py-2 rounded-md font-mono text-[12px] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500"
                    style={{
                      color: isActive ? '#fff' : SYS_MUTED,
                      background: isActive ? SYS_RED_DIM : 'transparent',
                      borderLeft: isActive ? `2px solid ${SYS_RED}` : '2px solid transparent',
                    }}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="shrink-0" style={{ color: isActive ? SYS_RED : SYS_MUTED }}>
                      {item.icon}
                    </span>
                    {item.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Footer */}
        <div className="p-3 border-t" style={{ borderColor: SYS_BORDER }}>
          <button
            onClick={logout}
            disabled={loggingOut}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-md font-mono text-[12px] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500 disabled:opacity-40"
            style={{ color: SYS_MUTED }}
            onMouseEnter={e => (e.currentTarget.style.color = SYS_RED)}
            onMouseLeave={e => (e.currentTarget.style.color = SYS_MUTED)}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M9 1h3a1 1 0 011 1v10a1 1 0 01-1 1H9M6 10l3-3-3-3M9 7H2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {loggingOut ? 'Déconnexion…' : 'Se déconnecter'}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="ml-56 flex-1 flex flex-col min-h-screen">
        {/* Header bande rouge */}
        <header
          className="sticky top-0 z-20 h-14 flex items-center px-6 gap-4 border-b"
          style={{ background: SYS_SURFACE, borderColor: SYS_BORDER, borderTop: `3px solid ${SYS_RED}` }}
          role="banner"
        >
          <div
            className="font-mono text-[11px] uppercase tracking-widest font-bold"
            style={{ color: SYS_RED }}
          >
            ⬛ SYSTEM ACCESS
          </div>
          <div className="flex-1" />
          <div
            className="font-mono text-[10px] px-2 py-1 rounded border"
            style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
          >
            admin · kakilambe.com
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 md:p-8 overflow-auto animate-[fadeIn_180ms_ease-out]">
          {children}
        </main>
      </div>
    </div>
  )
}
