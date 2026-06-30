'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useSidebar } from '@/lib/contexts/SidebarContext'
import { Badge } from '@/components/ui/Badge'

interface NavItem {
  href: string
  label: string
  icon: (active: boolean) => React.ReactNode
  badge?: string
}

const navItems: NavItem[] = [
  {
    href: '/dashboard',
    label: 'Tableau de bord',
    icon: (active) => <IconDashboard active={active} />,
  },
  {
    href: '/articles',
    label: 'Articles',
    icon: (active) => <IconArticles active={active} />,
  },
  {
    href: '/chat',
    label: 'Chat IA',
    icon: (active) => <IconChat active={active} />,
  },
  {
    href: '/sources',
    label: 'Sources RSS',
    icon: (active) => <IconSources active={active} />,
  },
  {
    href: '/history',
    label: 'Historique',
    icon: (active) => <IconHistory active={active} />,
  },
  {
    href: '/agent',
    label: 'Agent KORA',
    icon: (active) => <IconAgent active={active} />,
  },
]

const bottomItems: NavItem[] = [
  {
    href: '/settings',
    label: 'Paramètres',
    icon: (active) => <IconSettings active={active} />,
  },
]

export function Sidebar() {
  const pathname = usePathname()
  const { collapsed } = useSidebar()

  return (
    <>
      {/* Desktop / Tablet sidebar */}
      <aside
        className={
          `hidden md:flex flex-col fixed top-0 left-0 h-screen z-30 ` +
          `bg-white border-r border-gray-light transition-[width] duration-200 ` +
          `${collapsed ? 'w-16' : 'w-60'}`
        }
        aria-label="Navigation principale"
      >
        {/* Logo */}
        <div className={`flex items-center h-16 px-4 border-b border-gray-light shrink-0 ${collapsed ? 'justify-center' : ''}`}>
          {collapsed ? (
            <span className="text-orange font-heading font-extrabold text-xl">/K</span>
          ) : (
            <span className="font-heading font-extrabold text-lg text-anthracite">
              <span className="text-orange">/</span>KORA
            </span>
          )}
        </div>

        {/* Nav principale */}
        <nav className="flex-1 py-4 overflow-y-auto overflow-x-hidden" aria-label="Menu éditorial">
          <ul className="space-y-0.5 px-2" role="list">
            {navItems.map(item => (
              <NavLink key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
            ))}
          </ul>
        </nav>

        {/* Nav bas */}
        <div className="py-3 border-t border-gray-light">
          <ul className="space-y-0.5 px-2" role="list">
            {bottomItems.map(item => (
              <NavLink key={item.href} item={item} pathname={pathname} collapsed={collapsed} />
            ))}
            {/* Avatar utilisateur */}
            <li>
              <div className={`flex items-center gap-3 px-3 py-2.5 rounded-md ${collapsed ? 'justify-center' : ''}`}>
                <div className="w-7 h-7 rounded-full bg-orange/20 flex items-center justify-center shrink-0">
                  <span className="font-heading text-[11px] font-bold text-orange">K</span>
                </div>
                {!collapsed && (
                  <div className="min-w-0">
                    <p className="font-heading text-[12px] font-semibold text-anthracite truncate">Éditeur</p>
                    <p className="font-heading text-[11px] text-gray-dk truncate">kakilambe.com</p>
                  </div>
                )}
              </div>
            </li>
          </ul>
        </div>
      </aside>
    </>
  )
}

function NavLink({ item, pathname, collapsed }: { item: NavItem; pathname: string; collapsed: boolean }) {
  const isActive = pathname === item.href || pathname.startsWith(item.href + '/')

  return (
    <li>
      <Link
        href={item.href}
        className={
          `flex items-center gap-3 px-3 py-2.5 rounded-md ` +
          `font-heading text-[13px] font-medium transition-colors duration-100 ` +
          `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
          `${collapsed ? 'justify-center' : ''} ` +
          `${isActive
            ? 'bg-orange/10 text-orange'
            : 'text-gray-dk hover:bg-gray-pale hover:text-anthracite'
          }`
        }
        aria-current={isActive ? 'page' : undefined}
        aria-label={collapsed ? item.label : undefined}
        title={collapsed ? item.label : undefined}
      >
        <span className="shrink-0 w-[18px] h-[18px] flex items-center justify-center">
          {item.icon(isActive)}
        </span>
        {!collapsed && (
          <>
            <span className="flex-1 min-w-0 truncate">{item.label}</span>
            {item.badge && <Badge variant="orange" className="shrink-0">{item.badge}</Badge>}
          </>
        )}
      </Link>
    </li>
  )
}

/* ── SVG Icons ─────────────────────────────────────────────────────── */

function IconDashboard({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5} fill={active ? 'currentColor' : 'none'} fillOpacity={active ? 0.15 : 0}/>
      <rect x="10" y="1" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <rect x="1" y="10" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <rect x="10" y="10" width="7" height="7" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
    </svg>
  )
}

function IconArticles({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <rect x="2" y="2" width="14" height="14" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <path d="M5 6h8M5 9h8M5 12h5" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round"/>
    </svg>
  )
}

function IconChat({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <path d="M2 3a1 1 0 011-1h12a1 1 0 011 1v9a1 1 0 01-1 1H5l-3 3V3z" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinejoin="round" fill={active ? 'currentColor' : 'none'} fillOpacity={active ? 0.1 : 0}/>
    </svg>
  )
}

function IconSources({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <path d="M9 2a9.5 9.5 0 010 14M9 2a9.5 9.5 0 000 14M2 9h14" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
    </svg>
  )
}

function IconHistory({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <path d="M9 5v4l3 2" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function IconAgent({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <rect x="4" y="6" width="10" height="9" rx="2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <path d="M7 6V4a2 2 0 014 0v2" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <circle cx="7" cy="10.5" r="1" fill="currentColor"/>
      <circle cx="11" cy="10.5" r="1" fill="currentColor"/>
      <path d="M7 13h4" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round"/>
    </svg>
  )
}

function IconSettings({ active }: { active: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth={active ? 2 : 1.5}/>
      <path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.1 3.1l1.4 1.4M13.5 13.5l1.4 1.4M3.1 14.9l1.4-1.4M13.5 4.5l1.4-1.4" stroke="currentColor" strokeWidth={active ? 2 : 1.5} strokeLinecap="round"/>
    </svg>
  )
}
