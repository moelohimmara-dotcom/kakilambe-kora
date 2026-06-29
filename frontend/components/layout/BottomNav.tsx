'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface BottomNavItem {
  href: string
  label: string
  icon: (active: boolean) => React.ReactNode
}

const items: BottomNavItem[] = [
  {
    href: '/dashboard',
    label: 'Accueil',
    icon: (active) => (
      <svg width="22" height="22" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <rect x="1" y="1" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5} fill={active ? 'currentColor' : 'none'} fillOpacity="0.15"/>
        <rect x="10" y="1" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
        <rect x="1" y="10" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
        <rect x="10" y="10" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      </svg>
    ),
  },
  {
    href: '/articles',
    label: 'Articles',
    icon: (active) => (
      <svg width="22" height="22" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <rect x="2" y="2" width="14" height="14" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
        <path d="M5 6h8M5 9h8M5 12h5" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: '/chat',
    label: 'Chat',
    icon: (active) => (
      <svg width="22" height="22" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <path d="M2 3a1 1 0 011-1h12a1 1 0 011 1v9a1 1 0 01-1 1H5l-3 3V3z" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinejoin="round" fill={active ? 'currentColor' : 'none'} fillOpacity="0.1"/>
      </svg>
    ),
  },
  {
    href: '/agent',
    label: 'Agent',
    icon: (active) => (
      <svg width="22" height="22" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <rect x="4" y="6" width="10" height="9" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
        <path d="M7 6V4a2 2 0 014 0v2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
        <circle cx="7" cy="10.5" r="1" fill="currentColor"/>
        <circle cx="11" cy="10.5" r="1" fill="currentColor"/>
      </svg>
    ),
  },
  {
    href: '/settings',
    label: 'Réglages',
    icon: (active) => (
      <svg width="22" height="22" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
        <path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.1 3.1l1.4 1.4M13.5 13.5l1.4 1.4M3.1 14.9l1.4-1.4M13.5 4.5l1.4-1.4" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round"/>
      </svg>
    ),
  },
]

export function BottomNav() {
  const pathname = usePathname()

  return (
    <nav
      className="md:hidden fixed bottom-0 left-0 right-0 h-[62px] bg-white border-t border-gray-light z-30 flex items-center justify-around shadow-[0_-4px_16px_rgba(20,20,19,.08)]"
      aria-label="Navigation mobile"
    >
      {items.map(item => {
        const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
        return (
          <Link
            key={item.href}
            href={item.href}
            className={
              `flex flex-col items-center gap-1 px-3 py-1.5 rounded-md ` +
              `transition-colors duration-100 ` +
              `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
              `${isActive ? 'text-orange' : 'text-gray-dk hover:text-anthracite'}`
            }
            aria-current={isActive ? 'page' : undefined}
          >
            {item.icon(isActive)}
            <span className="font-heading text-[10px] font-semibold leading-none">
              {item.label}
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
