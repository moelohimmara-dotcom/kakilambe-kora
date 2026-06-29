'use client'

import { ReactNode } from 'react'
import { useSidebar } from '@/lib/contexts/SidebarContext'

export function MainContent({ children }: { children: ReactNode }) {
  const { collapsed } = useSidebar()

  return (
    <main
      className={
        `pt-16 pb-[62px] md:pb-0 transition-[margin] duration-200 ` +
        `${collapsed ? 'md:ml-16' : 'md:ml-60'}`
      }
      id="main-content"
    >
      <div className="page-enter">{children}</div>
    </main>
  )
}
