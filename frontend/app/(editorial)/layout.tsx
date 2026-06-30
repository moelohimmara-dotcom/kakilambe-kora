import { SidebarProvider } from '@/lib/contexts/SidebarContext'
import { ToastProvider } from '@/lib/contexts/ToastContext'
import { AppShell } from '@/components/layout/AppShell'

export const dynamic = 'force-dynamic'

export default function EditorialLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <SidebarProvider>
        <AppShell>{children}</AppShell>
      </SidebarProvider>
    </ToastProvider>
  )
}
