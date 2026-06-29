// SSE client helpers — streaming token par token

export function createSSEStream(
  url: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError?: (e: Error) => void,
): () => void {
  const es = new EventSource(url)

  es.onmessage = (event) => {
    if (event.data === '[DONE]') {
      onDone()
      es.close()
      return
    }
    try {
      const parsed = JSON.parse(event.data)
      if (parsed.token) onToken(parsed.token)
      if (parsed.error) {
        onError?.(new Error(parsed.error))
        es.close()
      }
    } catch {
      // ignore malformed chunk
    }
  }

  es.onerror = () => {
    onError?.(new Error('SSE connection error'))
    es.close()
  }

  return () => es.close()
}

export function createAgentLogStream(
  url: string,
  onLog: (log: Record<string, unknown>) => void,
): () => void {
  const es = new EventSource(url)
  es.onmessage = (event) => {
    try {
      const log = JSON.parse(event.data)
      onLog(log)
    } catch {
      // ignore
    }
  }
  return () => es.close()
}
