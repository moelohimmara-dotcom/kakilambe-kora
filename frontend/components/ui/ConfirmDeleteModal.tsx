'use client'

import { useEffect, useRef } from 'react'
import { Spinner } from './Spinner'

interface ConfirmDeleteModalProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  loading?: boolean
  title?: string
  description?: string
}

export function ConfirmDeleteModal({
  open,
  onClose,
  onConfirm,
  loading = false,
  title = 'Supprimer cet article ?',
  description = "Cette action est irréversible. L'article sera définitivement effacé de la base de données.",
}: ConfirmDeleteModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  // Focus cancel button dès l'ouverture
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => cancelRef.current?.focus(), 60)
      return () => clearTimeout(t)
    }
  }, [open])

  // Fermeture sur Escape
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !loading) onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose, loading])

  // Bloquer scroll body
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cdm-title"
      aria-describedby="cdm-desc"
      className="fixed inset-0 z-[9999] flex items-end md:items-center justify-center"
    >
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-anthracite/40 backdrop-blur-sm"
        onClick={() => !loading && onClose()}
      />

      {/* Boîte modale — bottom sheet mobile, carte centrée desktop */}
      <div className="relative w-full md:max-w-md bg-white shadow-2xl rounded-t-[24px] md:rounded-[24px] p-6 md:p-8 modal-scale-in">
        {/* Icône danger */}
        <div className="w-12 h-12 rounded-full bg-danger/10 flex items-center justify-center mb-5 mx-auto md:mx-0">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
            <path
              d="M11 7v5M11 15h.01M21 11a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z"
              stroke="#c0392b"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          </svg>
        </div>

        <h2 id="cdm-title" className="font-heading font-bold text-[18px] text-anthracite mb-2 text-center md:text-left">
          {title}
        </h2>
        <p id="cdm-desc" className="font-body text-[14px] text-gray-dk leading-relaxed mb-6 text-center md:text-left">
          {description}
        </p>

        {/* Boutons — empilés mobile, côte à côte desktop */}
        <div className="flex flex-col-reverse md:flex-row md:justify-end gap-3">
          {/* Annuler */}
          <button
            ref={cancelRef}
            onClick={onClose}
            disabled={loading}
            className="min-h-[48px] px-6 rounded-xl font-heading font-semibold text-[14px]
              bg-transparent text-gray-dk border border-gray-light
              hover:bg-gray-pale transition-all active:scale-[.98]
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2
              disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center"
          >
            Annuler
          </button>

          {/* Supprimer */}
          <button
            onClick={onConfirm}
            disabled={loading}
            className="min-h-[48px] px-6 rounded-xl font-heading font-semibold text-[14px]
              bg-danger text-white
              hover:bg-[#a93226] active:scale-[.98] transition-all
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger focus-visible:ring-offset-2
              disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center gap-2"
            aria-label="Confirmer la suppression"
          >
            {loading ? (
              <>
                <Spinner size="sm" />
                <span>Suppression…</span>
              </>
            ) : (
              'Supprimer définitivement'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
