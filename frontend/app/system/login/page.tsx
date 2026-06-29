'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

function AdminLoginInner() {
  const router = useRouter()
  const params = useSearchParams()
  const redirect = params.get('redirect') ?? '/system'
  const inputRef = useRef<HTMLInputElement>(null)

  const [secret, setSecret]   = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [attempts, setAttempts] = useState(0)

  useEffect(() => { inputRef.current?.focus() }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!secret.trim() || loading || attempts >= 5) return

    setLoading(true)
    setError('')

    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret }),
      })

      if (res.ok) {
        router.replace(redirect)
      } else {
        setAttempts(a => a + 1)
        setError(attempts >= 4 ? 'Trop de tentatives — accès bloqué' : 'Clé incorrecte')
        setSecret('')
      }
    } catch {
      setError('Erreur réseau')
    } finally {
      setLoading(false)
    }
  }

  const locked = attempts >= 5

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: '#0c0c0b' }}
    >
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded bg-red-600 flex items-center justify-center">
              <span className="font-mono text-white font-bold text-sm">SYS</span>
            </div>
          </div>
          <h1 className="font-mono font-bold text-xl text-white">/KORA — System</h1>
          <p className="font-mono text-[11px] text-red-500 mt-1 tracking-widest uppercase">
            Zone réservée — Accès restreint
          </p>
        </div>

        <div
          className="rounded-xl border p-8"
          style={{ background: '#141413', borderColor: '#2a2a28' }}
        >
          <form onSubmit={handleSubmit} noValidate>
            <label
              htmlFor="admin-secret"
              className="block font-mono text-[11px] text-red-400 uppercase tracking-widest mb-3"
            >
              Clé d'accès administrateur
            </label>

            <input
              id="admin-secret"
              ref={inputRef}
              type="password"
              value={secret}
              onChange={e => setSecret(e.target.value)}
              disabled={locked || loading}
              autoComplete="current-password"
              className="w-full px-4 py-3 rounded-lg font-mono text-[14px] text-white bg-[#0c0c0b] border border-[#2a2a28] focus:border-red-600 focus:outline-none transition-colors disabled:opacity-40 mb-4"
              placeholder="••••••••••••••••"
              aria-describedby={error ? 'admin-error' : undefined}
            />

            {error && (
              <p
                id="admin-error"
                role="alert"
                className="font-mono text-[12px] text-red-500 mb-4"
              >
                ✕ {error}
              </p>
            )}

            {locked ? (
              <div className="font-mono text-[12px] text-red-500 text-center py-3 border border-red-900 rounded-lg bg-red-950/30">
                Session verrouillée — rechargez la page
              </div>
            ) : (
              <button
                type="submit"
                disabled={!secret.trim() || loading}
                className="w-full py-3 rounded-lg font-mono font-bold text-[13px] bg-red-700 text-white hover:bg-red-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              >
                {loading ? 'Vérification…' : 'Accéder au système'}
              </button>
            )}
          </form>
        </div>

        <p className="font-mono text-[10px] text-[#444] text-center mt-6">
          GuinéePress Intelligence · Niveau d'accès : SYSTEM
        </p>
      </div>
    </div>
  )
}

export default function AdminLoginPage() {
  return (
    <Suspense>
      <AdminLoginInner />
    </Suspense>
  )
}
