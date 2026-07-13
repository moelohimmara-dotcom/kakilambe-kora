'use client'

import { useState, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Trash2, Archive, ArchiveRestore } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { useAsync, useMutation } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { articleApi } from '@/lib/api'
import { trashApi } from '@/lib/trashApi'
import { archiveApi } from '@/lib/archiveApi'
import { gamificationApi } from '@/lib/gamificationApi'
import { formatRelative, statusLabel, statusVariant } from '@/lib/utils'
import type { Article, ArticleStatus } from '@/lib/types'

// 'ARCHIVED' est un pseudo-statut front-end (voir lib/archiveApi.ts) — le
// backend n'a pas de colonne ARCHIVED, ce filtre recoupe côté client la
// liste complète avec le suivi local des ids archivés.
type TabValue = ArticleStatus | '' | 'ARCHIVED'

const STATUS_TABS: { label: string; value: TabValue }[] = [
  { label: 'Tous', value: '' },
  { label: 'En attente', value: 'PENDING_REVIEW' },
  { label: 'Publiés', value: 'PUBLISHED' },
  { label: 'Brouillons', value: 'DRAFT' },
  { label: 'Rejetés', value: 'REJECTED' },
  { label: 'Archivés', value: 'ARCHIVED' },
]

const VALID_STATUSES = new Set(STATUS_TABS.map(t => t.value))

