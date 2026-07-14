'use client'

import { ThemeProvider as NextThemesProvider } from 'next-themes'

// attribute="class" bascule la classe `dark` sur <html> — c'est cette
// classe que ciblent les overrides globaux de styles/globals.css (cf.
// `.dark .bg-white`, `.dark .text-anthracite`, etc.), qui retouchent
// l'app existante SANS modifier un seul composant (elle utilise des
// classes utilitaires Tailwind fixes, pas un système de tokens `dark:`).
// enableSystem=false : la source de vérité est le backend (table `users`,
// colonne theme), jamais la préférence système du navigateur.
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="light" enableSystem={false}>
      {children}
    </NextThemesProvider>
  )
}
