// Root cause (2026-07-15) : au chargement d'une page, AccountThemeSync lance
// GET /api/account/me pour resynchroniser le thème depuis le backend (source
// de vérité, cf. AccountThemeSync.tsx). Si l'utilisateur clique sur
// Clair/Sombre AVANT que cette requête ne réponde (VPS avec latence réseau
// réelle de l'ordre de la seconde), le setTheme() manuel s'applique
// instantanément, puis la réponse tardive de ce fetch — qui reflète encore
// l'ANCIEN thème lu au moment où elle a été lancée — écrase le choix qui
// vient d'être fait. Résultat observé : la page bascule sur le thème choisi,
// puis "clignote" en revenant sur l'ancien 1-2s plus tard.
//
// Ce ref partagé, posé à true dès qu'un changement de thème est déclenché
// manuellement (ThemeSection), indique à AccountThemeSync qu'un choix plus
// récent que sa propre requête en vol existe déjà — elle doit alors ignorer
// sa réponse au lieu de l'appliquer. Remis à false à chaque montage de page
// (rechargement/reconnexion), pour que la resynchronisation normale depuis
// le backend continue de fonctionner dans tous les autres cas.
//
// Backé par `window` plutôt qu'un simple module-scope object : SettingsScreen
// et AccountThemeSync sont bundlés dans des chunks JS distincts par Next.js
// (l'un dans le chunk de la page /settings, l'autre dans celui du layout
// éditorial) — un module importé séparément par les deux peut se retrouver
// dupliqué par le code-splitting, auquel cas chaque côté mute SA PROPRE copie
// de l'objet sans jamais se voir. Constaté en conditions réelles : la garde
// posée sur un simple module-scope object n'empêchait pas un second
// écrasement tardif. `window` est le seul espace garanti unique quel que
// soit le chunk qui y accède.
const g = globalThis as unknown as { __koraThemeOverride?: boolean }
export const themeOverride = {
  get current() { return g.__koraThemeOverride ?? false },
  set current(v: boolean) { g.__koraThemeOverride = v },
}
