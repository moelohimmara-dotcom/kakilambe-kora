import { AdminShell } from '@/components/admin/AdminShell'
import { ReactNode } from 'react'

export const metadata = {
  title: 'KORA System',
  robots: { index: false, follow: false },
}

export default function SystemProtectedLayout({ children }: { children: ReactNode }) {
  return <AdminShell>{children}</AdminShell>
}
