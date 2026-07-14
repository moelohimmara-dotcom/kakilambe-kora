'use client'

import { useCallback } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { StreakIndicator } from '@/components/ui/StreakIndicator'
import { CycleLaunchOverlay } from '@/components/ui/CycleLaunchOverlay'
import { useLaunchCycle } from '@/lib/useLaunchCycle'
import { gamificationApi } from '@/lib/gamificationApi'
import { useAsync } from '@/lib/hooks'

export function AgentScreen() {
  const {
    cycle, isRunning, isPaused, isBusy,
    pendingArticle,
    runCycle, running,
    cancelCycle, cancelling,
    liveMessage,
  } = useLaunchCycle()

  // Gamification (nouveau périmètre) — indicateur discret, indépendant du
  // polling de statut du cycle.
  const fetchStreak = useCallback(() => gamificationApi.getStreak(), [])
  const { data: streak } = useAsync(fetchStreak)

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-heading font-bold text-2xl text-anthracite">Agent KORA</h1>
        <p className="font-heading text-[13px] text-gray-dk mt-0.5">
          Contrôle du cycle IA · Validation humaine intégrée
        </p>
      </div>

      {/* Contrôles */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <Card>
          <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
            Lancer un cycle
          </h2>
          <div className="space-y-4">
            <Toggle
              checked={true}
              onChange={() => {}}
              disabled
              color="lavender"
              label="Mode semi-automatique"
              description="Verrouillé — validation humaine obligatoire avant toute publication"
            />

            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                size="md"
                loading={running}
                disabled={isBusy}
                onClick={() => runCycle(undefined as unknown as void)}
                className="flex-1"
              >
                {isBusy ? 'Cycle en cours…' : 'Lancer le cycle'}
              </Button>
              {!running && !isBusy && (
                <Badge variant="orange">HITL</Badge>
              )}
            </div>

            {streak && streak.days > 0 && <StreakIndicator days={streak.days} />}

            {isBusy && (
              <Button
                variant="ghost"
                size="sm"
                loading={cancelling}
                onClick={() => cancelCycle(undefined as unknown as void)}
                className="w-full"
              >
                ⏹ Annuler le cycle
              </Button>
            )}
          </div>
        </Card>

        <Card>
          <h2 className="font-heading font-semibold text-[14px] text-anthracite mb-4">
            Statut du cycle
          </h2>
          {!cycle || cycle.status === 'IDLE' ? (
            <div className="empty-state py-4">
              <p className="font-heading text-[13px] text-gray-dk">Aucun cycle actif</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-heading text-[12px] text-gray-dk">Statut</span>
                <CycleStatusBadge status={cycle.status} />
              </div>
              <div className="flex items-center justify-between">
                <span className="font-heading text-[12px] text-gray-dk">Mode</span>
                <span className="font-heading text-[12px] font-medium text-anthracite capitalize">{cycle.mode}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-heading text-[12px] text-gray-dk">Publiés</span>
                <span className="font-heading text-[12px] font-bold text-sage">{cycle.published_count ?? 0}</span>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Bannière passive — jamais de navigation forcée : contrairement à la
          redirection instantanée de runCycle() (déclenchée par l'action de
          l'utilisateur), ceci ne fait qu'informer si un cycle d'une session
          précédente est toujours en pause en arrivant sur cette page. */}
      {!isBusy && isPaused && pendingArticle && (
        <Card className="mb-6 border-orange/30 bg-orange/5">
          <div className="flex items-center justify-between gap-4">
            <p className="font-heading text-[13px] text-anthracite">
              Un article rédigé lors d'un cycle précédent attend toujours votre validation.
            </p>
            <Button href={`/articles/${pendingArticle.id}`} variant="outline" size="sm">
              Lire l'article →
            </Button>
          </div>
        </Card>
      )}

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

function CycleStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; variant: 'orange' | 'sage' | 'danger' | 'warning' | 'gray' }> = {
    RUNNING:   { label: 'En cours', variant: 'orange' },
    PAUSED:    { label: 'En pause', variant: 'warning' },
    COMPLETED: { label: 'Terminé', variant: 'sage' },
    FAILED:    { label: 'Échoué', variant: 'danger' },
    CANCELLED: { label: 'Annulé', variant: 'gray' },
    IDLE:      { label: 'Inactif', variant: 'gray' },
  }
  const { label, variant } = map[status] ?? { label: status, variant: 'gray' as const }
  return <Badge variant={variant} dot={status === 'RUNNING'} pulse={status === 'RUNNING'}>{label}</Badge>
}
