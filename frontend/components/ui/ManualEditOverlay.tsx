'use client'

import { useEffect, useState } from 'react'
import { Modal } from './Modal'
import { Button } from './Button'
import { ProgressRing } from './ProgressRing'
import { RichTextEditor } from './RichTextEditor'
import type { Article } from '@/lib/types'

// Overlay d'édition manuelle (nouveau périmètre produit, validé
// explicitement) — distinct de l'édition inline existante (EditableField
// dans ArticleEditorScreen.tsx, conservée telle quelle).
//
// Seul le "Corps" passe par un vrai éditeur WYSIWYG (RichTextEditor, TipTap)
// — c'est le seul champ réellement rendu en Markdown ailleurs dans
// l'application (via ReactMarkdown). "Titre" et "Méta-description SEO" sont
// des champs texte brut envoyés tels quels à WordPress/aux moteurs de
// recherche : y appliquer du gras/italique produirait des symboles Markdown
// littéraux dans un titre de publication ou une meta-tag, donc ils restent
// en simple texte. "Chapeau" n'est pas non plus rendu en Markdown ailleurs
// (affiché en italique via CSS fixe, pas de formatage riche) — texte simple
// également.

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
  // RichTextEditor n'est pas un composant contrôlé (TipTap n'aime pas
  // recevoir un nouveau `content` à chaque frappe) — ce compteur force son
  // remontage uniquement à l'ouverture, pour repartir du contenu réel.
  const [sessionKey, setSessionKey] = useState(0)

  useEffect(() => {
    if (open) {
      setFields({
        titre: article.titre ?? '',
        chapeau: article.chapeau ?? '',
        corps: article.corps ?? '',
        meta_description: article.meta_description ?? '',
      })
      setSessionKey(k => k + 1)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  async function handleSave() {
    await onSave(fields)
  }

  // Gamification (nouveau périmètre) — complétude SEO cosmétique.
  const seoChecks = [
    fields.titre.trim().length > 0,
    fields.chapeau.trim().length > 0,
    fields.corps.trim().length > 50,
    fields.meta_description.trim().length > 0 && fields.meta_description.length <= 155,
  ]
  const seoScore = seoChecks.filter(Boolean).length

  return (
    <Modal open={open} onClose={onClose} title="Édition manuelle" size="lg">
      <div className="flex items-center justify-end -mt-2 mb-3">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-dashed border-lavender bg-lavender-pale">
          <ProgressRing value={seoScore} max={seoChecks.length} size={28} label="Complétude SEO" />
          <span className="font-heading text-[11px] text-anthracite">Complétude SEO</span>
        </div>
      </div>

      <div className="space-y-5 max-h-[65vh] overflow-y-auto pr-1">
        <PlainField
          label="Titre"
          value={fields.titre}
          onChange={v => setFields(p => ({ ...p, titre: v }))}
        />
        <PlainField
          label="Chapeau"
          value={fields.chapeau}
          onChange={v => setFields(p => ({ ...p, chapeau: v }))}
          multiline
        />

        <div>
          <label className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-1.5">
            Corps
          </label>
          <RichTextEditor
            key={sessionKey}
            content={fields.corps}
            onChange={v => setFields(p => ({ ...p, corps: v }))}
            placeholder="Corps de l'article…"
          />
        </div>

        <div>
          <PlainField
            label="Méta-description SEO"
            value={fields.meta_description}
            onChange={v => setFields(p => ({ ...p, meta_description: v }))}
            multiline
          />
          <span className={`font-heading text-[10px] ${fields.meta_description.length > 155 ? 'text-danger' : 'text-gray-med'}`}>
            {fields.meta_description.length}/155
          </span>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 mt-5 pt-4 border-t border-gray-pale">
        <Button variant="ghost" size="sm" disabled={saving} onClick={onClose}>Annuler</Button>
        <Button variant="confirm" size="sm" loading={saving} onClick={handleSave}>
          Enregistrer
        </Button>
      </div>
    </Modal>
  )
}

// Champ texte brut (pas de Markdown) — titre/chapeau/méta-description sont
// envoyés tels quels à WordPress/aux moteurs de recherche, du formatage riche
// y produirait des symboles littéraux plutôt qu'un rendu.
function PlainField({
  label, value, onChange, multiline,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  multiline?: boolean
}) {
  return (
    <div>
      <label className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-1.5">
        {label}
      </label>
      {multiline ? (
        <textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          rows={2}
          className="form-input w-full"
          aria-label={label}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          className="form-input w-full"
          aria-label={label}
        />
      )}
    </div>
  )
}
