import { Suspense } from 'react'
import { ArticleEditorScreen } from '@/components/screens/ArticleEditorScreen'

export const metadata = { title: "Éditeur d'article · /KORA" }

export default async function ArticleEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return (
    <Suspense fallback={null}>
      <ArticleEditorScreen id={id} />
    </Suspense>
  )
}
