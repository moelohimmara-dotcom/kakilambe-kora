'use client'

import { useCallback, useState } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmDeleteModal } from '@/components/ui/ConfirmDeleteModal'
import { useAsync, useMutation, useInterval } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { trashApi, TrashedItem } from '@/lib/trashApi'
import { formatRelative } from '@/lib/utils'

// Écran corbeille — nouveau périmètre produit (aucune fonctionnalité
// équivalente dans le CDC existant). Contient les articles rejetés (purge
// 1h) et supprimés (purge 72h) en attente de purge — l'archivage persistant
// est un concept séparé, voir /articles → onglet "Archivés". Les entrées
// ici ne sont pas réellement modifiées côté backend au moment de l'envoi
// (voir TODO dans lib/trashApi.ts) : seule la purge (définitive) appelle le
// vrai DELETE existant.
export function TrashScreen() {
  const { show } = useToast()
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [anyActionInFlight, setAnyActionInFlight] = useState(false)

  const fetchTrash = useCallback(() => trashApi.listTrashed(), [])
  const { data, loading, refetch } = useAsync<TrashedItem[]>(fetchTrash)
  const items = data ?? []

  // Rafraîchit toutes les minutes pour que le compte à rebours et la purge
  // automatique à 72h restent à jour sans action utilisateur.
  useInterval(refetch, 60000)

  const { mutate: restore } = useMutation(async (id: string) => {
    setAnyActionInFlight(true)
    try {
      await trashApi.restoreItem(id)
      await refetch()
      show('Article restauré', 'success')
    } finally {
      setAnyActionInFlight(false)
    }
  })

  const { mutate: purge, loading: purging } = useMutation(async (id: string) => {
    setAnyActionInFlight(true)
    try {
      await trashApi.purgeItem(id)
      setDeleteTarget(null)
      await refetch()
      show('Article supprimé définitivement', 'warning')
    } catch (e) {
      show(e instanceof Error ? e.message : 'Échec de la suppression', 'error')
    } finally {
      setAnyActionInFlight(false)
    }
  })

  return (
    <div className="p-6 md:p-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="font-heading font-bold text-2xl text-anthracite">Corbeille</h1>
        <p className="font-heading text-[13px] text-gray-dk mt-0.5">
          Articles rejetés (1h) et supprimés (72h) avant purge automatique.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <div className="w-16 h-16 rounded-xl bg-gray-pale flex items-center justify-center">
            <span className="font-heading text-2xl text-gray-med">🗑</span>
          </div>
          <p className="font-heading font-semibold text-[15px] text-anthracite">Corbeille vide</p>
          <p className="font-heading text-[13px] text-gray-dk">Les articles rejetés ou supprimés apparaîtront ici.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map(item => (
            <TrashCard
              key={item.id}
              item={item}
              disabled={anyActionInFlight}
              onRestore={() => restore(item.id)}
              onPurge={() => setDeleteTarget(item.id)}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && purge(deleteTarget)}
        loading={purging}
        title="Purger cet article ?"
        description="Contrairement à l'archivage, la purge est immédiate et définitive : l'article sera effacé de la base de données."
      />
    </div>
  )
}

function TrashCard({
  item, disabled, onRestore, onPurge,
}: {
  item: TrashedItem
  disabled: boolean
  onRestore: () => void
  onPurge: () => void
}) {
  const msLeft = Math.max(0, new Date(item.purge_at).getTime() - Date.now())
  const isImminent = msLeft < 60 * 60 * 1000
  const purgeLabel = isImminent
    ? `Purge dans ${Math.max(1, Math.round(msLeft / 60000))} min — imminent`
    : `Purge dans ${Math.ceil(msLeft / (60 * 60 * 1000))}h`
  const reasonLabel = item.reason === 'rejected' ? 'Rejeté' : 'Supprimé'

  return (
    <Card padding="sm" className="flex flex-col overflow-hidden h-full opacity-90">
      <div className="-mx-4 -mt-4 mb-4 aspect-[16/9] w-[calc(100%+2rem)] shrink-0 bg-gray-pale grayscale">
        {item.article.image_url ? (
          <img src={item.article.image_url} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gray-pale">
            <span className="font-heading font-bold text-3xl text-gray-med">/</span>
          </div>
        )}
      </div>

      <div className="flex flex-col flex-1">
        <div className="flex items-center gap-2 mb-1.5">
          <h3 className="font-heading font-semibold text-[14px] text-anthracite line-clamp-2 flex-1">
            {item.article.titre}
          </h3>
          <Badge variant={item.reason === 'rejected' ? 'danger' : 'gray'} className="shrink-0">
            {reasonLabel}
          </Badge>
        </div>
        <span className="font-heading text-[11px] text-gray-med mb-3">
          {item.article.source_nom ?? '—'} · {reasonLabel.toLowerCase()} {formatRelative(item.trashed_at)}
        </span>

        <div className="mt-auto flex items-center justify-between gap-2 pt-2 border-t border-gray-pale">
          <Badge variant={isImminent ? 'danger' : 'gray'}>
            {purgeLabel}
          </Badge>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={disabled} onClick={onRestore}>
              Restaurer
            </Button>
            <Button variant="danger" size="sm" disabled={disabled} onClick={onPurge}>
              Purger
            </Button>
          </div>
        </div>
      </div>
    </Card>
  )
}
