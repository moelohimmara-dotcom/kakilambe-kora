'use client'

import { useEditor, EditorContent, Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Markdown } from 'tiptap-markdown'
import { Bold, Italic, Heading1, Heading2, List, ListOrdered } from 'lucide-react'

// Éditeur WYSIWYG réel (TipTap) — remplace l'ancien textarea + insertion de
// symboles Markdown littéraux. Le contenu s'affiche mis en forme pendant la
// frappe (gras/italique/titres/listes réellement rendus), pas de "**"/"##"
// visibles. Stockage inchangé : sérialise en Markdown au blur/update via
// tiptap-markdown, exactement le format déjà attendu par le backend et déjà
// rendu ailleurs via ReactMarkdown — aucune migration de données nécessaire.
//
// Non contrôlé au sens React classique : `content` n'initialise l'éditeur
// qu'au montage. Pour réinitialiser (ex. réouverture de l'overlay sur un
// autre article), le parent doit fournir une `key` différente plutôt que de
// compter sur un re-render avec un nouveau `content`.

interface RichTextEditorProps {
  content: string
  onChange: (markdown: string) => void
  placeholder?: string
  minHeightClass?: string
}

export function RichTextEditor({ content, onChange, placeholder, minHeightClass = 'min-h-[280px]' }: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2] } }),
      Placeholder.configure({ placeholder }),
      Markdown.configure({ html: false, transformPastedText: true }),
    ],
    content,
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class: `prose-article focus:outline-none ${minHeightClass}`,
      },
    },
    onUpdate: ({ editor }) => {
      const markdownStorage = (editor.storage as unknown as Record<string, { getMarkdown: () => string }>).markdown
      onChange(markdownStorage.getMarkdown())
    },
  })

  if (!editor) {
    return <div className={`form-input ${minHeightClass}`} />
  }

  return (
    <div>
      <Toolbar editor={editor} />
      <div className="form-input">
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}

function Toolbar({ editor }: { editor: Editor }) {
  return (
    <div className="flex gap-1 mb-1.5">
      <ToolbarButton title="Gras" active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}>
        <Bold size={15} aria-hidden="true" />
      </ToolbarButton>
      <ToolbarButton title="Italique" active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}>
        <Italic size={15} aria-hidden="true" />
      </ToolbarButton>
      <ToolbarButton title="Titre H1" active={editor.isActive('heading', { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}>
        <Heading1 size={15} aria-hidden="true" />
      </ToolbarButton>
      <ToolbarButton title="Titre H2" active={editor.isActive('heading', { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>
        <Heading2 size={15} aria-hidden="true" />
      </ToolbarButton>
      <ToolbarButton title="Liste à puces" active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}>
        <List size={15} aria-hidden="true" />
      </ToolbarButton>
      <ToolbarButton title="Liste numérotée" active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
        <ListOrdered size={15} aria-hidden="true" />
      </ToolbarButton>
    </div>
  )
}

function ToolbarButton({
  title, active, onClick, children,
}: {
  title: string
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-pressed={active}
      onClick={onClick}
      className={
        `w-8 h-8 flex items-center justify-center rounded-md border transition-colors ` +
        `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
        `${active ? 'bg-orange/10 border-orange text-orange' : 'border-gray-light text-gray-dk hover:bg-gray-pale hover:text-anthracite'}`
      }
    >
      {children}
    </button>
  )
}
