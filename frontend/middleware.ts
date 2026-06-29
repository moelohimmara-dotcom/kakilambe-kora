import { NextRequest, NextResponse } from 'next/server'

const ADMIN_COOKIE = 'kora_admin_token'

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Routes /system/** sauf /system/login
  if (pathname.startsWith('/system') && !pathname.startsWith('/system/login')) {
    const token = request.cookies.get(ADMIN_COOKIE)?.value

    if (!token || token.length < 8) {
      const loginUrl = new URL('/system/login', request.url)
      loginUrl.searchParams.set('redirect', pathname)
      return NextResponse.redirect(loginUrl)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/system/:path*'],
}
