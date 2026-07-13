'use client'

import { useEffect, useRef, useState } from 'react'
import { BASE_URL } from '@/lib/api'

const SYS_SURFACE = '#141413'
const SYS_BORDER  = '#2a2a28'
const SYS_MUTED   = '#5a5956'

interface LogEntry {
  ts: string
  level: 'INFO' | 'OK' | 'WARN' | 'ERROR' | 'DEBUG'
  node: string
  message: string
  raw: string
}

const LEVEL_COLOR: Record<string, string> = {
  INFO:  '#3d6e99',
  OK:    '#48bb78',
  WARN:  '#ecc94b',
  ERROR: '#fc8181',
  DEBUG: '#5a5956',
}

function parseLine(line: string): LogEntry {
  try {
    const obj = JSON.parse(line)
    return {
      ts:      obj.timestamp ?? obj.ts ?? new Date().toISOString(),
      level:   (obj.level ?? 'INFO').toUpperCase() as LogEntry['level'],
      node:    obj.node ?? obj.logger ?? '—',
      message: obj.message ?? obj.msg ?? line,
      raw:     line,
    }
  } catch {
    const m = line.match(/^(\d{4}-\d\d-\d\dT[\d:.Z]+)\s+(\w+)\s+(.*)$/)
    return {
      ts:      m?.[1] ?? new Date().toISOString(),
      level:   (m?.[2] ?? 'INFO').toUpperCase() as LogEntry['level'],
      node:    '',
      message: m?.[3] ?? line,
      raw:     line,
    }
  }
}

export default function LogsPage() {
  const [lines, setLines]     = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const [paused, setPaused]   = useState(false)
  const [filter, setFilter]   = useState<string>('ALL')
  const [search, setSearch]   = useState('')
  const bottomRef             = useRef<HTMLDivElement>(null)
  const pausedRef             = useRef(paused)
  pausedRef.current           = paused

  // TODO backend : /stream/logs n'existe pas — seul /api/agent/stream existe,
  // et il exige un cycle_id (suivi d'un cycle précis, pas un flux global tous
  // cycles confondus). Tant qu'un vrai endpoint de flux global n'existe pas,
  // cet écran affiche honnêtement "non connecté" plutôt que des lignes de
  // démonstration fictives présentées comme des logs réels.
  useEffect(() => {
    const es = new EventSource(`${BASE_URL}/stream/logs`)
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    es.onmessage = (e) => {
      if (pausedRef.current) return
      const entry = parseLine(e.data)
      setLines(prev => [...prev.slice(-500), entry])
    }
    return () => es.close()
  }, [])

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, paused])

  const visible = lines.filter(l => {
    if (filter !== 'ALL' && l.level !== filter) return false
    if (search && !l.message.toLowerCase().includes(search.toLowerCase()) && !l.node.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="max-w-5xl flex flex-col h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="font-mono font-bold text-xl text-white">Terminal Logs</h1>
          <p className="font-mono text-[12px] mt-0.5" style={{ color: connected ? '#48bb78' : '#fc8181' }}>
            {connected ? '● Flux SSE connecté' : '○ Non connecté — endpoint /stream/logs absent côté backend'}
          </p>
        </div>
        <button
          onClick={() => setPaused(p => !p)}
          className="font-mono text-[11px] px-3 py-1.5 rounded border transition-colors"
          style={{
            color: paused ? '#ecc94b' : SYS_MUTED,
            borderColor: paused ? 'rgba(236,201,75,.3)' : '#2a2a28',
          }}
        >
          {paused ? '▶ Reprendre' : '⏸ Pause'}
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-3 shrink-0 flex-wrap">
        <input
          id="log-search"
          type="search"
          aria-label="Filtrer les logs"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Filtrer…"
          className="flex-1 min-w-0 px-3 py-1.5 rounded font-mono text-[12px] text-white bg-[#0c0c0b] border border-[#2a2a28] focus:border-[#3d6e99] focus:outline-none"
        />
        {(['ALL', 'INFO', 'OK', 'WARN', 'ERROR', 'DEBUG'] as const).map(lvl => (
          <button
            key={lvl}
            onClick={() => setFilter(lvl)}
            className="font-mono text-[10px] px-2 py-1 rounded transition-colors"
            style={{
              color:      filter === lvl ? (LEVEL_COLOR[lvl] ?? '#fff') : SYS_MUTED,
              background: filter === lvl ? `${LEVEL_COLOR[lvl] ?? '#fff'}18` : 'transparent',
              border:     `1px solid ${filter === lvl ? (LEVEL_COLOR[lvl] ?? '#fff') + '40' : SYS_BORDER}`,
            }}
          >
            {lvl}
          </button>
        ))}
        <button
          onClick={() => setLines([])}
          className="font-mono text-[10px] px-2 py-1 rounded border transition-colors"
          style={{ color: SYS_MUTED, borderColor: SYS_BORDER }}
        >
          Vider
        </button>
      </div>

      {/* Terminal */}
      <div
        className="flex-1 overflow-y-auto rounded-lg border p-4 font-mono text-[12px] leading-relaxed"
        style={{ background: '#050504', borderColor: SYS_BORDER }}
        aria-live="polite"
        aria-label="Logs terminal"
      >
        {visible.length === 0 && (
          <div className="flex items-center justify-center h-32 text-center px-6" style={{ color: SYS_MUTED }}>
            {connected ? 'Aucun log à afficher' : "En attente de connexion — aucun endpoint de flux global n'est encore branché côté backend."}
          </div>
        )}
        {visible.map((l, i) => (
          <div
            key={i}
            className="flex items-start gap-3 py-0.5 hover:bg-white/[.03] rounded px-1 -mx-1"
          >
            <span className="text-[10px] shrink-0 mt-0.5" style={{ color: SYS_MUTED }}>
              {l.ts.slice(11, 19)}
            </span>
            <span
              className="shrink-0 font-bold text-[10px] w-12 text-right"
              style={{ color: LEVEL_COLOR[l.level] ?? '#fff' }}
            >
              {l.level}
            </span>
            {l.node && (
              <span className="shrink-0 text-[10px]" style={{ color: '#3d6e99' }}>
                [{l.node}]
              </span>
            )}
            <span style={{ color: '#c9c8c2' }}>{l.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="flex items-center justify-between mt-2 shrink-0">
        <span className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>
          {visible.length} ligne{visible.length > 1 ? 's' : ''} affichée{visible.length > 1 ? 's' : ''}
          {paused && <span className="ml-2 text-yellow-500">· PAUSE</span>}
        </span>
        <span className="font-mono text-[10px]" style={{ color: SYS_MUTED }}>
          {lines.length} / 500 max
        </span>
      </div>
    </div>
  )
}
