'use client'

import { useState, useRef, useEffect } from 'react'
import { Pin, Edit3, Archive, Trash2 } from 'lucide-react'
import type { ChatSession } from '@/lib/types'

interface SessionItemProps {
  session: ChatSession
  active: boolean
  onSelect: () => void
  onRename: (title: string) => void
  onTogglePin: () => void
  onArchive: () => void
  onDelete: () => void
}

export function SessionItem({
  session, active, onSelect, onRename, onTogglePin, onArchive, onDelete,
}: SessionItemProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(session.title ?? '')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing) inputRef.current?.focus()
  }, [isEditing])

  function startEditing(e: React.MouseEvent) {
    e.stopPropagation()
    setEditTitle(session.title ?? '')
    setIsEditing(true)
  }

  function save() {
    const trimmed = editTitle.trim()
    setIsEditing(false)
    if (trimmed && trimmed !== (session.title ?? '')) {
      onRename(trimmed)
    }
  }

  function cancel() {
    setEditTitle(session.title ?? '')
    setIsEditing(false)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') { e.preventDefault(); save() }
    if (e.key === 'Escape') { e.preventDefault(); cancel() }
  }

  return (
    <div
      onClick={!isEditing ? onSelect : undefined}
      className={
        `group relative flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ` +
        `${active ? 'bg-orange/10' : 'hover:bg-gray-pale'}`
      }
    >
      {session.is_pinned && !isEditing && (
        <Pin size={12} className="shrink-0 text-orange fill-orange" aria-label="Épinglée" />
      )}

      {isEditing ? (
        <input
          ref={inputRef}
          type="text"
          value={editTitle}
          onChange={e => setEditTitle(e.target.value)}
          onBlur={save}
          onKeyDown={handleKeyDown}
          onClick={e => e.stopPropagation()}
          className="flex-1 min-w-0 bg-transparent outline-none border-b border-orange/50 text-anthracite font-heading text-[13px] py-0.5"
          aria-label="Renommer la conversation"
        />
      ) : (
        <span
          className={`flex-1 min-w-0 truncate font-heading text-[13px] ${active ? 'text-anthracite font-medium' : 'text-gray-dk'}`}
        >
          {session.title || 'Nouvelle conversation'}
        </span>
      )}

      {!isEditing && (
        <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
          <button
            onClick={e => { e.stopPropagation(); onTogglePin() }}
            title={session.is_pinned ? 'Désépingler' : 'Épingler'}
            className="p-1 rounded text-gray-med hover:text-orange transition-colors"
            aria-label={session.is_pinned ? 'Désépingler' : 'Épingler'}
          >
            <Pin size={13} className={session.is_pinned ? 'fill-orange text-orange' : ''} />
          </button>
          <button
            onClick={startEditing}
            title="Renommer"
            className="p-1 rounded text-gray-med hover:text-anthracite transition-colors"
            aria-label="Renommer"
          >
            <Edit3 size={13} />
          </button>
          <button
            onClick={e => { e.stopPropagation(); onArchive() }}
            title="Archiver"
            className="p-1 rounded text-gray-med hover:text-anthracite transition-colors"
            aria-label="Archiver"
          >
            <Archive size={13} />
          </button>
          <button
            onClick={e => { e.stopPropagation(); onDelete() }}
            title="Supprimer"
            className="p-1 rounded text-gray-med hover:text-danger transition-colors"
            aria-label="Supprimer"
          >
            <Trash2 size={13} />
          </button>
        </div>
      )}
    </div>
  )
}
