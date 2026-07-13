'use client'

import {
  createContext, useContext, useState, useCallback,
  useEffect, ReactNode,
} from 'react'

// 'achievement' = variante gamification (nouveau périmètre produit), style
// pastel discret distinct des variantes fonctionnelles existantes.
export type ToastVariant = 'default' | 'success' | 'error' | 'warning' | 'achievement'

interface Toast {
  id: string
  message: string
  variant: ToastVariant
}

interface ToastContextValue {
  toasts: Toast[]
  show: (message: string, variant?: ToastVariant) => void
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const show = useCallback((message: string, variant: ToastVariant = 'default') => {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev, { id, message, variant }])
  }, [])

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, show, dismiss }}>
      {children}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}

/* Auto-dismiss individual toasts */
export function AutoDismissToast({ id, duration = 4000 }: { id: string; duration?: number }) {
  const { dismiss } = useToast()
  useEffect(() => {
    const t = setTimeout(() => dismiss(id), duration)
    return () => clearTimeout(t)
  }, [id, duration, dismiss])
  return null
}
