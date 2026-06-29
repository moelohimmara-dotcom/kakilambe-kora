import { NextRequest, NextResponse } from 'next/server'

const SESSION_COOKIE = 'kora_session'
const ADMIN_COOKIE   = 'kora_admin_token'

const PUBLIC_PATHS = ['/login', '/setup', '/system/login', '/api/auth', '/api/admin']

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

  // Routes /system/** → cookie admin
  if (pathname.startsWith('/system')) {
    const token = request.cookies.get(ADMIN_COOKIE)?.value
    if (!token || token.length < 8) {
      const url = new URL('/system/login', request.url)
      url.searchParams.set('redirect', pathname)
      return NextResponse.redirect(url)
    }
    return NextResponse.next()
  }

  // Routes éditoriales → cookie session
  const session = request.cookies.get(SESSION_COOKIE)?.value
  if (!session || session.length < 8) {
    const url = new URL('/login', request.url)
    url.searchParams.set('redirect', pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
