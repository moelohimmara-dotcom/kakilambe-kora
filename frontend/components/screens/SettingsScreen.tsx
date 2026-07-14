'use client'

import { useState, useCallback } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { Spinner } from '@/components/ui/Spinner'
import { useAsync, useMutation } from '@/lib/hooks'
import { useToast } from '@/lib/contexts/ToastContext'
import { settingsApi, providerApi, healthApi } from '@/lib/api'
import type { SystemPrompt, Provider, AppSettings, WpCategory, KoraCategoryLabel } from '@/lib/types'

type Tab = 'wordpress' | 'categories' | 'prompts' | 'providers'

// app_settings stocke tout en TEXT côté backend (str(value) en Python) —
// une valeur booléenne fausse revient comme la chaîne non vide "False",
// qui est "truthy" en JS. Sans coercion, un Toggle désactivé puis rechargé
// réapparaîtrait actif. Utilisé pour toutes les valeurs booléennes/numériques
// lues depuis /api/settings.
function asBool(v: unknown, fallback: boolean): boolean {
  if (typeof v === 'boolean') return v
  if (typeof v === 'string') return v.toLowerCase() === 'true'
  return fallback
}
function asNumber(v: unknown, fallback: number): number {
  const n = Number(v)
  return Number.isFinite(n) && v !== undefined && v !== null && v !== '' ? n : fallback
}

const KORA_LABELS: KoraCategoryLabel[] = [
  'Politique', 'Économie', 'Société', 'Sport', 'Culture', 'Sécurité', 'International',
]

