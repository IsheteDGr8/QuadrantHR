"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import {
  Sparkles,
  RefreshCw,
  ChevronDown,
  X,
  AlertTriangle,
  SendHorizonal,
  Clock,
} from "lucide-react"

type QA = { question: string; answer: string; pending?: boolean }

interface AiSummaryPanelProps {
  pageContext: unknown
  className?: string
}

/* ---------------------- task highlight helpers -------------------------- */

const TASK_ID_RE = /\bIN-\d+\b/g

function highlightTask(id: string) {
  const el = document.querySelector<HTMLElement>(`[data-intake-id="${id}"]`)
  if (!el) return false
  el.scrollIntoView({ behavior: "smooth", block: "center" })
  el.classList.remove("intake-flash") // restart animation if already flashing
  // Force a reflow so re-adding the class re-triggers the animation
  void el.offsetWidth
  el.classList.add("intake-flash")
  window.setTimeout(() => el.classList.remove("intake-flash"), 2600)
  return true
}

/** Injected once; animates the flash on task cards. */
function FlashStyles() {
  return (
    <style>{`
      @keyframes intakeFlashPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(255, 107, 74, 0); }
        20%, 60% { box-shadow: 0 0 0 4px rgba(255, 107, 74, 0.35); background-color: rgba(255, 107, 74, 0.07); }
        40%, 80% { box-shadow: 0 0 0 2px rgba(255, 107, 74, 0.16); }
      }
      .intake-flash {
        animation: intakeFlashPulse 1.3s ease-in-out 2;
        border-radius: 12px;
      }
      @media (prefers-reduced-motion: reduce) {
        .intake-flash {
          animation: none;
          box-shadow: 0 0 0 3px rgba(255, 107, 74, 0.4);
        }
      }
    `}</style>
  )
}

/* ---------- tiny markdown renderer (bold + bullets + ⏰ + ID chips) ------ */

function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = []
  let key = 0
  // First split on bold spans, then find task IDs inside each plain piece
  const boldParts = text.split(/(\*\*[^*]+\*\*)/g)
  for (const part of boldParts) {
    const isBold = part.startsWith("**") && part.endsWith("**")
    const inner = isBold ? part.slice(2, -2) : part
    const pieces: React.ReactNode[] = []
    let last = 0
    for (const m of inner.matchAll(TASK_ID_RE)) {
      const idx = m.index ?? 0
      if (idx > last) pieces.push(inner.slice(last, idx))
      const id = m[0]
      pieces.push(
        <button
          key={`id-${key++}`}
          onClick={() => highlightTask(id)}
          title={`Show ${id} on the page`}
          className="mx-0.5 inline-flex items-center rounded-md bg-[#FF6B4A]/12 px-1.5 py-0.5 font-mono text-xs font-semibold text-[#C24E2E] hover:bg-[#FF6B4A]/22"
        >
          {id}
        </button>
      )
      last = idx + id.length
    }
    if (last < inner.length) pieces.push(inner.slice(last))
    nodes.push(
      isBold ? (
        <strong key={key++} className="font-semibold text-foreground">
          {pieces}
        </strong>
      ) : (
        <React.Fragment key={key++}>{pieces}</React.Fragment>
      )
    )
  }
  return nodes
}

function AiText({ text }: { text: string }) {
  const lines = text.split("\n")
  const blocks: React.ReactNode[] = []
  let bullets: string[] = []
  let key = 0

  const flushBullets = () => {
    if (!bullets.length) return
    blocks.push(
      <ul key={key++} className="my-1.5 space-y-1.5">
        {bullets.map((b, i) => (
          <li key={i} className="flex gap-2 text-sm leading-relaxed text-slate-700">
            <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-[#FF6B4A]/60" />
            <span>{renderInline(b)}</span>
          </li>
        ))}
      </ul>
    )
    bullets = []
  }

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) {
      flushBullets()
      continue
    }
    if (/^[-*•]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*•]\s+/, ""))
      continue
    }
    flushBullets()
    if (line.startsWith("⏰")) {
      blocks.push(
        <div
          key={key++}
          className="my-1.5 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-relaxed text-amber-900"
        >
          <Clock className="mt-0.5 h-3.5 w-3.5 flex-none" aria-hidden />
          <span>{renderInline(line.replace(/^⏰\s*/, ""))}</span>
        </div>
      )
    } else {
      blocks.push(
        <p key={key++} className="my-1.5 text-sm leading-relaxed text-slate-700">
          {renderInline(line)}
        </p>
      )
    }
  }
  flushBullets()
  return <div>{blocks}</div>
}

/* ------------------------------- panel ---------------------------------- */

