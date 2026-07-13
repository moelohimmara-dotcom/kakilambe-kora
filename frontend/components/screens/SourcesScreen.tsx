'use client'

import { useState, useCallback } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { Toggle } from '@/components/ui/Toggle'
import { Modal } from '@/components/ui/Modal'
import { useAsync, useMutation } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { settingsApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import type { RSSSource } from '@/lib/types'

export function SourcesScreen() {
  const [showAdd, setShowAdd] = useState(false)
  const [newSource, setNewSource] = useState({ name: '', url: '', category: '' })
  const [formError, setFormError] = useState('')
  const { show } = useToast()

  const fetchSources = useCallback(() => settingsApi.sources(), [])
  const { data: sources, loading, refetch } = useAsync<RSSSource[]>(fetchSources)

  const { mutate: addSource, loading: adding } = useMutation(async () => {
    if (!newSource.name.trim() || !newSource.url.trim()) {
      setFormError('Nom et URL sont requis')
      return
    }
    try { new URL(newSource.url) } catch {
      setFormError('URL invalide')
      return
    }
    await settingsApi.createSource({
      name: newSource.name,
      url: newSource.url,
      category: newSource.category || undefined,
    })
    setNewSource({ name: '', url: '', category: '' })
    setFormError('')
    setShowAdd(false)
    show('Source ajoutée', 'success')
    await refetch()
  })

  const { mutate: deleteSource } = useMutation(async (id: string) => {
    await settingsApi.deleteSource(id)
    show('Source supprimée', 'warning')
    await refetch()
  })

  const { mutate: toggleSource } = useMutation(async ({ id, active }: { id: string; active: boolean }) => {
    await settingsApi.updateSource(id, { is_active: active })
    await refetch()
  })

  return (
    <div className="p-6 md:p-8 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-heading font-bold text-2xl text-anthracite">Sources RSS</h1>
          <p className="font-heading text-[13px] text-gray-dk mt-0.5">
            {loading ? '…' : `${(sources ?? []).length} source${(sources ?? []).length !== 1 ? 's' : ''} configurée${(sources ?? []).length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setShowAdd(true)}>
          + Ajouter une source
        </Button>
      </div>

      {/* Sources list */}
      {loading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : (sources ?? []).length === 0 ? (
        <div className="empty-state">
          <div className="w-16 h-16 rounded-xl bg-gray-pale flex items-center justify-center">
            <span className="font-heading text-2xl text-gray-med">◎</span>
          </div>
          <p className="font-heading font-semibold text-[15px] text-anthracite">Aucune source configurée</p>
          <p className="font-heading text-[13px] text-gray-dk max-w-xs">
            Ajoutez des sources RSS d'actualité guinéenne et africaine pour alimenter KORA.
          </p>
          <Button variant="primary" onClick={() => setShowAdd(true)}>Ajouter la première source</Button>
        </div>
      ) : (
        <div className="space-y-3">
          {(sources ?? []).map(source => (
            <SourceCard
              key={source.id}
              source={source}
              onDelete={() => deleteSource(source.id)}
              onToggle={active => toggleSource({ id: source.id, active })}
            />
          ))}
        </div>
      )}

      {/* Modal ajout */}
      <Modal
        open={showAdd}
        onClose={() => { setShowAdd(false); setFormError('') }}
        title="Ajouter une source RSS"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setShowAdd(false)}>Annuler</Button>
            <Button variant="confirm" size="sm" loading={adding} onClick={() => addSource(undefined as unknown as void)}>
              Ajouter
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {formError && (
            <p className="font-heading text-[12px] text-danger bg-danger/8 border border-danger/20 rounded-md px-3 py-2">
              {formError}
            </p>
          )}
          <div>
            <label htmlFor="src-name" className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2">
              Nom
            </label>
            <input
              id="src-name"
              type="text"
              value={newSource.name}
              onChange={e => setNewSource(p => ({ ...p, name: e.target.value }))}
              placeholder="ex: Guinée Conakry Info"
              className="form-input"
            />
          </div>
          <div>
            <label htmlFor="src-url" className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2">
              URL du flux RSS
            </label>
            <input
              id="src-url"
              type="url"
              value={newSource.url}
              onChange={e => setNewSource(p => ({ ...p, url: e.target.value }))}
              placeholder="https://example.com/rss.xml"
              className="form-input"
            />
          </div>
          <div>
            <label htmlFor="src-cat" className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2">
              Catégorie (optionnel)
            </label>
            <input
              id="src-cat"
              type="text"
              value={newSource.category}
              onChange={e => setNewSource(p => ({ ...p, category: e.target.value }))}
              placeholder="ex: Politique, Économie, Sport"
              className="form-input"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}

function SourceCard({
  source, onDelete, onToggle,
}: {
  source: RSSSource
  onDelete: () => void
  onToggle: (active: boolean) => void
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const { show } = useToast()

  return (
    <Card className="flex items-center gap-4">
      {/* Icon */}
      <div className="w-10 h-10 rounded-md bg-blue/10 flex items-center justify-center shrink-0">
        <span className="font-heading text-[11px] font-bold text-blue-txt">RSS</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="font-heading font-semibold text-[13px] text-anthracite truncate">{source.name}</p>
          {source.category && (
            <Badge variant="blue" className="shrink-0">{source.category}</Badge>
          )}
          {source.error_count > 0 && (
            <Badge variant="danger" className="shrink-0">{source.error_count} erreur{source.error_count > 1 ? 's' : ''}</Badge>
          )}
        </div>
        <p className="font-heading text-[11px] text-gray-med truncate">{source.url}</p>
        {source.last_synced && (
          <p className="font-heading text-[10px] text-gray-med mt-0.5">
            Dernière synchro : {formatDate(source.last_synced)}
          </p>
        )}
      </div>

      {/* Toggle actif */}
      <Toggle
        checked={source.is_active}
        onChange={onToggle}
        size="sm"
        aria-label={`Activer/désactiver ${source.name}`}
      />

      {/* Supprimer */}
      {confirmDelete ? (
        <div className="flex gap-2 shrink-0">
          <Button variant="danger" size="sm" onClick={() => { onDelete(); setConfirmDelete(false) }}>
            Confirmer
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>Annuler</Button>
        </div>
      ) : (
        <button
          onClick={() => setConfirmDelete(true)}
          className="w-11 h-11 flex items-center justify-center rounded-md text-gray-med hover:text-danger hover:bg-danger/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
          aria-label={`Supprimer ${source.name}`}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path d="M1 3.5h12M5 3.5V2a.5.5 0 01.5-.5h3a.5.5 0 01.5.5v1.5M6 6.5v4M8 6.5v4M2.5 3.5l1 8.5a.5.5 0 00.5.5h6a.5.5 0 00.5-.5l1-8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      )}
    </Card>
  )
}
