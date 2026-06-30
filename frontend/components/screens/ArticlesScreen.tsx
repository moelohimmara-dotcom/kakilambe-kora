'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmDeleteModal } from '@/components/ui/ConfirmDeleteModal'
import { useAsync, useMutation } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { articleApi } from '@/lib/api'
import { formatRelative, statusLabel, statusVariant } from '@/lib/utils'
import type { Article, ArticleStatus } from '@/lib/types'

const STATUS_TABS: { label: string; value: ArticleStatus | '' }[] = [
  { label: 'Tous', value: '' },
  { label: 'En attente', value: 'PENDING_REVIEW' },
  { label: 'Publiés', value: 'PUBLISHED' },
  { label: 'Brouillons', value: 'DRAFT' },
  { label: 'Rejetés', value: 'REJECTED' },
]

export function ArticlesScreen() {
  const [activeStatus, setActiveStatus] = useState<ArticleStatus | ''>('')
  const [evaporating, setEvaporating] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const { show } = useToast()

  const fetchArticles = useCallback(
    () => articleApi.list(activeStatus || undefined),
    [activeStatus]
  )
  const { data, loading, refetch } = useAsync(fetchArticles, [activeStatus])
  const articles = (data as { items: Article[] } | null)?.items ?? []

  const { mutate: approve, loading: approving } = useMutation(async (id: string) => {
    setEvaporating(id)
    await new Promise(r => setTimeout(r, 480))
    const result = await articleApi.approve(id)
    await refetch()
    setEvaporating(null)
    show('Article approuvé et publié sur WordPress', 'success')
    return result
  })

  const { mutate: reject } = useMutation(async (id: string) => {
    setEvaporating(id)
    await new Promise(r => setTimeout(r, 480))
    await articleApi.reject(id)
    await refetch()
    setEvaporating(null)
    show('Article rejeté', 'warning')
  })

  const { mutate: deleteArticle, loading: deleting } = useMutation(async (id: string) => {
    setEvaporating(id)
    await new Promise(r => setTimeout(r, 480))
    await articleApi.delete(id)
    setDeleteTarget(null)
    await refetch()
    setEvaporating(null)
    show('Article supprimé définitivement', 'warning')
  })

  return (
    <div className="p-6 md:p-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-heading font-bold text-2xl text-anthracite">Articles</h1>
          <p className="font-heading text-[13px] text-gray-dk mt-0.5">
            {loading ? '…' : `${articles.length} article${articles.length !== 1 ? 's' : ''}`}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-pale rounded-lg p-1 w-fit flex-wrap" role="tablist" aria-label="Filtrer les articles">
        {STATUS_TABS.map(tab => (
          <button
            key={tab.value}
            id={`tab-${tab.value || 'all'}`}
            role="tab"
            aria-selected={activeStatus === tab.value}
            aria-controls="articles-panel"
            onClick={() => setActiveStatus(tab.value)}
            className={
              `px-4 py-1.5 rounded-md font-heading text-[12px] font-semibold transition-all ` +
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

      {/* Articles list */}
      <div id="articles-panel" role="tabpanel" aria-labelledby={`tab-${activeStatus || 'all'}`}>
      {loading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : articles.length === 0 ? (
        <EmptyState status={activeStatus} />
      ) : (
        <div className="space-y-3">
          {articles.map(article => (
            <div
              key={article.id}
              className={evaporating === article.id ? 'article-evaporate' : ''}
            >
              <ArticleCard
                article={article}
                onApprove={() => approve(article.id)}
                onReject={() => reject(article.id)}
                onDelete={() => setDeleteTarget(article.id)}
                approving={approving && evaporating === article.id}
              />
            </div>
          ))}
        </div>
      )}
      </div>

      <ConfirmDeleteModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteArticle(deleteTarget)}
        loading={deleting}
      />
    </div>
  )
}

// ── Article Card ─────────────────────────────────────────────────────────────

function ArticleCard({
  article, onApprove, onReject, onDelete, approving,
}: {
  article: Article
  onApprove: () => void
  onReject: () => void
  onDelete: () => void
  approving: boolean
}) {
  return (
    <Card className="flex gap-4">
      {/* Thumbnail */}
      <div className="shrink-0">
        {article.image_url ? (
          <img
            src={article.image_url}
            alt=""
            className="w-20 h-20 rounded-md object-cover bg-gray-pale"
          />
        ) : (
          <div className="w-20 h-20 rounded-md bg-orange/10 flex items-center justify-center">
            <span className="font-heading font-bold text-2xl text-orange">/</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3 mb-1">
          <Link
            href={`/articles/${article.id}`}
            className="font-heading font-semibold text-[14px] text-anthracite hover:text-orange transition-colors line-clamp-2 flex-1"
          >
            {article.titre}
          </Link>
          <Badge variant={statusVariant(article.status)} className="shrink-0 mt-0.5">
            {statusLabel(article.status)}
          </Badge>
        </div>

        {article.chapeau && (
          <p className="font-body text-[13px] text-gray-dk line-clamp-2 mb-2">
            {article.chapeau}
          </p>
        )}

        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-heading text-[11px] text-gray-med">
            {article.source_nom ?? '—'} · {formatRelative(article.created_at)}
          </span>
          {article.word_count && (
            <span className="font-heading text-[11px] text-gray-med">
              {article.word_count} mots
            </span>
          )}
          {article.mots_cles && article.mots_cles.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {article.mots_cles.slice(0, 3).map(k => (
                <span key={k} className="font-heading text-[10px] bg-gray-pale text-gray-dk px-2 py-0.5 rounded-full">
                  {k}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Actions (PENDING_REVIEW seulement) */}
      {article.status === 'PENDING_REVIEW' && (
        <div className="shrink-0 flex flex-col gap-2 self-start">
          <Button
            variant="primary"
            size="sm"
            onClick={onApprove}
            loading={approving}
            aria-label={`Approuver : ${article.titre}`}
          >
            Approuver
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onReject}
            aria-label={`Rejeter : ${article.titre}`}
          >
            Rejeter
          </Button>
        </div>
      )}

      {/* Lien WP + Supprimer */}
      <div className="shrink-0 self-start flex flex-col items-end gap-2">
        {article.status === 'PUBLISHED' && article.wp_url && (
          <a
            href={article.wp_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-heading text-[12px] text-blue-txt hover:underline flex items-center gap-1"
          >
            Voir sur WP ↗
          </a>
        )}
        <button
          onClick={onDelete}
          className="font-heading text-[11px] text-gray-med hover:text-danger transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger rounded"
          aria-label={`Supprimer : ${article.titre}`}
        >
          Supprimer
        </button>
      </div>
    </Card>
  )
}

function EmptyState({ status }: { status: ArticleStatus | '' }) {
  return (
    <div className="empty-state">
      <div className="w-16 h-16 rounded-xl bg-gray-pale flex items-center justify-center">
        <span className="font-heading text-2xl text-gray-med">□</span>
      </div>
      <p className="font-heading font-semibold text-[15px] text-anthracite">
        {status ? `Aucun article "${statusLabel(status as ArticleStatus)}"` : 'Aucun article'}
      </p>
      <p className="font-heading text-[13px] text-gray-dk">
        🤖 KORA travaille, revenez bientôt.
      </p>
    </div>
  )
}
