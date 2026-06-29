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

const DEMO_LINES = [
  '{"ts":"2026-06-29T06:00:00Z","level":"INFO","node":"scheduler","message":"Démarrage cycle matinal"}',
  '{"ts":"2026-06-29T06:00:01Z","level":"INFO","node":"scraper","message":"Scraping 12 sources RSS"}',
  '{"ts":"2026-06-29T06:00:04Z","level":"OK","node":"selector","message":"5 articles sélectionnés pour rédaction"}',
  '{"ts":"2026-06-29T06:00:05Z","level":"INFO","node":"writer","message":"Rédaction article 1/5 — groq/llama-3.3-70b"}',
  '{"ts":"2026-06-29T06:00:12Z","level":"WARN","node":"llm_router","message":"Groq rate-limit — fallback sur gemini"}',
  '{"ts":"2026-06-29T06:00:13Z","level":"INFO","node":"writer","message":"Rédaction article 2/5 — gemini/gemini-2.0-flash"}',
  '{"ts":"2026-06-29T06:00:18Z","level":"OK","node":"writer","message":"Article 2/5 rédigé (847 mots)"}',
  '{"ts":"2026-06-29T06:00:19Z","level":"INFO","node":"illustrator","message":"Génération image via fal.ai/flux"}',
  '{"ts":"2026-06-29T06:00:25Z","level":"OK","node":"illustrator","message":"Image générée — upload WP media"}',
  '{"ts":"2026-06-29T06:00:26Z","level":"INFO","node":"publisher","message":"HITL — en attente validation humaine"}',
  '{"ts":"2026-06-29T06:01:45Z","level":"OK","node":"publisher","message":"Article approuvé — publication WordPress"}',
  '{"ts":"2026-06-29T06:01:47Z","level":"OK","node":"publisher","message":"Publié : https://kakilambe.com/?p=4821"}',
]

export default function LogsPage() {
  const [lines, setLines]     = useState<LogEntry[]>(DEMO_LINES.map(parseLine))
  const [paused, setPaused]   = useState(false)
  const [filter, setFilter]   = useState<string>('ALL')
  const [search, setSearch]   = useState('')
  const bottomRef             = useRef<HTMLDivElement>(null)
  const pausedRef             = useRef(paused)
  pausedRef.current           = paused

  useEffect(() => {
    const es = new EventSource(`${BASE_URL}/stream/logs`)
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
          <p className="font-mono text-[12px] mt-0.5" style={{ color: SYS_MUTED }}>Flux SSE en temps réel</p>
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
          <div className="flex items-center justify-center h-32" style={{ color: SYS_MUTED }}>
            Aucun log à afficher
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
