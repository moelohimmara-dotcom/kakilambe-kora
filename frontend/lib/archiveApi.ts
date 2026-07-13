// Couche stub — Archivage persistant (nouveau périmètre produit).
// D'après les wireframes fournis, "Archiver" est distinct de la corbeille :
// un article archivé reste visible indéfiniment sous l'onglet "Archivés" de
// /articles (pas de compte à rebours de purge), contrairement aux articles
// rejetés/supprimés qui passent par lib/trashApi.ts.
//
// TODO backend : aucune colonne ARCHIVED n'existe sur `articles` (voir
// backend/db/migrations/001_init.sql) — tant qu'elle n'existe pas, ce suivi
// reste purement front-end (localStorage), invisible d'un navigateur à
// l'autre. Endpoint réel à créer : POST/DELETE /api/articles/{id}/archive.

const STORAGE_KEY = 'kora_archived_v1'

function readStore(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function writeStore(ids: string[]) {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
}

export const archiveApi = {
  archivedIds(): Set<string> {
    return new Set(readStore())
  },

  async archiveArticle(id: string): Promise<void> {
    const ids = readStore()
    if (!ids.includes(id)) writeStore([...ids, id])
  },

  async unarchiveArticle(id: string): Promise<void> {
    writeStore(readStore().filter(x => x !== id))
  },
}
