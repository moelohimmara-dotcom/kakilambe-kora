import { SidebarProvider } from '@/lib/contexts/SidebarContext'
import { ToastProvider } from '@/lib/contexts/ToastContext'
import { AppShell } from '@/components/layout/AppShell'
import { ThemeProvider } from '@/components/providers/ThemeProvider'
import { AccountThemeSync } from '@/components/providers/AccountThemeSync'

export const dynamic = 'force-dynamic'

export default function EditorialLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AccountThemeSync />
      <ToastProvider>
        <SidebarProvider>
          <AppShell>{children}</AppShell>
        </SidebarProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}
