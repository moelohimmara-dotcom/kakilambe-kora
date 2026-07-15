// Root cause (2026-07-15, mise à jour après investigation approfondie) :
// AccountThemeSync se remonte (cleanup + effet relancé) chaque fois que la
// valeur de thème change réellement dans le contexte next-themes — y compris
// quand c'est SA PROPRE application d'une valeur qui déclenche ce changement.
// Avec l'ancienne version de cette garde (remise à `false` à chaque montage),
// chaque remontage relançait un nouveau GET /api/account/me ET réarmait la
// garde à false, ce qui pouvait laisser passer une réponse tardive et
// réappliquer une ancienne valeur — provoquant un rebond auto-entretenu
// (le thème change, ce qui remonte le composant, ce qui relance un fetch, qui
// réapplique une valeur, ce qui remonte à nouveau...) qui converge seulement
// après plusieurs allers-retours de quelques secondes. C'est ce rebond,
// pas une simple course initiale, qui se lisait comme un clignotement.
//
// Fix : ce flag devient un verrou À USAGE UNIQUE PAR CHARGEMENT DE PAGE,
// jamais réinitialisé par un remontage — seulement par un vrai rechargement
// (nouveau `globalThis`). Une fois posé à true (par la première synchronisation
// réussie OU par un choix manuel), AccountThemeSync ne retente plus jamais
// automatiquement pour le reste de la session de page, quel que soit le
// nombre de remontages qu'il subit ensuite.
//
// Backé par `globalThis` plutôt qu'un simple module-scope object : SettingsScreen
// et AccountThemeSync sont bundlés dans des chunks JS distincts par Next.js,
// et un module importé séparément par les deux peut se retrouver dupliqué par
// le code-splitting — `globalThis` est le seul espace garanti unique quel que
// soit le chunk qui y accède.
const g = globalThis as unknown as { __koraThemeOverride?: boolean }
export const themeOverride = {
  get current() { return g.__koraThemeOverride ?? false },
  set current(v: boolean) { g.__koraThemeOverride = v },
}
