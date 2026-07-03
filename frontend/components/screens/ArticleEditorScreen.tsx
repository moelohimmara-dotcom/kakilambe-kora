'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import { useAsync, useMutation } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { articleApi } from '@/lib/api'
import { formatDate, statusLabel, statusVariant, wordCount } from '@/lib/utils'
import type { Article } from '@/lib/types'

export function ArticleEditorScreen({ id }: { id: string }) {
  const router = useRouter()
  const { show } = useToast()
  const [evaporating, setEvaporating] = useState(false)
  const [confirmReject, setConfirmReject] = useState(false)

  const fetchArticle = useCallback(() => articleApi.get(id), [id])
  const { data: article, loading, error, refetch } = useAsync<Article>(fetchArticle)

  const { mutate: save } = useMutation(
    ({ field, value }: { field: string; value: string }) =>
      articleApi.patch(id, { [field]: value })
  )

  const { mutate: approve, loading: approving } = useMutation(async () => {
    setEvaporating(true)
    await new Promise(r => setTimeout(r, 480))
    await articleApi.approve(id)
    show('Article approuvé — publication en cours sur WordPress', 'success')
    router.push('/articles')
  })

  const { mutate: reject } = useMutation(async () => {
    await articleApi.reject(id)
    show('Article rejeté', 'warning')
    router.push('/articles')
  })

  const { mutate: regenerateImage, loading: regeneratingImage } = useMutation(async () => {
    await articleApi.regenerateImage(id)
    await refetch()
    show('Image régénérée', 'success')
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner size="lg" />
      </div>
    )
  }

  if (error || !article) {
    return (
      <div className="p-8 text-center">
        <p className="font-heading text-gray-dk">Article introuvable</p>
        <Button href="/articles" variant="ghost" size="sm" className="mt-4">← Retour</Button>
      </div>
    )
  }

  return (
    <div className={`min-h-screen ${evaporating ? 'article-evaporate' : ''}`}>
      {/* Top bar */}
      <div className="sticky top-16 z-10 bg-white/90 backdrop-blur-sm border-b border-gray-light px-6 py-3 flex items-center gap-4">
        <Button href="/articles" variant="ghost" size="sm">← Retour</Button>
        <div className="flex-1 min-w-0">
          <span className="font-heading text-[12px] text-gray-dk truncate block">
            {article.source_nom ?? '—'} · {formatDate(article.created_at)}
          </span>
        </div>
        <Badge variant={statusVariant(article.status)}>
          {statusLabel(article.status)}
        </Badge>
        {article.status === 'PENDING_REVIEW' && (
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setConfirmReject(true)}
            >
              Rejeter
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={approving}
              onClick={() => approve(undefined as unknown as void)}
            >
              Approuver et publier
            </Button>
          </>
        )}
        {article.wp_url && (
          <a
            href={article.wp_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-heading text-[12px] text-blue-txt hover:underline"
          >
            Voir sur WordPress ↗
          </a>
        )}
      </div>

      {/* Layout 2/3 + 1/3 */}
      <div className="flex flex-col lg:flex-row gap-0">

        {/* ── Colonne gauche 2/3 : Article ── */}
        <main className="flex-1 lg:max-w-[66%] p-6 md:p-8 border-r border-gray-pale">
          {/* Image */}
          {article.image_url && (
            <div className="mb-6 relative group">
              <div className="rounded-xl overflow-hidden">
                <img
                  src={article.image_url}
                  alt="Illustration de l'article"
                  className="w-full h-52 object-cover"
                />
              </div>
              {article.status !== 'PUBLISHED' && (
                <Button
                  variant="outline"
                  size="sm"
                  loading={regeneratingImage}
                  onClick={() => regenerateImage(undefined as unknown as void)}
                  className="absolute bottom-3 right-3 bg-white/90 backdrop-blur-sm"
                >
                  ↻ Régénérer l'image
                </Button>
              )}
            </div>
          )}

          {/* Titre */}
          <EditableField
            tag="h1"
            value={article.titre}
            className="font-heading font-bold text-[26px] leading-tight text-anthracite mb-4"
            onSave={v => save({ field: 'titre', value: v })}
            placeholder="Titre de l'article"
          />

          {/* Chapeau */}
          {article.chapeau !== undefined && (
            <EditableField
              tag="p"
              value={article.chapeau}
              className="font-body text-[16px] text-gray-dk leading-relaxed mb-6 italic border-l-2 border-orange pl-4"
              onSave={v => save({ field: 'chapeau', value: v })}
              placeholder="Chapeau de l'article"
            />
          )}

          <div className="divider mb-6" />

          {/* Corps */}
          {article.corps !== undefined && (
            <EditableField
              tag="div"
              value={article.corps}
              className="prose-article"
              onSave={v => save({ field: 'corps', value: v })}
              placeholder="Corps de l'article"
              multiline
            />
          )}
        </main>

        {/* ── Colonne droite 1/3 : Actions ── */}
        <aside className="lg:w-80 xl:w-96 shrink-0 p-6 md:p-8 space-y-6">
          {/* Méta SEO */}
          <div>
            <h2 className="font-heading font-semibold text-[13px] text-gray-dk uppercase tracking-wide mb-3">
              SEO
            </h2>
            <Card padding="sm" className="space-y-3">
              <div>
                <label className="block font-heading text-[11px] text-gray-dk mb-1.5">Méta-description</label>
                <EditableField
                  tag="p"
                  value={article.meta_description ?? ''}
                  className="font-heading text-[12px] text-anthracite leading-relaxed"
                  onSave={v => save({ field: 'meta_description', value: v })}
                  placeholder="Méta-description (max 155 caractères)"
                />
                {article.meta_description && (
                  <span className={`font-heading text-[10px] ${article.meta_description.length > 155 ? 'text-danger' : 'text-gray-med'}`}>
                    {article.meta_description.length}/155
                  </span>
                )}
              </div>
              <div>
                <label className="block font-heading text-[11px] text-gray-dk mb-1.5">Mots-clés</label>
                <div className="flex flex-wrap gap-1.5">
                  {(article.mots_cles ?? []).map(k => (
                    <span key={k} className="font-heading text-[11px] bg-orange/10 text-orange px-2.5 py-1 rounded-full">
                      {k}
                    </span>
                  ))}
                </div>
              </div>
            </Card>
          </div>

          {/* Statistiques */}
          <div>
            <h2 className="font-heading font-semibold text-[13px] text-gray-dk uppercase tracking-wide mb-3">
              Statistiques
            </h2>
            <Card padding="sm" className="space-y-2">
              <MetaRow label="Mots" value={article.corps ? wordCount(article.corps).toString() : '—'} />
              <MetaRow label="Source" value={article.source_nom ?? '—'} />
              <MetaRow label="Modèle LLM" value={article.llm_provider_used ?? '—'} />
              <MetaRow label="Créé" value={formatDate(article.created_at)} />
              {article.published_at && (
                <MetaRow label="Publié" value={formatDate(article.published_at)} />
              )}
            </Card>
          </div>

          {/* Source originale */}
          {article.source_url && (
            <div>
              <h2 className="font-heading font-semibold text-[13px] text-gray-dk uppercase tracking-wide mb-3">
                Source
              </h2>
              <Card padding="sm">
                <a
                  href={article.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-heading text-[12px] text-blue-txt hover:underline break-all"
                >
                  {article.source_url}
                </a>
              </Card>
            </div>
          )}

          {/* Actions HITL */}
          {article.status === 'PENDING_REVIEW' && (
            <div className="space-y-2">
              <Button
                variant="primary"
                size="lg"
                className="w-full"
                loading={approving}
                onClick={() => approve(undefined as unknown as void)}
              >
                ✓ Approuver et publier
              </Button>
              <Button
                variant="danger"
                size="md"
                className="w-full"
                onClick={() => setConfirmReject(true)}
              >
                Rejeter cet article
              </Button>
            </div>
          )}
        </aside>
      </div>

      {/* Modale confirmation rejet */}
      <Modal
        open={confirmReject}
        onClose={() => setConfirmReject(false)}
        title="Rejeter l'article"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setConfirmReject(false)}>Annuler</Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => { setConfirmReject(false); reject(undefined as unknown as void) }}
            >
              Confirmer le rejet
            </Button>
          </>
        }
      >
        <p className="font-heading text-[14px] text-gray-dk">
          Cet article sera marqué comme rejeté et ne sera pas publié sur WordPress. Cette action est irréversible.
        </p>
      </Modal>
    </div>
  )
}

