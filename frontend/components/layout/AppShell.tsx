import { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { BottomNav } from './BottomNav'
import { MobileSidebar } from './MobileSidebar'
import { MainContent } from './MainContent'
import { ToastContainer } from '@/components/ui/Toast'

interface AppShellProps {
  children: ReactNode
  title?: string
  topbarActions?: ReactNode
}

export function AppShell({ children, title, topbarActions }: AppShellProps) {
  return (
    <div className="min-h-screen bg-cream">
      <Sidebar />
      <MobileSidebar />
      <Topbar title={title}>{topbarActions}</Topbar>
      <BottomNav />
      <MainContent>{children}</MainContent>
      <ToastContainer />
    </div>
  )
}
