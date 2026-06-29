import { ToastProvider } from '@/lib/contexts/ToastContext'
import { ToastContainer } from '@/components/ui/Toast'

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      {children}
      <ToastContainer />
    </ToastProvider>
  )
}
