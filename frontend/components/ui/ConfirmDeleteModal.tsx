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
  description = 'Cette action est irréversible. L\'article sera définitivement effacé de la base de données.',
}: ConfirmDeleteModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  // Focus cancel button on open (évite suppression accidentelle)
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => cancelRef.current?.focus(), 50)
      return () => clearTimeout(t)
    }
  }, [open])

  // Fermeture sur Escape
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Bloquer le scroll du body
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    /* Overlay */
    <div
      className="fixed inset-0 z-50 bg-anthracite/40 backdrop-blur-sm flex items-end md:items-center justify-center"
      onClick={onClose}
      aria-modal="true"
      role="dialog"
      aria-labelledby="cdm-title"
      aria-describedby="cdm-desc"
    >
      {/* Conteneur — bottom sheet sur mobile, carte centrée sur desktop */}
      <div
        className={[
          'bg-white w-full md:max-w-md md:rounded-[24px] shadow-2xl',
          'rounded-t-[24px] md:rounded-[24px]',
          /* animation */
          'hidden md:block modal-scale-in',
        ].join(' ')}
        onClick={e => e.stopPropagation()}
      >
        {/* Version desktop */}
        <ModalContent
          title={title}
          description={description}
          loading={loading}
          onClose={onClose}
          onConfirm={onConfirm}
          cancelRef={cancelRef}
          stackButtons={false}
        />
      </div>

      {/* Bottom sheet — mobile uniquement */}
      <div
        className={[
          'bg-white w-full rounded-t-[24px] shadow-2xl',
          'block md:hidden sheet-slide-up',
        ].join(' ')}
        onClick={e => e.stopPropagation()}
      >
        <ModalContent
          title={title}
          description={description}
          loading={loading}
          onClose={onClose}
          onConfirm={onConfirm}
          cancelRef={cancelRef}
          stackButtons={true}
        />
      </div>
    </div>
  )
}

function ModalContent({
  title,
  description,
  loading,
  onClose,
  onConfirm,
  cancelRef,
  stackButtons,
}: {
  title: string
  description: string
  loading: boolean
  onClose: () => void
  onConfirm: () => void
  cancelRef: React.RefObject<HTMLButtonElement>
  stackButtons: boolean
}) {
  return (
    <div className="p-6 md:p-8">
      {/* Icône danger */}
      <div className="w-12 h-12 rounded-full bg-danger/10 flex items-center justify-center mb-5 mx-auto md:mx-0">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
          <path d="M11 7v5M11 15h.01M21 11a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z"
            stroke="#c0392b" strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
      </div>

      <h2 id="cdm-title" className="font-heading font-bold text-[18px] text-anthracite mb-2 text-center md:text-left">
        {title}
      </h2>
      <p id="cdm-desc" className="font-body text-[14px] text-gray-dk leading-relaxed mb-6 text-center md:text-left">
        {description}
      </p>

      {/* Boutons */}
      <div className={`flex gap-3 ${stackButtons ? 'flex-col' : 'flex-row justify-end'}`}>
        {/* Supprimer — en haut sur mobile, à droite sur desktop */}
        <button
          onClick={onConfirm}
          disabled={loading}
          className={[
            'min-h-[48px] px-6 rounded-xl font-heading font-semibold text-[14px]',
            'bg-danger text-white transition-all',
            'hover:bg-[#a93226] active:scale-[.98]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger focus-visible:ring-offset-2',
            'disabled:opacity-50 disabled:pointer-events-none',
            'flex items-center justify-center gap-2',
            stackButtons ? 'order-1 w-full' : 'order-2',
          ].join(' ')}
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

        {/* Annuler — en bas sur mobile, à gauche sur desktop */}
        <button
          ref={cancelRef}
          onClick={onClose}
          disabled={loading}
          className={[
            'min-h-[48px] px-6 rounded-xl font-heading font-semibold text-[14px]',
            'bg-transparent text-gray-dk border border-gray-light',
            'hover:bg-gray-pale transition-all active:scale-[.98]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange focus-visible:ring-offset-2',
            'disabled:opacity-50 disabled:pointer-events-none',
            'flex items-center justify-center',
            stackButtons ? 'order-2 w-full' : 'order-1',
          ].join(' ')}
        >
          Annuler
        </button>
      </div>
    </div>
  )
}
