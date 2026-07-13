// Couche stub — Corbeille (nouveau périmètre produit, validé explicitement).
// D'après les wireframes fournis, la corbeille contient deux catégories
// d'articles, chacune avec sa propre rétention avant purge automatique :
//   - 'deleted'  → 72h (action "Supprimer")
//   - 'rejected' → 1h  (action "Rejeter")
// L'archivage ("Archiver") est un concept SÉPARÉ et persistant (voir
// lib/archiveApi.ts) — les articles archivés n'apparaissent jamais ici,
// seulement sous l'onglet "Archivés" de /articles.
//
// TODO backend : aucune colonne `rejected_at`/`deleted_at` n'existe sur
// `articles`, et DELETE /api/articles/{id} est un vrai DELETE SQL immédiat
// (voir backend/api/article_routes.py:296). Tant que le backend n'expose
// pas ces champs + une purge planifiée, cette rétention est un concept
// purement front-end (localStorage) : le statut réel de l'article
// (PENDING_REVIEW/REJECTED/etc.) n'est modifié que par les vrais appels
// API déjà existants (articleApi.reject/patch) ; "Supprimer" ne modifie
// RIEN côté backend tant que la purge n'a pas eu lieu.
// Endpoints réels à créer plus tard : POST /api/articles/{id}/trash,
// POST /api/articles/{id}/restore, job planifié de purge.

import type { Article } from './types'
import { articleApi } from './api'

export type TrashReason = 'deleted' | 'rejected'

export interface TrashedItem {
  id: string
  reason: TrashReason
  article: Pick<Article, 'id' | 'titre' | 'chapeau' | 'image_url' | 'status' | 'source_nom' | 'created_at'>
  trashed_at: string
  purge_at: string
}

const STORAGE_KEY = 'kora_trash_v2'
const RETENTION_MS: Record<TrashReason, number> = {
  deleted: 72 * 60 * 60 * 1000,
  rejected: 1 * 60 * 60 * 1000,
}

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
  trashedIds(): Set<string> {
    return new Set(readStore().map(t => t.id))
  },

  async sendToTrash(article: Article, reason: TrashReason): Promise<void> {
    const now = new Date()
    const item: TrashedItem = {
      id: article.id,
      reason,
      article: {
        id: article.id,
        titre: article.titre,
        chapeau: article.chapeau,
        image_url: article.image_url,
        status: article.status,
        source_nom: article.source_nom,
        created_at: article.created_at,
      },
      trashed_at: now.toISOString(),
      purge_at: new Date(now.getTime() + RETENTION_MS[reason]).toISOString(),
    }
    const items = readStore().filter(t => t.id !== article.id)
    writeStore([item, ...items])
  },

  // Auto-purge les entrées dont la rétention est écoulée (appel réel au
  // DELETE existant) avant de renvoyer la liste active.
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

  // Retire l'article de la corbeille. Pour un article rejeté, le vrai statut
  // backend est remis à PENDING_REVIEW (redonne une chance d'être revalidé) ;
  // pour un article "supprimé", son statut réel n'a jamais changé (le DELETE
  // n'a lieu qu'à la purge), il redevient simplement visible normalement.
  async restoreItem(id: string): Promise<void> {
    const item = readStore().find(t => t.id === id)
    if (item?.reason === 'rejected') {
      await articleApi.patch(id, { status: 'PENDING_REVIEW' }).catch(() => {})
    }
    writeStore(readStore().filter(t => t.id !== id))
  },

  // Purge manuelle anticipée — suppression réelle et immédiate (irréversible).
  async purgeItem(id: string): Promise<void> {
    await articleApi.delete(id)
    writeStore(readStore().filter(t => t.id !== id))
  },
}
