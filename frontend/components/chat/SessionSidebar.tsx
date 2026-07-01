'use client'

import { useCallback, useState } from 'react'
import { Plus } from 'lucide-react'
import { SessionItem } from './SessionItem'
import { ConfirmDeleteModal } from '@/components/ui/ConfirmDeleteModal'
import { Spinner } from '@/components/ui/Spinner'
import { useAsync, useMutation } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { chatApi } from '@/lib/api'
import type { ChatSession } from '@/lib/types'

interface SessionSidebarProps {
  activeSessionId: string | null
  onSelect: (id: string) => void
  onNewConversation: () => void
  refreshKey?: number
}

export function SessionSidebar({ activeSessionId, onSelect, onNewConversation, refreshKey }: SessionSidebarProps) {
  const { show } = useToast()
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const fetchSessions = useCallback(() => chatApi.sessions(), [])
  const { data, loading, refetch } = useAsync(fetchSessions, [refreshKey])
  const sessions: ChatSession[] = data ?? []

  const { mutate: rename } = useMutation(async ({ id, title }: { id: string; title: string }) => {
    await chatApi.updateSession(id, { title })
    await refetch()
  })

  const { mutate: togglePin } = useMutation(async (session: ChatSession) => {
    await chatApi.updateSession(session.id, { is_pinned: !session.is_pinned })
    await refetch()
  })

  const { mutate: archive } = useMutation(async (id: string) => {
    await chatApi.updateSession(id, { status: 'archived' })
    await refetch()
    show('Conversation archivée', 'warning')
    if (id === activeSessionId) onNewConversation()
  })

  const { mutate: remove, loading: deleting } = useMutation(async (id: string) => {
    await chatApi.deleteSession(id)
    setDeleteTarget(null)
    await refetch()
    show('Conversation supprimée', 'warning')
    if (id === activeSessionId) onNewConversation()
  })

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-gray-light shrink-0">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg font-heading text-[13px] font-semibold text-anthracite bg-white border border-gray-light hover:border-orange hover:text-orange transition-colors"
        >
          <Plus size={15} />
          Nouvelle conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {loading ? (
          <div className="flex justify-center py-8"><Spinner size="sm" /></div>
        ) : sessions.length === 0 ? (
          <p className="font-heading text-[12px] text-gray-med text-center py-8 px-3">
            Aucune conversation. Commencez à discuter avec KORA.
          </p>
        ) : (
          sessions.map(session => (
            <SessionItem
              key={session.id}
              session={session}
              active={session.id === activeSessionId}
              onSelect={() => onSelect(session.id)}
              onRename={title => rename({ id: session.id, title })}
              onTogglePin={() => togglePin(session)}
              onArchive={() => archive(session.id)}
              onDelete={() => setDeleteTarget(session.id)}
            />
          ))
        )}
      </div>

      <ConfirmDeleteModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && remove(deleteTarget)}
        loading={deleting}
        title="Supprimer cette conversation ?"
        description="Cette action est irréversible. Tous les messages de cette conversation seront définitivement effacés."
      />
    </div>
  )
}
