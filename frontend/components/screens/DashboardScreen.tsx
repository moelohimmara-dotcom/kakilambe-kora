'use client'

import { useCallback } from 'react'
import Link from 'next/link'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { GamificationBar } from '@/components/ui/GamificationBar'
import { CycleLaunchOverlay } from '@/components/ui/CycleLaunchOverlay'
import { useLaunchCycle } from '@/lib/useLaunchCycle'
import { useAsync, useInterval } from '@/lib/hooks'
import { articleApi, agentApi } from '@/lib/api'
import { formatRelative, statusLabel, statusVariant } from '@/lib/utils'
import type { Article } from '@/lib/types'

// Forme réelle de la réponse GET /api/agent/status — plate, jamais imbriquée
// sous une clé "cycle" (bug précédent : (res as {cycle?}).cycle était toujours
// undefined, la carte de statut affichait "Inactif" en permanence).
interface CycleStatusInfo {
  cycle_id?: string
  status: string
  mode?: string
  published_count?: number
}

interface DashboardData {
  pending: Article[]
  recent: Article[]
  cycle: CycleStatusInfo | null
}

export function DashboardScreen() {
  // Même hook que /agent (CDC §3.4.1 : "même flux, pas une implémentation
  // dupliquée divergente") — le bouton "Lancer un cycle" déclenche
  // désormais réellement un cycle depuis le Dashboard au lieu de se
  // contenter de naviguer vers /agent. Le cycle_id est partagé via
  // localStorage : si l'utilisateur navigue vers /agent pendant l'attente,
  // cet écran reprend le suivi du même cycle sans le relancer.
  const { isBusy, running, isRunning, runCycle, cancelCycle, cancelling, liveMessage } = useLaunchCycle()

  const fetchDashboard = useCallback(async (): Promise<DashboardData> => {
    const [pendingRes, recentRes, cycleRes] = await Promise.allSettled([
      articleApi.list('PENDING_REVIEW'),
      articleApi.list(undefined, 1),
      agentApi.status(),
    ])

    return {
      pending: pendingRes.status === 'fulfilled' ? (pendingRes.value as { items: Article[] }).items ?? [] : [],
      recent: recentRes.status === 'fulfilled' ? (recentRes.value as { items: Article[] }).items ?? [] : [],
      cycle: cycleRes.status === 'fulfilled' ? (cycleRes.value as unknown as CycleStatusInfo) : null,
    }
  }, [])

  const { data, loading, refetch } = useAsync(fetchDashboard)

  // Refresh actif pendant un cycle, sinon toutes les 60s
  useInterval(
    refetch,
    data?.cycle?.status === 'RUNNING' || data?.cycle?.status === 'PAUSED' ? 10000 : 60000,
  )

  const pending = data?.pending ?? []
  const recent = data?.recent ?? []
  const cycle = data?.cycle
  const isPaused = cycle?.status === 'PAUSED'
  // L'article le plus récent en attente correspond à celui qui bloque le
  // cycle en pause HITL — mis en avant dans la carte d'aperçu ci-dessous.
  const hitlArticle = isPaused ? pending[0] : undefined

  return (
    <div className="p-6 md:p-8 max-w-6xl">
      {/* En-tête */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-heading font-bold text-2xl text-anthracite">Tableau de bord</h1>
          <p className="font-heading text-[13px] text-gray-dk mt-0.5">GuinéePress Intelligence · kakilambe.com</p>
        </div>
        <div className="flex items-center gap-3">
          <GamificationBar />
          <Button
            variant="primary"
            size="sm"
            loading={running}
            disabled={isBusy}
            onClick={() => runCycle(undefined as unknown as void)}
          >
            {isBusy ? 'Cycle en cours…' : 'Lancer un cycle'}
          </Button>
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          value={pending.length}
          label="En attente de validation"
          variant="orange"
          loading={loading}
        />
        <KpiCard
          value={recent.filter(a => a.status === 'PUBLISHED').length}
          label="Publiés (page actuelle)"
          variant="sage"
          loading={loading}
        />
        <KpiCard
          value={recent.filter(a => a.status === 'FAILED').length}
          label="Erreurs"
          variant="danger"
          loading={loading}
        />
        <CycleStatusCard cycle={cycle ?? null} loading={loading} />
      </div>

      {/* Aperçu HITL — cycle en pause, article prêt à valider */}
      {hitlArticle && (
        <section className="mb-8">
          <Card className="border-orange/30 bg-orange/5">
            <div className="flex items-start gap-4">
              {hitlArticle.image_url ? (
                <img
                  src={hitlArticle.image_url}
                  alt=""
                  className="w-24 h-24 rounded-lg object-cover shrink-0 bg-gray-pale"
                />
              ) : (
                <div className="w-24 h-24 rounded-lg bg-orange/10 flex items-center justify-center shrink-0">
                  <span className="text-orange font-heading font-bold text-2xl">/</span>
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="warning">Cycle en pause · HITL</Badge>
                </div>
                <h3 className="font-heading font-semibold text-[15px] text-anthracite line-clamp-1">
                  {hitlArticle.titre}
                </h3>
                {hitlArticle.chapeau && (
                  <p className="font-heading text-[12px] text-gray-dk mt-1 line-clamp-2">
                    {hitlArticle.chapeau}
                  </p>
                )}
                <div className="flex gap-3 mt-3">
                  <Button href="/agent" variant="primary" size="sm">
                    Valider dans Agent KORA →
                  </Button>
                  <Button href={`/articles/${hitlArticle.id}`} variant="outline" size="sm">
                    Lire l'article
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </section>
      )}

      {/* Articles en attente */}
      {pending.length > 0 && (
        <section className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-heading font-semibold text-[15px] text-anthracite">
              En attente de validation
              <Badge variant="orange" className="ml-2">{pending.length}</Badge>
            </h2>
            <Link href="/articles?status=PENDING_REVIEW" className="font-heading text-[12px] text-orange hover:underline">
              Voir tout →
            </Link>
          </div>
          <div className="space-y-3">
            {pending.slice(0, 3).map(a => (
              <ArticleRow key={a.id} article={a} />
            ))}
          </div>
        </section>
      )}

      {/* Articles récents */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-heading font-semibold text-[15px] text-anthracite">Articles récents</h2>
          <Link href="/articles" className="font-heading text-[12px] text-orange hover:underline">
            Voir tout →
          </Link>
        </div>
        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : recent.length === 0 ? (
          <EmptyDashboard onLaunch={() => runCycle(undefined as unknown as void)} running={running} isBusy={isBusy} />
        ) : (
          <div className="space-y-2">
            {recent.slice(0, 8).map(a => (
              <ArticleRow key={a.id} article={a} />
            ))}
          </div>
        )}
      </section>

      <CycleLaunchOverlay
        isBusy={isBusy}
        isRunning={isRunning}
        cancelling={cancelling}
        onCancel={() => cancelCycle(undefined as unknown as void)}
        liveMessage={liveMessage}
      />
    </div>
  )
}

// ── Composants internes ────────────────────────────────────────────────────

function KpiCard({
  value, label, variant, loading,
}: {
  value: number
  label: string
  variant: 'orange' | 'sage' | 'danger' | 'blue'
  loading: boolean
}) {
  const colors = {
    orange: 'text-orange',
    sage:   'text-sage',
    danger: 'text-danger',
    blue:   'text-blue-txt',
  }
  return (
    <Card className="text-center">
      {loading ? (
        <div className="skeleton h-9 w-16 mx-auto mb-2" />
      ) : (
        <div className={`font-heading font-bold text-3xl ${colors[variant]}`}>{value}</div>
      )}
      <p className="font-heading text-[11px] text-gray-dk mt-1 leading-tight">{label}</p>
    </Card>
  )
}

function CycleStatusCard({ cycle, loading }: { cycle: CycleStatusInfo | null; loading: boolean }) {
  const statusMap: Record<string, { label: string; color: string }> = {
    RUNNING: { label: 'En cours', color: 'text-orange' },
    PAUSED:  { label: 'En pause HITL', color: 'text-warning' },
    COMPLETED: { label: 'Complété', color: 'text-sage' },
    FAILED: { label: 'Échoué', color: 'text-danger' },
    CANCELLED: { label: 'Annulé', color: 'text-gray-med' },
    IDLE: { label: 'Inactif', color: 'text-gray-med' },
  }
  const active = cycle && cycle.status !== 'IDLE'
  const st = cycle ? (statusMap[cycle.status] ?? { label: cycle.status, color: 'text-gray-dk' }) : null

  return (
    <Card className="text-center">
      {loading ? (
        <div className="skeleton h-9 w-20 mx-auto mb-2" />
      ) : cycle ? (
        <div className={`font-heading font-bold text-xl ${st?.color}`}>{st?.label}</div>
      ) : (
        <div className="font-heading font-bold text-xl text-gray-med">Inactif</div>
      )}
      <p className="font-heading text-[11px] text-gray-dk mt-1">{active ? 'Cycle en cours' : 'Dernier cycle'}</p>
    </Card>
  )
}

function ArticleRow({ article }: { article: Article }) {
  return (
    <Link href={`/articles/${article.id}`} className="block">
      <Card hover padding="sm" className="flex items-center gap-4">
        {/* Image thumbnail */}
        {article.image_url ? (
          <img
            src={article.image_url}
            alt=""
            className="w-14 h-14 rounded-md object-cover shrink-0 bg-gray-pale"
          />
        ) : (
          <div className="w-14 h-14 rounded-md bg-orange/10 flex items-center justify-center shrink-0">
            <span className="text-orange font-heading font-bold text-lg">/</span>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="font-heading font-semibold text-[13px] text-anthracite truncate">
            {article.titre}
          </p>
          <p className="font-heading text-[11px] text-gray-dk mt-0.5 truncate">
            {article.source_nom ?? '—'} · {formatRelative(article.created_at)}
          </p>
        </div>

        {/* Status */}
        <Badge variant={statusVariant(article.status)} className="shrink-0">
          {statusLabel(article.status)}
        </Badge>
      </Card>
    </Link>
  )
}

function EmptyDashboard({ onLaunch, running, isBusy }: { onLaunch: () => void; running: boolean; isBusy: boolean }) {
  return (
    <div className="empty-state">
      <div className="w-16 h-16 rounded-xl bg-orange/10 flex items-center justify-center">
        <span className="font-heading font-extrabold text-2xl text-orange">/K</span>
      </div>
      <p className="font-heading font-semibold text-[15px] text-anthracite">Aucun article pour l'instant</p>
      <p className="font-heading text-[13px] text-gray-dk max-w-xs">
        Lancez votre premier cycle KORA pour collecter et rédiger des articles automatiquement.
      </p>
      <Button variant="primary" size="md" loading={running} disabled={isBusy} onClick={onLaunch}>
        Lancer le premier cycle
      </Button>
    </div>
  )
}