export function SettingsScreen() {
  const [tab, setTab] = useState<Tab>('wordpress')

  const TABS: { key: Tab; label: string }[] = [
    { key: 'wordpress',  label: 'WordPress' },
    { key: 'categories', label: 'Catégories' },
    { key: 'prompts',    label: 'Prompts système' },
    { key: 'providers',  label: 'Fournisseurs LLM' },
  ]

  return (
    <div className="p-6 md:p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="font-heading font-bold text-2xl text-anthracite">Paramètres</h1>
        <p className="font-heading text-[13px] text-gray-dk mt-0.5">Configuration du système KORA</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-pale rounded-lg p-1 w-fit" role="tablist" aria-label="Sections des paramètres">
        {TABS.map(t => (
          <button
            key={t.key}
            id={`settings-tab-${t.key}`}
            role="tab"
            aria-selected={tab === t.key}
            aria-controls="settings-panel"
            onClick={() => setTab(t.key)}
            className={
              `px-4 py-1.5 rounded-md font-heading text-[12px] font-semibold transition-all ` +
              `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange ` +
              `${tab === t.key ? 'bg-white text-anthracite shadow-sm' : 'text-gray-dk hover:text-anthracite'}`
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      <div id="settings-panel" role="tabpanel" aria-labelledby={`settings-tab-${tab}`}>
        {tab === 'wordpress' && <WordPressTab />}
        {tab === 'categories' && <CategoriesTab />}
        {tab === 'prompts' && <PromptsTab />}
        {tab === 'providers' && <ProvidersTab />}
      </div>
    </div>
  )
}

// ── WordPress Tab ─────────────────────────────────────────────────────────────

function WordPressTab() {
  const { show } = useToast()
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'ok' | 'fail' | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [testingEmail, setTestingEmail] = useState(false)

  const fetchSettings = useCallback(() => settingsApi.get(), [])
  const { data, loading } = useAsync<AppSettings>(fetchSettings)
  const [form, setForm] = useState<AppSettings>({})

  // Sync form with fetched data
  const settings = data ?? {}

  const { mutate: save, loading: saving } = useMutation(async () => {
    await settingsApi.patch(form as Record<string, unknown>)
    show('Paramètres sauvegardés', 'success')
  })

  async function testConnection() {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await healthApi.check() as { services?: Record<string, string> }
      setTestResult(r.services?.wordpress === 'ok' ? 'ok' : 'fail')
    } catch {
      setTestResult('fail')
    } finally {
      setTesting(false)
    }
  }

  async function testEmail() {
    setTestingEmail(true)
    try {
      const r = await settingsApi.testEmail()
      show(`Email de test envoyé à ${r.to}`, 'success')
    } catch (e) {
      show(e instanceof Error ? e.message : 'Échec de l\'envoi de l\'email', 'error')
    } finally {
      setTestingEmail(false)
    }
  }

  if (loading) return <div className="flex justify-center py-8"><Spinner /></div>

  // app_settings renvoie tout en texte brut (str(value) côté backend) —
  // coercion explicite pour que les Toggle/number reflètent la vraie valeur,
  // y compris "false"/"False" (sinon truthy en JS car chaîne non vide).
  const raw = { ...settings, ...form } as Record<string, unknown>
  const current = {
    ...raw,
    auto_publish_enabled: asBool(raw.auto_publish_enabled, false),
    daily_article_limit: asNumber(raw.daily_article_limit, 3),
    cycle_hour: asNumber(raw.cycle_hour, 6),
    delay_between_posts: asNumber(raw.delay_between_posts, 15),
    daily_report: asBool(raw.daily_report, false),
    error_alerts: asBool(raw.error_alerts, false),
  } as AppSettings

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
          Connexion WordPress
        </h2>
        <div className="space-y-4">
          <Field label="URL du site" id="wp_url">
            <input
              id="wp_url"
              type="url"
              defaultValue={current.wp_url ?? ''}
              onChange={e => setForm(p => ({ ...p, wp_url: e.target.value }))}
              placeholder="https://kakilambe.com"
              className="form-input"
            />
          </Field>
          <Field label="Identifiant" id="wp_user">
            <input
              id="wp_user"
              type="text"
              defaultValue={current.wp_username ?? ''}
              onChange={e => setForm(p => ({ ...p, wp_username: e.target.value }))}
              placeholder="admin"
              className="form-input"
            />
          </Field>
          <Field label="Mot de passe d'application" id="wp_pass">
            <div className="relative">
              <input
                id="wp_pass"
                type={showPassword ? 'text' : 'password'}
                defaultValue={current.wp_app_password ? '••••••••••••' : ''}
                onChange={e => setForm(p => ({ ...p, wp_app_password: e.target.value }))}
                placeholder="xxxx xxxx xxxx xxxx xxxx"
                className="form-input pr-16"
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 font-heading text-[11px] text-gray-dk hover:text-anthracite px-2 py-1"
                aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
              >
                {showPassword ? 'Masquer' : 'Afficher'}
              </button>
            </div>
          </Field>
        </div>

        <div className="flex items-center gap-3 mt-5 pt-5 border-t border-gray-pale">
          <Button variant="ghost" size="sm" onClick={testConnection} loading={testing}>
            Tester la connexion
          </Button>
          {testResult === 'ok' && <Badge variant="sage" dot>Connexion OK</Badge>}
          {testResult === 'fail' && <Badge variant="danger">Connexion échouée</Badge>}
          <div className="flex-1" />
          <Button variant="confirm" size="sm" loading={saving} onClick={() => save(undefined as unknown as void)}>
            Sauvegarder
          </Button>
        </div>
      </Card>

      <Card>
        <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
          Publication automatique
        </h2>
        <div className="space-y-4">
          <Toggle
            checked={current.auto_publish_enabled ?? false}
            onChange={v => setForm(p => ({ ...p, auto_publish_enabled: v }))}
            label="Activer la publication automatique"
            description="Les articles en mode Auto sont publiés sans validation manuelle"
          />
          <Field label="Limite d'articles par cycle" id="daily_limit">
            <input
              id="daily_limit"
              type="number"
              min={1} max={20}
              defaultValue={current.daily_article_limit ?? 3}
              onChange={e => setForm(p => ({ ...p, daily_article_limit: Number(e.target.value) }))}
              className="form-input w-24"
            />
          </Field>
        </div>
      </Card>

      <Card>
        <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
          Planification & Cycles
        </h2>
        <div className="space-y-4">
          <Field label="Heure d'exécution du cycle (UTC)" id="cycle_hour">
            <input
              id="cycle_hour"
              type="number"
              min={0} max={23}
              defaultValue={current.cycle_hour ?? 6}
              onChange={e => setForm(p => ({ ...p, cycle_hour: Number(e.target.value) }))}
              className="form-input w-24"
              placeholder="6"
            />
            <p className="font-heading text-[11px] text-gray-dk mt-1">Exemple : 6 pour 6h00 UTC.</p>
          </Field>
          <Field label="Délai entre chaque publication (secondes)" id="delay_posts">
            <input
              id="delay_posts"
              type="number"
              min={0} max={3600}
              defaultValue={current.delay_between_posts ?? 15}
              onChange={e => setForm(p => ({ ...p, delay_between_posts: Number(e.target.value) }))}
              className="form-input w-24"
            />
            <p className="font-heading text-[11px] text-gray-dk mt-1">
              Espacement (via QStash) entre chaque article publié lors d&apos;un même cycle.
            </p>
          </Field>
        </div>
      </Card>

      <Card>
        <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
          Notifications & Alertes
        </h2>
        <div className="space-y-4">
          <Toggle
            checked={current.daily_report ?? false}
            onChange={v => setForm(p => ({ ...p, daily_report: v }))}
            label="Activer le rapport quotidien"
            description="Recevez un email résumant l'activité de KORA après chaque cycle."
          />
          <Toggle
            checked={current.error_alerts ?? false}
            onChange={v => setForm(p => ({ ...p, error_alerts: v }))}
            label="Alertes d'erreur"
            description="Signale les échecs de cycle dans le rapport email."
          />
          <Field label="Email de l'administrateur" id="admin_email">
            <input
              id="admin_email"
              type="email"
              defaultValue={current.admin_email ?? ''}
              onChange={e => setForm(p => ({ ...p, admin_email: e.target.value }))}
              className="form-input"
              placeholder="admin@kakilambe.com"
            />
          </Field>

          <div className="mt-4 pt-4 border-t border-gray-pale">
            <Button variant="outline" size="sm" onClick={testEmail} loading={testingEmail}>
              Envoyer un email de test
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

// ── Catégories Tab ────────────────────────────────────────────────────────────
// Remplace les IDs codés en dur dans writer.py : synchronise les vraies
// catégories WordPress puis laisse l'utilisateur les associer aux 7 libellés
// éditoriaux fixes utilisés par l'agent.

function CategoriesTab() {
  const { show } = useToast()
  const fetchCategories = useCallback(() => settingsApi.wpCategories(), [])
  const { data: categories, loading, refetch } = useAsync<WpCategory[]>(fetchCategories)

  const { mutate: sync, loading: syncing } = useMutation(async () => {
    const result = await settingsApi.syncWpCategories() as { synced: number }
    show(`${result.synced} catégorie(s) synchronisée(s) depuis WordPress`, 'success')
    await refetch()
  })

  const { mutate: setMapping } = useMutation(async ({ wpId, label }: { wpId: number; label: string | null }) => {
    await settingsApi.updateWpCategoryMapping(wpId, label)
    await refetch()
  })

  const list = categories ?? []
  const mappedLabels = new Set(list.map(c => c.kora_label).filter(Boolean))
  const unmapped = KORA_LABELS.filter(l => !mappedLabels.has(l))

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-heading font-semibold text-[14px] text-anthracite">
              Synchronisation WordPress
            </h2>
            <p className="font-heading text-[12px] text-gray-dk mt-0.5">
              Récupère les vraies catégories de kakilambe.com et les associe aux libellés éditoriaux de KORA.
            </p>
          </div>
          <Button variant="primary" size="sm" loading={syncing} onClick={() => sync(undefined as unknown as void)}>
            Synchroniser
          </Button>
        </div>

        {unmapped.length > 0 && list.length > 0 && (
          <div className="mb-4 px-3 py-2 rounded-md bg-warning/10 border border-warning/30">
            <p className="font-heading text-[12px] text-anthracite">
              Non mappés (retombent sur la catégorie par défaut) : {unmapped.join(', ')}
            </p>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : list.length === 0 ? (
          <div className="empty-state py-8">
            <p className="font-heading text-[13px] text-gray-dk">
              Aucune catégorie synchronisée. Cliquez sur « Synchroniser » pour récupérer celles de WordPress.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {list.map(cat => (
              <div key={cat.wp_id} className="flex items-center justify-between gap-4 px-3 py-2.5 rounded-md bg-gray-pale">
                <div className="min-w-0">
                  <span className="font-heading text-[13px] font-medium text-anthracite">{cat.name}</span>
                  <span className="font-mono text-[10px] text-gray-med ml-2">#{cat.wp_id}</span>
                </div>
                <select
                  value={cat.kora_label ?? ''}
                  onChange={e => setMapping({ wpId: cat.wp_id, label: e.target.value || null })}
                  className="form-input w-48 shrink-0"
                  aria-label={`Libellé KORA pour ${cat.name}`}
                >
                  <option value="">— Non mappée —</option>
                  {KORA_LABELS.map(label => (
                    <option key={label} value={label}>{label}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

// ── Prompts Tab ───────────────────────────────────────────────────────────────

function PromptsTab() {
  const { show } = useToast()
  const [editing, setEditing] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editTemp, setEditTemp] = useState(0.7)
  const [refining, setRefining] = useState<string | null>(null)
  const [instruction, setInstruction] = useState('')

  const fetchPrompts = useCallback(() => settingsApi.prompts(), [])
  const { data: prompts, loading, refetch } = useAsync<SystemPrompt[]>(fetchPrompts)

  const { mutate: save, loading: saving } = useMutation(async (id: string) => {
    await settingsApi.updatePrompt(id, { content: editContent, temperature: editTemp })
    show('Prompt sauvegardé', 'success')
    setEditing(null)
    await refetch()
  })

  const { mutate: resetPrompt, loading: resetting } = useMutation(async (id: string) => {
    try {
      const result = await settingsApi.resetPrompt(id)
      setEditContent(result.content)
      setEditTemp(result.temperature)
      show('Prompt restauré à sa valeur d\'origine', 'success')
      await refetch()
    } catch (e) {
      show(e instanceof Error ? e.message : 'Impossible de restaurer ce prompt', 'error')
    }
  })

  // Fait évoluer un prompt secondaire via une instruction en langage naturel
  // (correction ponctuelle ou amélioration continue — le même mécanisme sert
  // les deux : chaque appel réécrit à partir du contenu ACTUEL, donc des
  // instructions successives s'accumulent naturellement au fil des cycles).
  const { mutate: refine, loading: refiningInFlight } = useMutation(async (id: string) => {
    if (!instruction.trim()) return
    try {
      const result = await settingsApi.refinePrompt(id, instruction.trim())
      show('Prompt mis à jour selon ton instruction', 'success')
      setInstruction('')
      setRefining(null)
      if (editing === id) { setEditContent(result.content); setEditTemp(result.temperature) }
      await refetch()
    } catch (e) {
      show(e instanceof Error ? e.message : "Impossible de faire évoluer ce prompt", 'error')
    }
  })

  // Dérive une version cohérente à partir du prompt principal ACTUEL (pas un
  // texte d'origine figé) — utile si ce prompt secondaire est devenu
  // incohérent avec la ligne éditoriale de référence.
  const { mutate: restoreFromPrimary, loading: restoringFromPrimary } = useMutation(async (id: string) => {
    try {
      const result = await settingsApi.restorePromptFromPrimary(id)
      show('Prompt restauré depuis le prompt principal', 'success')
      if (editing === id) { setEditContent(result.content); setEditTemp(result.temperature) }
      await refetch()
    } catch (e) {
      show(e instanceof Error ? e.message : 'Impossible de restaurer ce prompt', 'error')
    }
  })

  if (loading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <div className="space-y-4">
      {(prompts ?? []).map(prompt => (
        <Card key={prompt.id}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <h3 className="font-heading font-semibold text-[14px] text-anthracite">{prompt.name}</h3>
              {prompt.is_builtin && <Badge variant="blue">Système</Badge>}
              {prompt.is_default && <Badge variant="sage">Défaut</Badge>}
              {prompt.frontend_locked && <Badge variant="danger">🔒 Verrouillé</Badge>}
            </div>
            {!prompt.frontend_locked && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditing(prompt.id)
                  setEditContent(prompt.content)
                  setEditTemp(prompt.temperature)
                }}
              >
                Modifier
              </Button>
            )}
          </div>

          {prompt.frontend_locked ? (
            <>
              <p className="font-mono text-[11px] text-gray-dk bg-gray-pale rounded-md p-3 line-clamp-3">
                {prompt.content}
              </p>
              <p className="font-heading text-[11px] text-gray-med mt-2">
                Prompt principal — modifiable uniquement par accès backend direct (script), jamais depuis cette interface.
              </p>
            </>
          ) : editing === prompt.id ? (
            <div className="space-y-3">
              <textarea
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
                rows={8}
                className="form-input font-mono text-[12px] resize-y"
                aria-label={`Contenu du prompt ${prompt.name}`}
              />
              <div className="flex items-center gap-4">
                <label htmlFor={`temp-${prompt.id}`} className="font-heading text-[12px] text-gray-dk">
                  Température : <strong>{editTemp}</strong>
                </label>
                <input
                  id={`temp-${prompt.id}`}
                  type="range"
                  min={0} max={1} step={0.05}
                  value={editTemp}
                  onChange={e => setEditTemp(Number(e.target.value))}
                  className="flex-1 accent-orange"
                  aria-valuemin={0}
                  aria-valuemax={1}
                  aria-valuenow={editTemp}
                />
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button variant="confirm" size="sm" loading={saving} onClick={() => save(prompt.id)}>
                  Sauvegarder
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setEditing(null)}>Annuler</Button>
                {prompt.is_builtin && (
                  <Button
                    variant="danger"
                    size="sm"
                    loading={resetting}
                    onClick={() => {
                      if (confirm('Voulez-vous vraiment écraser vos modifications pour revenir au prompt système par défaut ?')) {
                        resetPrompt(prompt.id)
                      }
                    }}
                  >
                    Restaurer par défaut
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  loading={restoringFromPrimary}
                  onClick={() => {
                    if (confirm('Dériver une nouvelle version de ce prompt à partir du prompt principal actuel ? Le contenu actuel sera remplacé.')) {
                      restoreFromPrimary(prompt.id)
                    }
                  }}
                >
                  Restaurer depuis le prompt principal
                </Button>
              </div>

              {/* Évolution guidée par instruction — sert aussi bien la
                  correction ponctuelle que l'amélioration continue au fil
                  des cycles (cf. commentaire sur `refine` ci-dessus). */}
              <div className="pt-3 border-t border-gray-light">
                {refining === prompt.id ? (
                  <div className="space-y-2">
                    <label htmlFor={`instr-${prompt.id}`} className="block font-heading text-[12px] font-semibold text-gray-dk">
                      Décris le changement souhaité, en langage naturel
                    </label>
                    <textarea
                      id={`instr-${prompt.id}`}
                      value={instruction}
                      onChange={e => setInstruction(e.target.value)}
                      rows={2}
                      placeholder="Ex : rends le ton plus formel · affine la longueur des méta-descriptions pour les prochains cycles…"
                      className="form-input text-[13px] resize-y"
                    />
                    <div className="flex gap-2">
                      <Button
                        variant="confirm"
                        size="sm"
                        loading={refiningInFlight}
                        disabled={!instruction.trim()}
                        onClick={() => refine(prompt.id)}
                      >
                        Appliquer
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => { setRefining(null); setInstruction('') }}>
                        Annuler
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button variant="outline" size="sm" onClick={() => setRefining(prompt.id)}>
                    Faire évoluer via une instruction…
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <p className="font-mono text-[11px] text-gray-dk bg-gray-pale rounded-md p-3 line-clamp-3">
              {prompt.content}
            </p>
          )}
        </Card>
      ))}
    </div>
  )
}

// ── Providers Tab ─────────────────────────────────────────────────────────────

function ProvidersTab() {
  const { show } = useToast()
  const fetchProviders = useCallback(() => providerApi.list(), [])
  const { data: providers, loading, refetch } = useAsync<Provider[]>(fetchProviders)

  const { mutate: resetAll } = useMutation(async () => {
    await providerApi.reset()
    show('Fournisseurs réinitialisés', 'success')
    await refetch()
  })

  if (loading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={() => resetAll(undefined as unknown as void)}>
          Réinitialiser tous
        </Button>
      </div>

      {(providers ?? []).map(provider => (
        <ProviderRow key={provider.name} provider={provider} onRefetch={refetch} />
      ))}
    </div>
  )
}

function ProviderRow({ provider, onRefetch }: { provider: Provider; onRefetch: () => void }) {
  const { show } = useToast()
  const statusMap: Record<string, { label: string; variant: 'sage' | 'orange' | 'warning' | 'danger' }> = {
    ACTIVE:       { label: 'Actif', variant: 'sage' },
    RATE_LIMITED: { label: 'Limité', variant: 'warning' },
    EXHAUSTED:    { label: 'Épuisé', variant: 'danger' },
    OFFLINE:      { label: 'Hors ligne', variant: 'danger' },
  }
  const st = statusMap[provider.status] ?? { label: provider.status, variant: 'gray' as const }
  const usagePct = provider.usage_pct ?? (
    provider.daily_token_limit ? Math.round((provider.tokens_used_today / provider.daily_token_limit) * 100) : null
  )

  const { mutate: override } = useMutation(async (status: string) => {
    await providerApi.override(provider.name, status)
    show(`${provider.name} → ${status}`, 'success')
    onRefetch()
  })

  return (
    <Card>
      <div className="flex items-center gap-4 mb-3">
        <div className="w-10 h-10 rounded-md bg-blue/10 flex items-center justify-center shrink-0">
          <span className="font-heading text-[10px] font-bold text-blue-txt uppercase">
            {provider.name.slice(0, 4)}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-heading font-semibold text-[13px] text-anthracite capitalize">{provider.name}</span>
            <Badge variant={st.variant as 'sage' | 'orange' | 'warning' | 'danger'}>{st.label}</Badge>
          </div>
          <span className="font-mono text-[11px] text-gray-dk">{provider.model}</span>
        </div>
        <div className="text-right shrink-0">
          <div className="font-heading text-[12px] font-semibold text-anthracite">
            {provider.tokens_used_today.toLocaleString()} tokens
          </div>
          <div className="font-heading text-[10px] text-gray-dk">{provider.requests_today} requêtes</div>
        </div>
      </div>

      {/* Usage bar */}
      {usagePct !== null && (
        <div className="mb-3">
          <div className="flex justify-between mb-1">
            <span className="font-heading text-[10px] text-gray-dk">Utilisation</span>
            <span className="font-heading text-[10px] text-gray-dk">{usagePct}%</span>
          </div>
          <div
            className="h-1.5 bg-gray-pale rounded-full overflow-hidden"
            role="progressbar"
            aria-valuenow={usagePct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Utilisation ${provider.name} : ${usagePct}%`}
          >
            <div
              className={`h-full rounded-full transition-all ${usagePct > 80 ? 'bg-danger' : usagePct > 60 ? 'bg-warning' : 'bg-sage'}`}
              style={{ width: `${Math.min(usagePct, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Override actions */}
      {provider.status !== 'ACTIVE' && (
        <Button variant="ghost" size="sm" onClick={() => override('ACTIVE')}>
          Remettre actif
        </Button>
      )}
    </Card>
  )
}

// ── Shared ────────────────────────────────────────────────────────────────────
function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block font-heading text-[12px] font-semibold text-gray-dk uppercase tracking-wide mb-2">
        {label}
      </label>
      {children}
    </div>
  )
}
