'use client'

import { useToast, AutoDismissToast, ToastVariant } from '@/lib/contexts/ToastContext'

const icons: Record<ToastVariant, string> = {
  default: '●',
  success: '✓',
  error:   '✕',
  warning: '!',
  achievement: '🏆',
}

const variantCls: Record<ToastVariant, string> = {
  default: 'bg-anthracite text-white',
  success: 'bg-sage text-white',
  error:   'bg-danger text-white',
  warning: 'bg-warning text-white',
  // Gamification — ton pastel discret, bordure pointillée, distinct des
  // variantes fonctionnelles solides ci-dessus. Accent lavande réservé à la
  // gamification, jamais réutilisé ailleurs.
  achievement: 'bg-lavender-pale text-anthracite border border-dashed border-lavender',
}

export function ToastContainer() {
  const { toasts, dismiss } = useToast()

  if (toasts.length === 0) return null

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      aria-label="Notifications"
      className="fixed bottom-20 right-6 z-[9999] flex flex-col gap-2 lg:bottom-6"
    >
      {toasts.map(t => (
        <div
          key={t.id}
          role="alert"
          className={
            `flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg max-w-xs ` +
            `font-heading text-[13px] font-medium animate-[slideUp_200ms_ease-out] ` +
            `${variantCls[t.variant]}`
          }
        >
          <span className="text-sm font-bold" aria-hidden="true">{icons[t.variant]}</span>
          <span className="flex-1">{t.message}</span>
          <button
            onClick={() => dismiss(t.id)}
            className="opacity-60 hover:opacity-100 transition-opacity"
            aria-label="Fermer"
          >
            ×
          </button>
          <AutoDismissToast id={t.id} />
        </div>
      ))}
    </div>
  )
}
