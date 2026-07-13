'use client'

import { useEffect, useRef, useState } from 'react'
import { Modal } from './Modal'
import { Button } from './Button'
import type { Article } from '@/lib/types'

// Overlay d'édition manuelle (nouveau périmètre produit, validé
// explicitement) — distinct de l'édition inline existante (EditableField
// dans ArticleEditorScreen.tsx, conservée telle quelle). Fournit une barre
// d'outils Markdown (gras/italique/titre/liste) sur titre/chapeau/corps/SEO.
//
// Note honnête : seul le champ "corps" est réellement rendu en Markdown
// ailleurs dans l'application (via ReactMarkdown). "Titre" et
// "Méta-description SEO" sont des champs texte brut envoyés tels quels à
// WordPress/aux moteurs de recherche — y insérer des symboles Markdown
// (**gras**) les ferait apparaître littéralement en production. La barre
// d'outils reste disponible partout comme demandé, avec un avertissement
// inline sur ces deux champs plutôt qu'une omission silencieuse.

export interface ManualEditFields {
  titre: string
  chapeau: string
  corps: string
  meta_description: string
}

interface ManualEditOverlayProps {
  open: boolean
  onClose: () => void
  article: Pick<Article, 'titre' | 'chapeau' | 'corps' | 'meta_description'>
  onSave: (fields: ManualEditFields) => Promise<void>
  saving: boolean
}

export function ManualEditOverlay({ open, onClose, article, onSave, saving }: ManualEditOverlayProps) {
  const [fields, setFields] = useState<ManualEditFields>({
    titre: article.titre ?? '',
    chapeau: article.chapeau ?? '',
    corps: article.corps ?? '',
    meta_description: article.meta_description ?? '',
  })

  // Resynchronise à chaque ouverture (pas à chaque frappe) pour repartir du
  // contenu réel courant, y compris si l'article a changé entre-temps.
  useEffect(() => {
    if (open) {
      setFields({
        titre: article.titre ?? '',
        chapeau: article.chapeau ?? '',
        corps: article.corps ?? '',
        meta_description: article.meta_description ?? '',
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  async function handleSave() {
    await onSave(fields)
  }

  return (
    <Modal open={open} onClose={onClose} title="Édition manuelle" size="lg">
      <div className="space-y-5 max-h-[65vh] overflow-y-auto pr-1">
        <MarkdownField
          label="Titre"
          value={fields.titre}
          onChange={v => setFields(p => ({ ...p, titre: v }))}
          rows={2}
          warnPlainText
        />
        <MarkdownField
          label="Chapeau"
          value={fields.chapeau}
          onChange={v => setFields(p => ({ ...p, chapeau: v }))}
          rows={3}
        />
        <MarkdownField
          label="Corps"
          value={fields.corps}
          onChange={v => setFields(p => ({ ...p, corps: v }))}
          rows={12}
        />
        <MarkdownField
          label="Méta-description SEO"
          value={fields.meta_description}
          onChange={v => setFields(p => ({ ...p, meta_description: v }))}
          rows={2}
          warnPlainText
        />
      </div>

      <div className="flex items-center justify-end gap-3 mt-5 pt-4 border-t border-gray-pale">
        <Button variant="ghost" size="sm" disabled={saving} onClick={onClose}>Annuler</Button>
        <Button variant="primary" size="sm" loading={saving} onClick={handleSave}>
          Enregistrer
        </Button>
      </div>
    </Modal>
  )
}

// ── Champ avec barre d'outils Markdown ──────────────────────────────────────

function MarkdownField({
  label, value, onChange, rows, warnPlainText,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  rows: number
  warnPlainText?: boolean
}) {
  const ref = useRef<HTMLTextAreaElement>(null)

  function wrapSelection(before: string, after: string) {
    const el = ref.current
    if (!el) return
    const { selectionStart: start, selectionEnd: end } = el
    const selected = value.slice(start, end)
    const next = value.slice(0, start) + before + selected + after + value.slice(end)
    onChange(next)
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(start + before.length, start + before.length + selected.length)
    })
  }

  function prefixLines(prefix: string) {
    const el = ref.current
    if (!el) return
    const { selectionStart: start, selectionEnd: end } = el
    const lineStart = value.lastIndexOf('\n', start - 1) + 1
    const before = value.slice(0, lineStart)
    const target = value.slice(lineStart, end)
    const after = value.slice(end)
    const transformed = target.split('\n').map(l => prefix + l).join('\n')
    onChange(before + transformed + after)
    requestAnimationFrame(() => el.focus())
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide">
          {label}
        </label>
        <div className="flex gap-1">
          <ToolbarButton title="Gras" onClick={() => wrapSelection('**', '**')}><strong>G</strong></ToolbarButton>
          <ToolbarButton title="Italique" onClick={() => wrapSelection('*', '*')}><em>I</em></ToolbarButton>
          <ToolbarButton title="Titre" onClick={() => prefixLines('## ')}>H</ToolbarButton>
          <ToolbarButton title="Liste" onClick={() => prefixLines('- ')}>•</ToolbarButton>
        </div>
      </div>
      {warnPlainText && (
        <p className="font-heading text-[10px] text-gray-med mb-1.5">
          Champ texte brut (WordPress/SEO) — la mise en forme Markdown n&apos;y est pas rendue, évitez-la ici.
        </p>
      )}
      <textarea
        ref={ref}
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={rows}
        className="form-input font-mono text-[12px] resize-y w-full"
        aria-label={label}
      />
    </div>
  )
}

function ToolbarButton({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className="w-8 h-8 flex items-center justify-center rounded-md border border-gray-light text-[12px] text-gray-dk hover:bg-gray-pale hover:text-anthracite transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange"
    >
      {children}
    </button>
  )
}
