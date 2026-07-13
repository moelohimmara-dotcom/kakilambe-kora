// Couche stub/typée — régénération scindée texte/visuel (nouveau périmètre
// produit, validé explicitement). Isolée de lib/api.ts pour ne jamais faire
// supposer aux composants que ces fonctions sont mockées inline.

import { articleApi } from './api'

export interface RegenVersions { text: number; visual: number }

const STORAGE_PREFIX = 'kora_regen_version_'

function readVersions(id: string): RegenVersions {
  if (typeof window === 'undefined') return { text: 1, visual: 1 }
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + id)
    return raw ? (JSON.parse(raw) as RegenVersions) : { text: 1, visual: 1 }
  } catch {
    return { text: 1, visual: 1 }
  }
}

function writeVersions(id: string, v: RegenVersions) {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_PREFIX + id, JSON.stringify(v))
}

export const regenerationApi = {
  getVersions(id: string): RegenVersions {
    return readVersions(id)
  },

  // Réel — enveloppe l'endpoint existant et déjà isolé à l'image côté
  // backend (POST /api/articles/{id}/regenerate-image), aucune donnée
  // mockée nécessaire ici. Le compteur de version, en revanche, est un
  // concept purement front-end (localStorage) tant qu'aucune colonne
  // `visual_version` n'existe sur `articles`.
  async regenerateVisual(id: string): Promise<{ image_url: string; wp_media_id: number; version: number }> {
    const result = await articleApi.regenerateImage(id)
    const versions = readVersions(id)
    versions.visual += 1
    writeVersions(id, versions)
    return { ...result, version: versions.visual }
  },

  // Réel — appelle le vrai endpoint existant et testé (POST
  // /api/articles/{id}/regenerate, cf. test_regenerate_live.py 7/7). Ne
  // JAMAIS remplacer par un mock : c'est la fonctionnalité phare du produit
  // (boucle de régénération HITL) — la régresser silencieusement pour
  // satisfaire le découpage texte/visuel serait une perte de capacité réelle.
  //
  // Limitation honnête : cet endpoint réécrit systématiquement le texte ET
  // l'image ensemble côté backend (voir backend/api/article_routes.py:175 —
  // _write_with_retry() PUIS generate_and_upload_image()) ; il n'existe pas
  // encore d'endpoint isolant le texte seul.
  // TODO backend : créer POST /api/articles/{id}/regenerate-text,
  // réutilisant uniquement _write_with_retry() sans toucher à l'image, pour
  // que ce bouton n'ait plus cet effet de bord sur le visuel.
  async regenerateText(id: string): Promise<{ id: string; titre: string; chapeau: string; corps: string; image_url: string | null; version: number }> {
    const result = await articleApi.regenerate(id)
    const versions = readVersions(id)
    versions.text += 1
    writeVersions(id, versions)
    return { ...result, version: versions.text }
  },
}
