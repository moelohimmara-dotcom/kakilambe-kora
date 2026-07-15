// Types TypeScript partagés KORA

export type ArticleStatus = 'DRAFT' | 'PENDING_REVIEW' | 'PUBLISHED' | 'REJECTED' | 'FAILED'
// 'CHAT_EXPORT' retiré — origine liée au chat, supprimé (voir ChatMessage/ChatSession ci-dessous).
export type ArticleOrigin = 'AGENT_AUTO' | 'AGENT_SEMI'
export type ProviderStatus = 'ACTIVE' | 'RATE_LIMITED' | 'EXHAUSTED' | 'OFFLINE'
export type CycleStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PAUSED' | 'CANCELLED'
export type CycleMode = 'auto' | 'semi'
export type BadgeVariant = 'orange' | 'sage' | 'blue' | 'gray' | 'danger' | 'warning'

export interface Article {
  id: string
  titre: string
  chapeau?: string
  corps?: string
  meta_description?: string
  mots_cles?: string[]
  categorie_id?: number
  source_url?: string
  source_nom?: string
  image_url?: string
  wp_url?: string
  status: ArticleStatus
  origin: ArticleOrigin
  llm_provider_used?: string
  word_count?: number
  cycle_id?: string
  created_at: string
  published_at?: string
  // Date réelle de publication de la source (jamais générée par le LLM,
  // null si non confirmée — cf. migration 013 backend). date_label/
  // date_confirmed sont calculés côté backend (article_routes.py) à partir
  // de ce seul champ, jamais de created_at.
  source_published_at?: string | null
  date_label?: string
  date_confirmed?: boolean
}

export interface Provider {
  name: string
  model: string
  status: ProviderStatus
  tokens_used_today: number
  daily_token_limit: number | null
  usage_pct: number | null
  requests_today: number
  rate_limited_until?: string
}

export interface Cycle {
  id: string
  mode: CycleMode
  status: CycleStatus
  articles_collected: number
  articles_selected: number
  articles_published: number
  articles_rejected: number
  started_at: string
  completed_at?: string
}

export interface RSSSource {
  id: string
  name: string
  url: string
  category?: string
  source_level: number
  is_active: boolean
  last_synced?: string
  error_count: number
}

export interface SystemPrompt {
  id: string
  name: string
  content: string
  is_default: boolean
  is_builtin: boolean
  temperature: number
  // Prompt principal (KORA Journaliste) — jamais modifiable depuis le
  // frontend, vérifié côté serveur sur chaque route de mutation.
  frontend_locked: boolean
}

export interface KpiData {
  pending_count: number
  published_week: number
  next_cycle_hour: string
}

export type KoraCategoryLabel =
  | 'Politique' | 'Économie' | 'Société' | 'Sport' | 'Culture' | 'Sécurité' | 'International'

export interface WpCategory {
  wp_id: number
  name: string
  slug: string
  kora_label: KoraCategoryLabel | null
  synced_at: string
}

export interface AppSettings {
  wp_url?: string
  wp_username?: string
  wp_app_password?: string
  auto_publish_enabled?: boolean
  daily_article_limit?: number
  publication_delay_hours?: number
  report_email?: string
  admin_email?: string
  cycle_hour?: number
  delay_between_posts?: number
  daily_report?: boolean
  error_alerts?: boolean
}
