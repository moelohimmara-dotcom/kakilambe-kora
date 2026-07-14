'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'

export default function LoginPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const data = new FormData(e.currentTarget)
    const email    = data.get('email') as string
    const password = data.get('password') as string

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (res.ok) {
        const params = new URLSearchParams(window.location.search)
        router.push(params.get('redirect') ?? '/dashboard')
      } else {
        const body = await res.json().catch(() => ({}))
        setError(body.detail || 'Identifiants incorrects')
      }
    } catch {
      setError('Connexion impossible — vérifiez votre réseau')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="font-heading font-extrabold text-4xl text-anthracite mb-2">
            <span className="text-orange">/</span>KORA
          </div>
          <p className="font-heading text-[13px] text-gray-dk">
            GuinéePress Intelligence · kakilambe.com
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl border border-gray-light shadow-card p-8">
          <h1 className="font-heading font-semibold text-[17px] text-anthracite mb-6">
            Connexion
          </h1>

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2"
              >
                Adresse e-mail
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                placeholder="vous@kakilambe.com"
                className="form-input"
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? 'login-error' : undefined}
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2"
              >
                Mot de passe
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  placeholder="••••••••"
                  className="form-input pr-16"
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? 'login-error' : undefined}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 font-heading text-[11px] font-semibold text-gray-dk uppercase tracking-wide"
                  tabIndex={-1}
                >
                  {showPassword ? 'Cacher' : 'Voir'}
                </button>
              </div>
            </div>

            {error && (
              <p
                id="login-error"
                role="alert"
                className="font-heading text-[12px] text-danger bg-danger/8 border border-danger/20 rounded-md px-3 py-2"
              >
                {error}
              </p>
            )}

            <Button
              type="submit"
              variant="confirm"
              size="lg"
              loading={loading}
              className="w-full mt-2"
            >
              {loading ? 'Connexion…' : 'Se connecter'}
            </Button>
          </form>
        </div>

        <p className="text-center font-heading text-[11px] text-gray-med mt-6">
          GuinéePress Intelligence — Phase 3
        </p>
      </div>
    </div>
  )
}
