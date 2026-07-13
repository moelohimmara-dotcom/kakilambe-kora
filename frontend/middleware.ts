import { NextRequest, NextResponse } from 'next/server'

const SESSION_COOKIE = 'kora_session'
const ADMIN_COOKIE   = 'kora_admin_token'

const PUBLIC_PATHS = ['/login', '/setup', '/system/login', '/api/auth', '/api/admin']

// Faille corrigée : ce middleware ne comparait le cookie qu'à sa LONGUEUR
// (`token.length < 8`), jamais à sa valeur réelle. `/api/admin/login` et
// `/api/auth/login` posent tous deux le cookie = ADMIN_SECRET_KEY en clair
// (même secret partagé pour les deux espaces) — n'importe quelle chaîne de
// 8+ caractères nommée kora_admin_token/kora_session contournait donc
// entièrement l'authentification de /system/* ET du groupe éditorial,
// puisque rien ne revalidait jamais la valeur côté serveur après la pose du
// cookie. Comparaison en temps constant (timingSafeEqualString) pour éviter
// qu'un timing attack sur la comparaison ne révèle le secret caractère par
// caractère.
function timingSafeEqualString(a: string, b: string): boolean {
  if (a.length !== b.length) return false
  let mismatch = 0
  for (let i = 0; i < a.length; i++) {
    mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i)
  }
  return mismatch === 0
}

function hasValidSecret(request: NextRequest, cookieName: string): boolean {
  const expected = process.env.ADMIN_SECRET_KEY
  if (!expected) return false
  const token = request.cookies.get(cookieName)?.value
  if (!token) return false
  return timingSafeEqualString(token, expected)
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Laisser passer les routes publiques et assets
  if (
    PUBLIC_PATHS.some(p => pathname.startsWith(p)) ||
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon')
  ) {
    return NextResponse.next()
  }

  // Routes /system/** → cookie admin, revalidé contre le vrai secret
  if (pathname.startsWith('/system')) {
    if (!hasValidSecret(request, ADMIN_COOKIE)) {
      const url = new URL('/system/login', request.url)
      url.searchParams.set('redirect', pathname)
      return NextResponse.redirect(url)
    }
    return NextResponse.next()
  }

  // Routes éditoriales → cookie session, revalidé contre le vrai secret
  if (!hasValidSecret(request, SESSION_COOKIE)) {
    const url = new URL('/login', request.url)
    url.searchParams.set('redirect', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
