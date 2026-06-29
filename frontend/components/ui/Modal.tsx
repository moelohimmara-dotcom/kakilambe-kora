'use client'

import { useEffect, useRef, ReactNode } from 'react'
import { Button } from './Button'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}

const sizes = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

export function Modal({ open, onClose, title, children, footer, size = 'md' }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    if (open) {
      el.showModal()
    } else {
      el.close()
    }
  }, [open])

  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    const onCancel = (e: Event) => { e.preventDefault(); onClose() }
    el.addEventListener('cancel', onCancel)
    return () => el.removeEventListener('cancel', onCancel)
  }, [onClose])

  if (!open) return null

  return (
    <dialog
      ref={dialogRef}
      className={
        `${sizes[size]} w-full rounded-xl border border-gray-light bg-white shadow-lg ` +
        `backdrop:bg-anthracite/40 backdrop:backdrop-blur-sm ` +
        `open:animate-[fadeIn_180ms_ease-out] p-0`
      }
      onClick={e => { if (e.target === dialogRef.current) onClose() }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-light">
        <h2 className="font-heading text-base font-semibold text-anthracite">{title}</h2>
        <button
          onClick={onClose}
          className="w-8 h-8 flex items-center justify-center rounded-md text-gray-dk hover:bg-gray-pale transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
          aria-label="Fermer"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="px-6 py-5">{children}</div>

      {/* Footer */}
      {footer && (
        <div className="px-6 py-4 border-t border-gray-pale flex items-center justify-end gap-3">
          {footer}
        </div>
      )}
    </dialog>
  )
}
