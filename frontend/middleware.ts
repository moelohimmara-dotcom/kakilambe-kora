import { NextRequest, NextResponse } from 'next/server'
import { jwtVerify } from 'jose'

const SESSION_COOKIE = 'kora_session'
const ADMIN_COOKIE   = 'kora_admin_token'

const PUBLIC_PATHS = ['/login', '/setup', '/system/login', '/api/auth', '/api/admin']

// Migration 2026-07-14 (table `users` réelle, cf. backend/db/migrations/010_users_table.sql) :
// les cookies ne contiennent plus le secret ADMIN_SECRET_KEY en clair — ce
// design comparait un cookie directement à une variable d'environnement
// STATIQUE, ce qui aurait rendu tout changement de mot de passe en base
// invisible ici (jamais revérifié). Remplacé par un jeton signé HS256
// (format JWT standard, émis par backend/core/security.py) : la validité
// se vérifie par SIGNATURE uniquement, sans appel DB depuis l'Edge Runtime,
// tout en reflétant réellement le mot de passe actuel de l'utilisateur
// (la signature ne peut être forgée sans connaître la clé de signature).
function getSigningKey(): Uint8Array {
  const secret = process.env.SESSION_JWT_SECRET || process.env.ADMIN_SECRET_KEY || ''
  return new TextEncoder().encode(secret)
}

async function verifySessionCookie(request: NextRequest, cookieName: string): Promise<boolean> {
  const token = request.cookies.get(cookieName)?.value
  if (!token) return false
  const secret = getSigningKey()
  if (secret.length === 0) return false
  try {
    await jwtVerify(token, secret, { algorithms: ['HS256'] })
    return true
  } catch {
    return false
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Laisser passer les routes publiques et assets
  if (
    PUBLIC_PATHS.some(p => pathname.startsWith(p)) ||
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon')
  ) {
    return NextResponse.next()
  }

  // Routes /system/** → cookie admin, revalidé par signature JWT
  if (pathname.startsWith('/system')) {
    if (!(await verifySessionCookie(request, ADMIN_COOKIE))) {
      const url = new URL('/system/login', request.url)
      url.searchParams.set('redirect', pathname)
      return NextResponse.redirect(url)
    }
    return NextResponse.next()
  }

  // Routes éditoriales → cookie session, revalidé par signature JWT
  if (!(await verifySessionCookie(request, SESSION_COOKIE))) {
    const url = new URL('/login', request.url)
    url.searchParams.set('redirect', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
