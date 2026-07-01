'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Menu, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { SessionSidebar } from '@/components/chat/SessionSidebar'
import { useToast } from '@/lib/contexts/ToastContext'
import { chatApi, BASE_URL } from '@/lib/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

export function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [sidebarRefresh, setSidebarRefresh] = useState(0)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { show } = useToast()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function autoResize() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  function startNewConversation() {
    setSessionId(null)
    setMessages([])
    setMobileSidebarOpen(false)
  }

  async function selectSession(id: string) {
    try {
      const { session, messages: history } = await chatApi.session(id)
      setSessionId(session.id)
      setMessages(history.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })))
      setMobileSidebarOpen(false)
    } catch {
      show('Impossible de charger cette conversation', 'error')
    }
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || streaming) return

    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    const userMsg: Message = { role: 'user', content: text }
    const assistantMsg: Message = { role: 'assistant', content: '', streaming: true }
    setMessages(prev => [...prev, userMsg, assistantMsg])
    setStreaming(true)

    // Session créée en base au premier message — pas au chargement de page
    // (évite de polluer la sidebar de conversations vides jamais utilisées).
    let activeSessionId = sessionId
    if (!activeSessionId) {
      try {
        const created = await chatApi.createSession()
        activeSessionId = created.id
        setSessionId(created.id)
      } catch {
        show('Impossible de créer la conversation', 'error')
        setStreaming(false)
        return
      }
    }

    const url = chatApi.streamUrl(activeSessionId, text)
    const es = new EventSource(url)
    let accumulated = ''

    es.onmessage = (e) => {
      if (e.data === '[DONE]') {
        es.close()
        setStreaming(false)
        setMessages(prev =>
          prev.map((m, i) =>
            i === prev.length - 1 ? { ...m, streaming: false, content: accumulated } : m
          )
        )
        setSidebarRefresh(k => k + 1)
        return
      }
      try {
        const data = JSON.parse(e.data)
        if (data.token) {
          accumulated += data.token
          setMessages(prev =>
            prev.map((m, i) =>
              i === prev.length - 1 ? { ...m, content: accumulated } : m
            )
          )
        }
        if (data.error) {
          show(data.error, 'error')
          es.close()
          setStreaming(false)
        }
      } catch { /* ignore */ }
    }

    es.onerror = () => {
      es.close()
      setStreaming(false)
      show('Erreur de connexion au chat', 'error')
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex h-[calc(100vh-64px)] relative">
      {/* Sidebar desktop */}
      <aside className="hidden md:block w-64 shrink-0 border-r border-gray-light bg-gray-pale/30">
        <SessionSidebar
          activeSessionId={sessionId}
          onSelect={selectSession}
          onNewConversation={startNewConversation}
          refreshKey={sidebarRefresh}
        />
      </aside>

      {/* Sidebar mobile (drawer) */}
      {mobileSidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-anthracite/40" onClick={() => setMobileSidebarOpen(false)} />
          <aside className="relative w-72 max-w-[80vw] bg-white h-full shadow-2xl">
            <div className="flex items-center justify-between px-3 py-3 border-b border-gray-light">
              <span className="font-heading font-semibold text-[13px] text-anthracite">Conversations</span>
              <button onClick={() => setMobileSidebarOpen(false)} aria-label="Fermer" className="p-1 text-gray-med">
                <X size={18} />
              </button>
            </div>
            <SessionSidebar
              activeSessionId={sessionId}
              onSelect={selectSession}
              onNewConversation={startNewConversation}
              refreshKey={sidebarRefresh}
            />
          </aside>
        </div>
      )}

      <div className="flex flex-col flex-1 min-w-0">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-light shrink-0 flex items-center gap-3">
        <button
          onClick={() => setMobileSidebarOpen(true)}
          className="md:hidden p-1.5 text-gray-dk hover:text-anthracite transition-colors"
          aria-label="Ouvrir l'historique des conversations"
        >
          <Menu size={20} />
        </button>
        <div>
          <h1 className="font-heading font-bold text-xl text-anthracite">Chat IA</h1>
          <p className="font-heading text-[12px] text-gray-dk">Assistant journalistique KORA</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
            <div className="w-16 h-16 rounded-xl bg-orange/10 flex items-center justify-center">
              <span className="font-heading font-extrabold text-2xl text-orange">/K</span>
            </div>
            <p className="font-heading font-semibold text-[15px] text-anthracite">Comment puis-je vous aider ?</p>
            <p className="font-heading text-[13px] text-gray-dk max-w-xs">
              Posez-moi une question sur l'actualité guinéenne, demandez de reformuler un article, ou explorez des idées éditoriales.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {[
                'Résume les dernières nouvelles de Guinée',
                'Écris un chapeau accrocheur',
                'Vérifie les mots-clés SEO',
              ].map(s => (
                <button
                  key={s}
                  onClick={() => { setInput(s); textareaRef.current?.focus() }}
                  className="font-heading text-[12px] bg-white border border-gray-light text-gray-dk rounded-full px-4 py-2 hover:border-orange hover:text-orange transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatBubble key={i} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 px-4 py-4 bg-white border-t border-gray-light">
        <div className="max-w-3xl mx-auto flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => { setInput(e.target.value); autoResize() }}
              onKeyDown={handleKeyDown}
              placeholder="Posez votre question… (Entrée pour envoyer, Maj+Entrée pour sauter une ligne)"
              rows={1}
              disabled={streaming}
              className="form-input resize-none pr-4 py-3 leading-relaxed disabled:opacity-50"
              aria-label="Message"
            />
          </div>
          <Button
            variant="primary"
            size="md"
            onClick={sendMessage}
            disabled={!input.trim() || streaming}
            loading={streaming}
            aria-label="Envoyer"
          >
            {streaming ? <Spinner size="sm" /> : 'Envoyer'}
          </Button>
        </div>
      </div>
      </div>
    </div>
  )
}

function ChatBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-[fadeIn_180ms_ease-out]`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-orange/20 flex items-center justify-center shrink-0 mr-3 mt-1">
          <span className="font-heading font-bold text-[11px] text-orange">/K</span>
        </div>
      )}
      <div
        className={
          `max-w-[75%] px-4 py-3 rounded-xl font-body text-[14px] leading-relaxed ` +
          `${isUser
            ? 'bg-orange text-white rounded-br-sm'
            : 'bg-white border border-gray-light text-anthracite rounded-bl-sm'
          }`
        }
      >
        <div
          className={`whitespace-pre-wrap ${message.streaming ? 'streaming-cursor' : ''}`}
          dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
        />
      </div>
    </div>
  )
}

function formatMarkdown(text: string): string {
  // Minimal markdown: **bold**, *italic*, `code`
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code class="bg-gray-pale px-1 rounded text-[13px] font-mono">$1</code>')
}
