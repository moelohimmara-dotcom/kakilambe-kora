'use client'

import { useEffect } from 'react'
import { useTheme } from 'next-themes'
import { accountApi } from '@/lib/api'
import { themeOverride } from '@/lib/theme/themeOverride'

// Root cause à éviter (cf. exemple "comportement_a_eviter" de la demande) :
// un thème stocké seulement en localStorage navigateur rend impossible
// toute consultation/modification par un admin système. next-themes gère
// déjà un cache localStorage pour un rendu instantané sans flash, mais la
// VRAIE source de vérité reste le backend — resynchronisée ici à chaque
// chargement de page (et donc après une reconnexion), pour qu'un
// changement fait ailleurs (ex. par un admin via /api/account/admin/users)
// se reflète bien au prochain chargement, pas seulement sur l'appareil qui
// a fait le changement.
export function AccountThemeSync() {
  const { setTheme } = useTheme()

  useEffect(() => {
    let cancelled = false
    themeOverride.current = false
    accountApi.me()
      .then(account => {
        // Si un changement manuel a eu lieu pendant que cette requête était
        // en vol, cette réponse est déjà obsolète — l'appliquer reviendrait
        // à écraser un choix plus récent (cf. themeOverride.ts).
        if (!cancelled && !themeOverride.current) setTheme(account.theme)
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