export function AiSummaryPanel({ pageContext, className }: AiSummaryPanelProps) {
  const [open, setOpen] = React.useState(true)
  const [collapsed, setCollapsed] = React.useState(false)
  const [briefing, setBriefing] = React.useState<string | null>(null)
  const [briefingError, setBriefingError] = React.useState<string | null>(null)
  const [loadingBriefing, setLoadingBriefing] = React.useState(false)
  const [qa, setQa] = React.useState<QA[]>([])
  const [question, setQuestion] = React.useState("")
  const scrollRef = React.useRef<HTMLDivElement>(null)
  // Keep latest context for asks/refresh without re-triggering the auto briefing.
  const pageContextRef = React.useRef(pageContext)
  pageContextRef.current = pageContext

  const fetchBriefing = React.useCallback(async () => {
    setLoadingBriefing(true)
    setBriefingError(null)
    try {
      const res = await fetch("/api/ai-summary", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ mode: "briefing", pageContext: pageContextRef.current }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? res.statusText)
      setBriefing(data.text)
    } catch (err) {
      setBriefingError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setLoadingBriefing(false)
    }
  }, [])

  // Run once per mount (one visit). Tab switches must not remount this panel.
  // Leaving Tasks and coming back remounts IntakePage → briefing runs again.
  React.useEffect(() => {
    void fetchBriefing()
  }, [fetchBriefing])

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [qa, briefing])

  async function askQuestion() {
    const q = question.trim()
    if (!q) return
    setQuestion("")
    setQa((prev) => [...prev, { question: q, answer: "", pending: true }])
    try {
      const res = await fetch("/api/ai-summary", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ mode: "question", question: q, pageContext: pageContextRef.current }),
      })
      const data = await res.json()
      const answer = res.ok
        ? data.text
        : `Couldn't answer that: ${data.error ?? res.statusText}`
      setQa((prev) =>
        prev.map((item, i) =>
          i === prev.length - 1 ? { ...item, answer, pending: false } : item
        )
      )
      // Auto-flash the first task the answer points to
      if (res.ok) {
        const firstId = answer.match(TASK_ID_RE)?.[0]
        if (firstId) window.setTimeout(() => highlightTask(firstId), 300)
      }
    } catch {
      setQa((prev) =>
        prev.map((item, i) =>
          i === prev.length - 1
            ? { ...item, answer: "Couldn't reach the AI service.", pending: false }
            : item
        )
      )
    }
  }

  if (!open || collapsed) {
    return (
      <button
        type="button"
        onClick={() => {
          setOpen(true)
          setCollapsed(false)
        }}
        aria-label="Open today's briefing"
        className={cn(
          "fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full",
          "bg-gradient-to-br from-[#FF8F6B] to-[#FF6B4A] text-white",
          "shadow-[0_12px_40px_-8px_rgba(255,107,74,0.75)]",
          "ring-4 ring-[#FF6B4A]/20 transition-transform hover:scale-105 hover:ring-[#FF6B4A]/35 active:scale-95",
          "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#FF6B4A]/50",
          className,
        )}
      >
        <Sparkles className="h-6 w-6" aria-hidden />
        <span className="sr-only">Today's briefing</span>
      </button>
    )
  }

  return (
    <div
      className={cn(
        "fixed bottom-4 right-4 z-40 w-[420px] max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-[#FFD9C8] bg-white shadow-2xl",
        className
      )}
    >
      <FlashStyles />
      {/* Header */}
      <div className="flex items-center justify-between bg-gradient-to-r from-[#FF8F6B] to-[#FF6B4A] px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4" aria-hidden />
          <span className="text-sm font-semibold">Today's briefing</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={fetchBriefing}
            disabled={loadingBriefing}
            aria-label="Refresh briefing"
            className="rounded-md p-1.5 hover:bg-card/10 disabled:opacity-50"
          >
            <RefreshCw className={cn("h-4 w-4", loadingBriefing && "animate-spin")} />
          </button>
          <button
            onClick={() => setCollapsed(true)}
            aria-label="Minimize briefing"
            className="rounded-md p-1.5 hover:bg-card/10"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              setCollapsed(true)
              setOpen(false)
            }}
            aria-label="Minimize briefing"
            className="rounded-md p-1.5 hover:bg-card/10"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <>
          {/* Body */}
          <div ref={scrollRef} className="max-h-[400px] space-y-4 overflow-y-auto p-4">
            {loadingBriefing && (
              <div className="space-y-2" aria-label="Generating briefing">
                <div className="h-3 w-3/4 animate-pulse rounded bg-slate-200" />
                <div className="h-3 w-full animate-pulse rounded bg-slate-200" />
                <div className="h-3 w-5/6 animate-pulse rounded bg-slate-200" />
              </div>
            )}

            {!loadingBriefing && briefingError && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-center">
                <AlertTriangle className="mx-auto mb-2 h-5 w-5 text-red-500" aria-hidden />
                <p className="text-sm font-medium text-red-800">
                  Couldn't generate today's briefing
                </p>
                <p className="mt-1 text-xs text-red-600">{briefingError}</p>
                <button
                  onClick={fetchBriefing}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-red-700 ring-1 ring-red-200 hover:bg-red-100"
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Retry
                </button>
              </div>
            )}

            {!loadingBriefing && briefing && <AiText text={briefing} />}

            {/* Q&A thread */}
            {qa.map((item, i) => (
              <div key={i} className="space-y-2">
                <div className="ml-8 rounded-xl rounded-br-sm bg-gradient-to-br from-[#FF8F6B] to-[#FF6B4A] px-3 py-2 text-sm text-white">
                  {item.question}
                </div>
                <div className="mr-8 rounded-xl rounded-bl-sm border border-[#FFD9C8] bg-[#FFF6F0] px-3 py-2">
                  {item.pending ? (
                    <span className="inline-block h-3 w-24 animate-pulse rounded bg-slate-200 align-middle" />
                  ) : (
                    <AiText text={item.answer} />
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Ask bar */}
          <div className="border-t border-slate-200 p-3">
            <div className="flex items-center gap-2 rounded-xl border border-[#FFD9C8] bg-[#FFF6F0] px-3 py-1.5 focus-within:border-[#FF6B4A] focus-within:ring-2 focus-within:ring-[#FF6B4A]/25">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && askQuestion()}
                placeholder="Ask about anything on this page…"
                aria-label="Ask a question about this page"
                className="w-full bg-transparent py-1 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
              />
              <button
                onClick={askQuestion}
                disabled={!question.trim()}
                aria-label="Send question"
                className="rounded-lg p-1.5 text-[#FF6B4A] hover:bg-[#FFE8DE] disabled:opacity-40"
              >
                <SendHorizonal className="h-4 w-4" />
              </button>
            </div>
          </div>
      </>
    </div>
  )
}