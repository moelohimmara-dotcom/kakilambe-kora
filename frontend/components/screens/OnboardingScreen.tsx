'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useToast } from '@/lib/contexts/ToastContext'
import { settingsApi, healthApi } from '@/lib/api'

type Step = 'welcome' | 'wordpress' | 'sources' | 'done'

interface WPForm { url: string; username: string; password: string }
interface SourceForm { name: string; url: string }

const DEFAULT_SOURCES: SourceForm[] = [
  { name: 'Guinée Conakry Info', url: 'https://www.guineematin.com/feed/' },
  { name: 'Africa News', url: 'https://fr.africanews.com/rss/' },
  { name: 'Jeune Afrique', url: 'https://www.jeuneafrique.com/feed/' },
]

export function OnboardingScreen() {
  const router = useRouter()
  const { show } = useToast()
  const [step, setStep] = useState<Step>('welcome')
  const [wp, setWp] = useState<WPForm>({ url: '', username: '', password: '' })
  const [sources, setSources] = useState<SourceForm[]>(DEFAULT_SOURCES)
  const [newSource, setNewSource] = useState<SourceForm>({ name: '', url: '' })
  const [testing, setTesting] = useState(false)
  const [wpStatus, setWpStatus] = useState<'idle' | 'ok' | 'fail'>('idle')
  const [saving, setSaving] = useState(false)

  const STEPS: Step[] = ['welcome', 'wordpress', 'sources', 'done']
  const stepIndex = STEPS.indexOf(step)

  async function testWP() {
    if (!wp.url || !wp.username || !wp.password) {
      show('Remplissez tous les champs', 'error')
      return
    }
    setTesting(true)
    setWpStatus('idle')
    try {
      await settingsApi.patch({ wp_url: wp.url, wp_username: wp.username, wp_app_password: wp.password })
      const health = await healthApi.check() as { services?: Record<string, string> }
      setWpStatus(health.services?.wordpress === 'ok' ? 'ok' : 'fail')
    } catch {
      setWpStatus('fail')
    } finally {
      setTesting(false)
    }
  }

  async function finishSetup() {
    setSaving(true)
    try {
      for (const src of sources) {
        await settingsApi.createSource({ name: src.name, url: src.url }).catch(() => {})
      }
      show('Configuration terminée !', 'success')
      setStep('done')
    } catch {
      show('Erreur lors de la sauvegarde', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="font-heading font-extrabold text-4xl text-anthracite mb-2">
            <span className="text-orange">/</span>KORA
          </div>
          <p className="font-heading text-[13px] text-gray-dk">Configuration initiale</p>
        </div>

        {/* Progress */}
        <div className="flex items-center gap-2 mb-8 justify-center">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center font-heading text-[11px] font-bold transition-colors ${
                i < stepIndex ? 'bg-sage text-white' :
                i === stepIndex ? 'bg-orange text-white' :
                'bg-gray-pale text-gray-med'
              }`}>
                {i < stepIndex ? '✓' : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={`h-0.5 w-8 transition-colors ${i < stepIndex ? 'bg-sage' : 'bg-gray-pale'}`} />
              )}
            </div>
          ))}
        </div>

        {/* Step: Welcome */}
        {step === 'welcome' && (
          <Card>
            <h1 className="font-heading font-bold text-xl text-anthracite mb-3">Bienvenue !</h1>
            <p className="font-body text-[14px] text-gray-dk leading-relaxed mb-2">
              <strong>/KORA</strong> est votre assistant journalistique IA pour <strong>kakilambe.com</strong>.
            </p>
            <p className="font-body text-[14px] text-gray-dk leading-relaxed mb-6">
              En quelques étapes, nous allons configurer votre connexion WordPress et vos sources d'actualité.
            </p>
            <ul className="space-y-2 mb-8">
              {['Connexion WordPress', 'Sources RSS Guinée/Afrique', 'Premier cycle IA'].map((item, i) => (
                <li key={i} className="flex items-center gap-3 font-heading text-[13px] text-anthracite">
                  <span className="w-5 h-5 rounded-full bg-orange/20 flex items-center justify-center text-[10px] font-bold text-orange">{i + 1}</span>
                  {item}
                </li>
              ))}
            </ul>
            <Button variant="primary" size="lg" className="w-full" onClick={() => setStep('wordpress')}>
              Commencer la configuration
            </Button>
          </Card>
        )}

        {/* Step: WordPress */}
        {step === 'wordpress' && (
          <Card>
            <h2 className="font-heading font-bold text-xl text-anthracite mb-1">WordPress</h2>
            <p className="font-body text-[13px] text-gray-dk mb-5">
              Connectez KORA à votre WordPress pour publier automatiquement.
            </p>
            <div className="space-y-4 mb-5">
              <div>
                <label htmlFor="ob-url" className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2">URL du site</label>
                <input id="ob-url" type="url" value={wp.url} onChange={e => setWp(p => ({ ...p, url: e.target.value }))} placeholder="https://kakilambe.com" className="form-input" />
              </div>
              <div>
                <label htmlFor="ob-user" className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2">Identifiant WordPress</label>
                <input id="ob-user" type="text" value={wp.username} onChange={e => setWp(p => ({ ...p, username: e.target.value }))} placeholder="admin" className="form-input" />
              </div>
              <div>
                <label htmlFor="ob-pass" className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2">Mot de passe d'application</label>
                <input id="ob-pass" type="password" value={wp.password} onChange={e => setWp(p => ({ ...p, password: e.target.value }))} placeholder="xxxx xxxx xxxx xxxx" className="form-input" autoComplete="new-password"/>
                <p className="font-heading text-[11px] text-gray-med mt-1.5">Générez un mot de passe d'application dans WordPress → Profil</p>
              </div>
            </div>
            <div className="flex items-center gap-3 mb-5">
              <Button variant="ghost" size="sm" onClick={testWP} loading={testing}>Tester la connexion</Button>
              {wpStatus === 'ok' && <Badge variant="sage" dot>Connexion réussie</Badge>}
              {wpStatus === 'fail' && <Badge variant="danger">Connexion échouée</Badge>}
            </div>
            <div className="flex gap-3">
              <Button variant="ghost" size="md" onClick={() => setStep('welcome')}>← Retour</Button>
              <Button variant="primary" size="md" className="flex-1" onClick={() => setStep('sources')}>
                Continuer →
              </Button>
            </div>
          </Card>
        )}

        {/* Step: Sources */}
        {step === 'sources' && (
          <Card>
            <h2 className="font-heading font-bold text-xl text-anthracite mb-1">Sources RSS</h2>
            <p className="font-body text-[13px] text-gray-dk mb-5">
              Ces sources alimenteront KORA en actualités. Vous pourrez en ajouter d'autres plus tard.
            </p>
            <div className="space-y-2 mb-4">
              {sources.map((src, i) => (
                <div key={i} className="flex items-center gap-3 bg-gray-pale rounded-md px-3 py-2">
                  <div className="w-6 h-6 rounded bg-blue/15 flex items-center justify-center">
                    <span className="font-heading text-[9px] font-bold text-blue-txt">RSS</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-heading text-[12px] font-semibold text-anthracite">{src.name}</p>
                    <p className="font-heading text-[10px] text-gray-dk truncate">{src.url}</p>
                  </div>
                  <button
                    onClick={() => setSources(prev => prev.filter((_, j) => j !== i))}
                    className="text-gray-med hover:text-danger transition-colors"
                    aria-label={`Supprimer ${src.name}`}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <div className="flex gap-2 mb-5">
              <input
                id="onboarding-source-name"
                type="text"
                aria-label="Nom de la source RSS"
                value={newSource.name}
                onChange={e => setNewSource(p => ({ ...p, name: e.target.value }))}
                placeholder="Nom de la source"
                className="form-input flex-1"
              />
              <input
                id="onboarding-source-url"
                type="url"
                aria-label="URL du flux RSS"
                value={newSource.url}
                onChange={e => setNewSource(p => ({ ...p, url: e.target.value }))}
                placeholder="URL RSS"
                className="form-input flex-1"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (newSource.name && newSource.url) {
                    setSources(p => [...p, newSource])
                    setNewSource({ name: '', url: '' })
                  }
                }}
              >
                +
              </Button>
            </div>
            <div className="flex gap-3">
              <Button variant="ghost" size="md" onClick={() => setStep('wordpress')}>← Retour</Button>
              <Button variant="primary" size="md" className="flex-1" loading={saving} onClick={finishSetup}>
                Terminer la configuration
              </Button>
            </div>
          </Card>
        )}

        {/* Step: Done */}
        {step === 'done' && (
          <Card className="text-center">
            <div className="w-16 h-16 rounded-xl bg-sage/20 flex items-center justify-center mx-auto mb-5">
              <span className="text-sage font-heading font-bold text-3xl">✓</span>
            </div>
            <h2 className="font-heading font-bold text-xl text-anthracite mb-2">Configuration terminée !</h2>
            <p className="font-body text-[14px] text-gray-dk mb-8">
              KORA est prêt à rédiger des articles pour kakilambe.com. Lancez votre premier cycle depuis le tableau de bord.
            </p>
            <Button variant="primary" size="lg" href="/" className="w-full">
              Accéder au tableau de bord
            </Button>
          </Card>
        )}
      </div>
    </div>
  )
}
