import { Suspense } from 'react'
import { ArticlesScreen } from '@/components/screens/ArticlesScreen'

export const metadata = { title: 'Articles · /KORA' }

export default function ArticlesPage() {
  return (
    <Suspense fallback={null}>
      <ArticlesScreen />
    </Suspense>
  )
}