// ── EditableField ─────────────────────────────────────────────────────────────

interface EditableFieldProps {
  tag: 'h1' | 'h2' | 'p' | 'div'
  value: string
  className?: string
  onSave: (value: string) => void
  placeholder?: string
  multiline?: boolean
}

function EditableField({ tag: Tag, value, className = '', onSave, placeholder, multiline }: EditableFieldProps) {
  const ref = useRef<HTMLElement>(null)
  const [editing, setEditing] = useState(false)
  // Le corps (multiline) contient du Markdown ("## sous-titre") — affiché en
  // clair (## visible) tant qu'aucun rendu n'était appliqué. En lecture, on
  // le rend en HTML propre ; au clic, on repasse en édition du texte brut
  // Markdown (c'est le format source, l'utilisateur édite toujours le
  // Markdown, seul l'AFFICHAGE change entre les deux modes).
  const isMarkdownView = multiline && !editing

  // Sync external changes when not editing (mode contentEditable uniquement)
  useEffect(() => {
    if (!editing && !isMarkdownView && ref.current && ref.current.innerText !== value) {
      ref.current.innerText = value || ''
    }
  }, [value, editing, isMarkdownView])

  const handleClick = () => {
    setEditing(true)
    setTimeout(() => ref.current?.focus(), 0)
  }

  const handleBlur = () => {
    setEditing(false)
    const newVal = ref.current?.innerText?.trim() ?? ''
    if (newVal !== value) onSave(newVal)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!multiline && e.key === 'Enter') {
      e.preventDefault()
      ref.current?.blur()
    }
    if (e.key === 'Escape') {
      if (ref.current) ref.current.innerText = value || ''
      ref.current?.blur()
    }
  }

  if (isMarkdownView) {
    return (
      <div
        onClick={handleClick}
        className={`${className} cursor-text hover:bg-orange/5 rounded transition-colors`}
        title="Cliquez pour modifier"
      >
        {value ? <ReactMarkdown>{value}</ReactMarkdown> : (
          <span className="text-gray-med">{placeholder}</span>
        )}
      </div>
    )
  }

  return (
    <Tag
      ref={ref as React.Ref<HTMLElement & HTMLDivElement>}
      contentEditable={editing}
      suppressContentEditableWarning
      onClick={handleClick}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      data-placeholder={placeholder}
      className={
        `${className} cursor-text hover:bg-orange/5 rounded transition-colors ` +
        `${!editing ? 'focus:outline-none' : ''} ` +
        `empty:before:content-[attr(data-placeholder)] empty:before:text-gray-med`
      }
      title="Cliquez pour modifier"
    />
  )
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="font-heading text-[11px] text-gray-med">{label}</span>
      <span className="font-heading text-[12px] text-anthracite font-medium text-right max-w-[60%] truncate">{value}</span>
    </div>
  )
}
