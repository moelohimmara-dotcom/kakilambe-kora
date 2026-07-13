// Couche stub — Corbeille (nouveau périmètre produit, validé explicitement).
//
// TODO backend : il n'existe aujourd'hui aucune colonne `ARCHIVED` ni
// `archived_at` sur la table `articles`, et `DELETE /api/articles/{id}`
// est un vrai DELETE SQL immédiat (voir backend/api/article_routes.py:296).
// Tant que le backend n'expose pas un vrai statut ARCHIVED + une purge
// planifiée, "Archiver" est une vue purement front-end : l'article réel
// n'est ni modifié ni supprimé en base, seul son id est masqué de la liste
// /articles et suivi ici (localStorage). "Purger" en revanche appelle le
// vrai endpoint DELETE existant — action réellement destructive.
//
// Endpoints réels à créer plus tard : POST /api/articles/{id}/archive,
// POST /api/articles/{id}/restore, avec un job planifié de purge à 72h.

import type { Article } from './types'
import { articleApi } from './api'

export interface TrashedItem {
  id: string
  article: Pick<Article, 'id' | 'titre' | 'chapeau' | 'image_url' | 'status' | 'source_nom' | 'created_at'>
  archived_at: string
  purge_at: string
}

const STORAGE_KEY = 'kora_trash_v1'
const RETENTION_MS = 72 * 60 * 60 * 1000

function readStore(): TrashedItem[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as TrashedItem[]) : []
  } catch {
    return []
  }
}

function writeStore(items: TrashedItem[]) {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

export const trashApi = {
  archivedIds(): Set<string> {
    return new Set(readStore().map(t => t.id))
  },

  async archiveArticle(article: Article): Promise<void> {
    const now = new Date()
    const item: TrashedItem = {
      id: article.id,
      article: {
        id: article.id,
        titre: article.titre,
        chapeau: article.chapeau,
        image_url: article.image_url,
        status: article.status,
        source_nom: article.source_nom,
        created_at: article.created_at,
      },
      archived_at: now.toISOString(),
      purge_at: new Date(now.getTime() + RETENTION_MS).toISOString(),
    }
    const items = readStore().filter(t => t.id !== article.id)
    writeStore([item, ...items])
  },

  // Auto-purge les entrées dont la rétention de 72h est écoulée (appel réel
  // au DELETE existant) avant de renvoyer la liste active.
  async listTrashed(): Promise<TrashedItem[]> {
    const items = readStore()
    const now = Date.now()
    const expired = items.filter(t => new Date(t.purge_at).getTime() <= now)
    const active = items.filter(t => new Date(t.purge_at).getTime() > now)

    if (expired.length > 0) {
      await Promise.all(expired.map(t => articleApi.delete(t.id).catch(() => {})))
      writeStore(active)
    }

    return active
  },

  // Retire l'article de la corbeille — il redevient visible normalement sur
  // /articles (son statut réel n'a jamais changé côté backend).
  async restoreItem(id: string): Promise<void> {
    writeStore(readStore().filter(t => t.id !== id))
  },

  // Purge manuelle anticipée — suppression réelle et immédiate (irréversible).
  async purgeItem(id: string): Promise<void> {
    await articleApi.delete(id)
    writeStore(readStore().filter(t => t.id !== id))
  },
}
