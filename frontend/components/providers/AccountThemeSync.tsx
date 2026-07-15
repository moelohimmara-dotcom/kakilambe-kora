'use client'

import { useEffect } from 'react'
import { useTheme } from 'next-themes'
import { accountApi } from '@/lib/api'
import { themeOverride } from '@/lib/theme/themeOverride'

// Root cause à éviter (cf. exemple "comportement_a_eviter" de la demande) :
// un thème stocké seulement en localStorage navigateur rend impossible
// toute consultation/modification par un admin système. next-themes gère
// déjà un cache localStorage pour un rendu instantané sans flash, mais la
// VRAIE source de vérité reste le backend — resynchronisée ici une seule
// fois par chargement de page (et donc après une reconnexion), pour qu'un
// changement fait ailleurs (ex. par un admin via /api/account/admin/users)
// se reflète bien au prochain chargement, pas seulement sur l'appareil qui
// a fait le changement.
//
// Le flag `themeOverride` n'est JAMAIS remis à false ici (cf.
// lib/theme/themeOverride.ts) : le remettre à false à chaque montage est ce
// qui causait le rebond observé en conditions réelles (ce composant se
// remonte à chaque changement réel de thème, y compris ceux qu'il vient
// lui-même de déclencher — remettre la garde à false à ce moment-là laissait
// passer une resynchronisation en boucle). Ici, on vérifie simplement une
// fois si un sync ou un choix a déjà eu lieu cette session ; si non, on
// synchronise et on verrouille pour le reste de la session de page.
export function AccountThemeSync() {
  const { setTheme } = useTheme()

  useEffect(() => {
    if (themeOverride.current) return
    let cancelled = false
    accountApi.me()
      .then(account => {
        if (!cancelled && !themeOverride.current) {
          setTheme(account.theme)
          themeOverride.current = true
        }
      })
      .catch(() => {
        // Non authentifié ou erreur réseau — laisse next-themes sur sa
        // valeur par défaut/locale, le middleware gère déjà la redirection
        // login si nécessaire.
      })
    return () => { cancelled = true }
  }, [setTheme])

  return null
}
