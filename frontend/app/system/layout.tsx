'use client'

import { usePathname } from 'next/navigation'
import { AdminShell } from '@/components/admin/AdminShell'
import { ReactNode } from 'react'

export default function SystemLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  // La page login ne doit pas être enveloppée dans l'AdminShell
  if (pathname === '/system/login') {
    return <>{children}</>
  }

  return <AdminShell>{children}</AdminShell>
}
