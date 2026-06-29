'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

// ── useAsync ────────────────────────────────────────────────────────────────
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = []
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fn()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue')
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => { run() }, [run])

  return { data, loading, error, refetch: run }
}

// ── useMutation ─────────────────────────────────────────────────────────────
export function useMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mutate = useCallback(async (args: TArgs): Promise<TResult | null> => {
    setLoading(true)
    setError(null)
    try {
      const result = await fn(args)
      return result
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur inconnue'
      setError(msg)
      return null
    } finally {
      setLoading(false)
    }
  }, [fn])

  return { mutate, loading, error }
}

// ── useInterval ─────────────────────────────────────────────────────────────
export function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn)
  useEffect(() => { ref.current = fn })
  useEffect(() => {
    if (ms === null) return
    const id = setInterval(() => ref.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}

// ── useSSE ──────────────────────────────────────────────────────────────────
export function useSSE<T = Record<string, unknown>>(
  url: string | null,
  onMessage: (data: T) => void,
) {
  useEffect(() => {
    if (!url) return
    const es = new EventSource(url)
    es.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data) as T) } catch { /* ignore */ }
    }
    return () => es.close()
  }, [url, onMessage])
}

// ── useDebounce ─────────────────────────────────────────────────────────────
export function useDebounce<T>(value: T, ms = 400): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}
