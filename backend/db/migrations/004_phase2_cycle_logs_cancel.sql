-- ═══════════════════════════════════════════════════════════════════
-- Migration 004 — Plan V3 Phase 2 : kill switch + persistance des logs
-- ═══════════════════════════════════════════════════════════════════

-- Ajoute CANCELLED comme statut valide pour les cycles (kill switch)
ALTER TABLE cycles DROP CONSTRAINT IF EXISTS cycles_status_check;
ALTER TABLE cycles ADD CONSTRAINT cycles_status_check
  CHECK (status IN ('RUNNING','COMPLETED','FAILED','PAUSED','CANCELLED'));

-- Table de persistance des logs de cycle (survit au redémarrage du backend
-- et permet de rejouer l'historique récent à la connexion SSE)
CREATE TABLE IF NOT EXISTS cycle_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id   UUID NOT NULL,
    level      TEXT NOT NULL,
    event      TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cycle_logs_cycle_id ON cycle_logs(cycle_id, created_at);

ALTER TABLE cycle_logs ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'cycle_logs' AND policyname = 'deny_anon_cycle_logs'
  ) THEN
    CREATE POLICY deny_anon_cycle_logs ON cycle_logs FOR ALL TO anon USING (false);
  END IF;
END $$;
