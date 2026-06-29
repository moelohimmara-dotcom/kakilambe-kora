import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const { email, password } = await req.json().catch(() => ({}))

  const adminKey = process.env.ADMIN_SECRET_KEY
  const adminEmail = process.env.ADMIN_EMAIL ?? 'mistermarcket@gmail.com'

  if (!adminKey || !email || !password) {
    return NextResponse.json({ detail: 'Identifiants manquants' }, { status: 401 })
  }

  const emailMatch = email.toLowerCase().trim() === adminEmail.toLowerCase()
  const passMatch  = password === adminKey

  if (!emailMatch || !passMatch) {
    return NextResponse.json({ detail: 'Identifiants incorrects' }, { status: 401 })
  }

  const res = NextResponse.json({ ok: true })
  res.cookies.set('kora_session', adminKey, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
    maxAge: 60 * 60 * 8, // 8h
  })
  return res
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true })
  res.cookies.delete('kora_session')
  return res
}
