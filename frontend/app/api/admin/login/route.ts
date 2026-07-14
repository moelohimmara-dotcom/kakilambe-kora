import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const { secret } = await req.json().catch(() => ({}))

  const expected = process.env.ADMIN_SECRET_KEY
  // .trim() : même correctif que /api/auth/login — un espace ajouté par un
  // clavier mobile/auto-remplissage est invisible dans un champ masqué.
  if (!expected || !secret || secret.trim() !== expected.trim()) {
    return NextResponse.json({ error: 'Accès refusé' }, { status: 401 })
  }

  // Token = secret haché côté client (HMAC-SHA256 serait idéal en prod,
  // mais pour ce contexte on stocke le secret directement en cookie httpOnly)
  const res = NextResponse.json({ ok: true })
  res.cookies.set('kora_admin_token', secret, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/system',
    maxAge: 60 * 60 * 8, // 8h
  })
  return res
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true })
  res.cookies.delete('kora_admin_token')
  return res
}