export function ArticlesScreen() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const statusFromUrl = searchParams.get('status') ?? ''
  const [activeStatus, setActiveStatus] = useState<TabValue>(
    VALID_STATUSES.has(statusFromUrl as TabValue) ? (statusFromUrl as TabValue) : ''
  )
  const [evaporating, setEvaporating] = useState<string | null>(null)
  const [navigatingId, setNavigatingId] = useState<string | null>(null)
  // Suivi local — archivage persistant (lib/archiveApi.ts) et corbeille
  // (lib/trashApi.ts, rejetés + supprimés en attente de purge) sont deux
  // stores distincts, le backend n'ayant ni l'un ni l'autre en base.
  const [archivedIds, setArchivedIds] = useState<Set<string>>(() => archiveApi.archivedIds())
  const [trashedIds, setTrashedIds] = useState<Set<string>>(() => trashApi.trashedIds())
  const { show } = useToast()

  // Transition de sortie (fade + léger scale, CSS natif) avant navigation
  // vers la page de détail — évite le saut brutal signalé dans le CDC (5.4.1),
  // sans dépendance supplémentaire.
  function openArticle(id: string) {
    setNavigatingId(id)
    setTimeout(() => router.push(`/articles/${id}`), 200)
  }

  const fetchArticles = useCallback(
    () => articleApi.list(activeStatus === 'ARCHIVED' ? undefined : (activeStatus || undefined)),
    [activeStatus]
  )
  const { data, loading, refetch } = useAsync(fetchArticles, [activeStatus])
  const rawArticles = (data as { items: Article[] } | null)?.items ?? []
  const articles = activeStatus === 'ARCHIVED'
    ? rawArticles.filter(a => archivedIds.has(a.id))
    : rawArticles.filter(a => !archivedIds.has(a.id) && !trashedIds.has(a.id))

  const { mutate: approve, loading: approving } = useMutation(async (id: string) => {
    setEvaporating(id)
    await new Promise(r => setTimeout(r, 480))
    const result = await articleApi.approve(id)
    await refetch()
    setEvaporating(null)
    show('Article approuvé et publié sur WordPress', 'success')
    const milestone = await gamificationApi.checkNewMilestone().catch(() => null)
    if (milestone) show(milestone.label, 'achievement')
    return result
  })

  // Rejeter change le vrai statut (REJECTED, comme avant) ET envoie
  // l'article dans la corbeille avec une rétention courte (1h — voir
  // wireframes fournis), plutôt que de le laisser simplement rejeté en
  // place sans suite.
  const { mutate: reject } = useMutation(async (article: Article) => {
    setEvaporating(article.id)
    await new Promise(r => setTimeout(r, 480))
    await articleApi.reject(article.id)
    await trashApi.sendToTrash(article, 'rejected')
    setTrashedIds(trashApi.trashedIds())
    await refetch()
    setEvaporating(null)
    show('Article rejeté — envoyé à la corbeille (purge dans 1h)', 'warning')
  })

  // Archivage persistant — distinct de la corbeille, aucune purge, filtrable
  // sous l'onglet "Archivés" (voir lib/archiveApi.ts).
  const { mutate: archive } = useMutation(async (article: Article) => {
    setEvaporating(article.id)
    await new Promise(r => setTimeout(r, 480))
    await archiveApi.archiveArticle(article.id)
    setArchivedIds(archiveApi.archivedIds())
    setEvaporating(null)
    show('Article archivé', 'success')
  })

  const { mutate: unarchive } = useMutation(async (id: string) => {
    await archiveApi.unarchiveArticle(id)
    setArchivedIds(archiveApi.archivedIds())
    show('Article désarchivé', 'success')
  })

  // Supprimer envoie désormais à la corbeille (72h, restaurable) au lieu
  // d'un DELETE réel instantané — la suppression réelle n'a lieu qu'à la
  // purge (auto ou manuelle depuis /corbeille).
  const { mutate: deleteArticle } = useMutation(async (article: Article) => {
    setEvaporating(article.id)
    await new Promise(r => setTimeout(r, 480))
    await trashApi.sendToTrash(article, 'deleted')
    setTrashedIds(trashApi.trashedIds())
    await refetch()
    setEvaporating(null)
    show('Article envoyé à la corbeille (purge dans 72h)', 'warning')
  })

  return (
    <div className="p-4 md:p-8 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-heading font-bold text-2xl text-anthracite">Articles</h1>
          <p className="font-heading text-[13px] text-gray-dk mt-0.5">
            {loading ? '…' : `${articles.length} article${articles.length !== 1 ? 's' : ''}`}
          </p>
        </div>
      </div>

      {/* Tabs — scrollable horizontalement sur mobile plutôt que de wrapper */}
      <div
        className="flex gap-1 mb-6 bg-gray-pale rounded-lg p-1 w-full md:w-fit overflow-x-auto"
        role="tablist"
        aria-label="Filtrer les articles"
      >
        {STATUS_TABS.map(tab => (
          <button
            key={tab.value}
            id={`tab-${tab.value || 'all'}`}
            role="tab"
            aria-selected={activeStatus === tab.value}
            aria-controls="articles-panel"
            onClick={() => setActiveStatus(tab.value)}
            className={
              `shrink-0 px-4 min-h-[44px] rounded-md font-heading text-[12px] font-semibold transition-all ` +
              `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
              `${activeStatus === tab.value
                ? 'bg-white text-anthracite shadow-sm'
                : 'text-gray-dk hover:text-anthracite'
              }`
            }
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Grille de cartes — 1 colonne mobile, 2 tablette, 3 desktop */}
      <div id="articles-panel" role="tabpanel" aria-labelledby={`tab-${activeStatus || 'all'}`}>
      {loading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : articles.length === 0 ? (
        <EmptyState status={activeStatus} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {articles.map(article => (
            <div
              key={article.id}
              className={
                evaporating === article.id
                  ? 'article-evaporate'
                  : navigatingId === article.id
                  ? 'opacity-0 scale-[0.98] transition-all duration-200'
                  : ''
              }
            >
              <ArticleCard
                article={article}
                isArchivedView={activeStatus === 'ARCHIVED'}
                onOpen={() => openArticle(article.id)}
                onApprove={() => approve(article.id)}
                onReject={() => reject(article)}
                onArchive={() => activeStatus === 'ARCHIVED' ? unarchive(article.id) : archive(article)}
                onDelete={() => deleteArticle(article)}
                approving={approving && evaporating === article.id}
              />
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  )
}

// ── Article Card ─────────────────────────────────────────────────────────────
// Carte verticale pleinement cliquable (ouvre la page de consultation au clic
// n'importe où sur la carte) — les boutons d'action internes stoppent la
// propagation pour ne pas déclencher l'ouverture en même temps.

function ArticleCard({
  article, isArchivedView, onOpen, onApprove, onReject, onArchive, onDelete, approving,
}: {
  article: Article
  isArchivedView: boolean
  onOpen: () => void
  onApprove: () => void
  onReject: () => void
  onArchive: () => void
  onDelete: () => void
  approving: boolean
}) {
  function stop<T>(fn: () => T) {
    return (e: React.MouseEvent) => { e.stopPropagation(); fn() }
  }

  return (
    <Card
      padding="sm"
      onClick={onOpen}
      className="flex flex-col cursor-pointer hover:shadow-md hover:scale-[1.01] transition-all duration-200 overflow-hidden h-full"
    >
      {/* Miniature — marge négative pour "bleeder" jusqu'aux bords malgré le
          padding par défaut de Card (éviter un conflit d'utilitaires p-0/p-5
          dont l'ordre de cascade Tailwind n'est pas garanti sur un même
          élément). */}
      <div className="-mx-4 -mt-4 mb-4 aspect-[16/9] w-[calc(100%+2rem)] shrink-0 bg-gray-pale">
        {article.image_url ? (
          <img
            src={article.image_url}
            alt=""
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-orange/10">
            <span className="font-heading font-bold text-3xl text-orange">/</span>
          </div>
        )}
      </div>

      <div className="flex flex-col flex-1">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <h3 className="font-heading font-semibold text-[14px] text-anthracite line-clamp-2 flex-1">
            {article.titre}
          </h3>
          <Badge variant={statusVariant(article.status)} className="shrink-0">
            {statusLabel(article.status)}
          </Badge>
        </div>

        {article.chapeau && (
          <p className="font-body text-[13px] text-gray-dk line-clamp-2 mb-3">
            {article.chapeau}
          </p>
        )}

        <span className="font-heading text-[11px] text-gray-med mb-3">
          {article.source_nom ?? '—'} · {formatRelative(article.created_at)}
        </span>

        <div className="mt-auto flex items-center justify-between gap-2 pt-2 border-t border-gray-pale">
          {article.status === 'PENDING_REVIEW' ? (
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={stop(onApprove)}
                loading={approving}
                aria-label={`Approuver : ${article.titre}`}
              >
                Approuver
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={stop(onReject)}
                aria-label={`Rejeter : ${article.titre}`}
              >
                Rejeter
              </Button>
            </div>
          ) : article.status === 'PUBLISHED' && article.wp_url ? (
            <a
              href={article.wp_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="font-heading text-[12px] text-blue-txt hover:underline min-h-[44px] flex items-center"
            >
              Voir sur WP ↗
            </a>
          ) : <span />}

          <div className="flex items-center shrink-0">
            <button
              onClick={stop(onArchive)}
              title={isArchivedView ? 'Désarchiver' : 'Archiver'}
              className="w-11 h-11 flex items-center justify-center text-gray-med hover:text-anthracite transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
              aria-label={`${isArchivedView ? 'Désarchiver' : 'Archiver'} : ${article.titre}`}
            >
              {isArchivedView ? <ArchiveRestore size={18} aria-hidden="true" /> : <Archive size={18} aria-hidden="true" />}
            </button>
            {!isArchivedView && (
              <button
                onClick={stop(onDelete)}
                title="Supprimer"
                className="w-11 h-11 flex items-center justify-center text-gray-med hover:text-danger transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
                aria-label={`Supprimer : ${article.titre}`}
              >
                <Trash2 size={18} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}

function EmptyState({ status }: { status: TabValue }) {
  const label = status === 'ARCHIVED' ? 'Archivés' : status ? statusLabel(status as ArticleStatus) : null
  return (
    <div className="empty-state">
      <div className="w-16 h-16 rounded-xl bg-gray-pale flex items-center justify-center">
        <span className="font-heading text-2xl text-gray-med">□</span>
      </div>
      <p className="font-heading font-semibold text-[15px] text-anthracite">
        {label ? `Aucun article "${label}"` : 'Aucun article'}
      </p>
      <p className="font-heading text-[13px] text-gray-dk">
        🤖 KORA travaille, revenez bientôt.
      </p>
    </div>
  )
}
