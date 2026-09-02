"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { Filter, Inbox, Plus } from "lucide-react"
import { toast } from "sonner"
import { WorkRow } from "@/components/work-bits"
import { statusMeta, WORK_QUEUE_DISPLAY_LIMIT, type WorkStatus } from "@/lib/hr-data"
import { useNavigation } from "@/lib/navigation"
import { ensureWorkHydrated, useWorkStore } from "@/lib/work-store"
import {
  linkedChatIdForWork,
  pruneTrivialChatWorkItems,
} from "@/lib/chat-work-bridge"
import { useChat } from "@/lib/chat-store"
import { PageContainer, PageHeader } from "@/components/management/shared"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type StatusFilter = WorkStatus | "all"

const filters: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All work" },
  { key: "needs_approval", label: statusMeta.needs_approval.label },
  { key: "running", label: statusMeta.running.label },
  { key: "queued", label: statusMeta.queued.label },
  { key: "blocked", label: statusMeta.blocked.label },
  { key: "completed", label: statusMeta.completed.label },
]

function WorkQueueContent() {
  const nav = useNavigation()
  const hydrated = useWorkStore((s) => s.hydrated)
  const items = useWorkStore((s) => s.items)
  const listByStatus = useWorkStore((s) => s.listByStatus)
  const setStatus = useWorkStore((s) => s.setStatus)
  const pruneMissingChats = useWorkStore((s) => s.pruneMissingChats)
  const [status, setFilterState] = useState<StatusFilter>("all")

  const isRunning = useChat((s) => s.isRunning)
  const pendingApproval = useChat((s) => s.pendingApproval)
  const activeId = useChat((s) => s.activeId)
  const sessionHydrated = useChat((s) => s.sessionHydrated)
  const conversations = useChat((s) => s.conversations)
  const knownChatIds = useMemo(
    () => new Set(conversations.map((c) => c.id)),
    [conversations],
  )

  useEffect(() => {
    ensureWorkHydrated()
    const t = window.setTimeout(() => pruneTrivialChatWorkItems(), 400)
    return () => window.clearTimeout(t)
  }, [])

  // Drop rows whose Copilot chat is gone (or whose id was PII-mangled).
  useEffect(() => {
    if (!hydrated || !sessionHydrated) return
    pruneMissingChats(knownChatIds)
  }, [hydrated, sessionHydrated, knownChatIds, pruneMissingChats])

  // Keep row status iterative while a Copilot run is live (even if you're on Work).
  useEffect(() => {
    if (!activeId) return
    const item = items.find((w) => linkedChatIdForWork(w) === activeId)
    if (!item) return
    if (pendingApproval && item.status !== "needs_approval") {
      setStatus(item.id, "needs_approval")
      return
    }
    if (isRunning && !pendingApproval && item.status !== "running") {
      setStatus(item.id, "running")
    }
  }, [activeId, isRunning, pendingApproval, items, setStatus])

  // Deep-link /work/[id] is handled by navigateToWorkDetail → real chat (no stub).
  useEffect(() => {
    if (nav.selectedWorkId) {
      nav.navigateToWorkDetail(nav.selectedWorkId)
    }
  }, [nav.selectedWorkId])

  useEffect(() => {
    try {
      const raw = new URLSearchParams(window.location.search).get("status")
      const valid: StatusFilter[] = [
        "needs_approval",
        "running",
        "queued",
        "blocked",
        "completed",
        "all",
      ]
      if (raw && valid.includes(raw as StatusFilter)) setFilterState(raw as StatusFilter)
    } catch {
      /* ignore */
    }
  }, [])

  const liveItems = useMemo(() => {
    if (!hydrated || !sessionHydrated) return []
    return listByStatus(status).filter((w) => {
      const chatId = linkedChatIdForWork(w)
      return Boolean(chatId && knownChatIds.has(chatId) && !/REDACTED/i.test(chatId))
    })
  }, [hydrated, sessionHydrated, listByStatus, status, knownChatIds])

  const startEmailTriage = () => {
    const brief =
      "Read the most recent 10 emails from the email inbox, summarize each one, and write the summary into a Markdown file. Highlight anything that needs a reply or follow-up."
    nav.startChatWithMessage(brief, { newChat: true, autoSend: true })
    toast.success("Started Copilot chat for email triage")
  }

  const setFilter = (key: StatusFilter) => {
    setFilterState(key)
    const path = key === "all" ? "/work" : `/work?status=${key}`
    try {
      window.history.replaceState(window.history.state, "", path)
    } catch {
      /* ignore */
    }
  }

  const liveCountFor = (key: StatusFilter) => {
    if (!sessionHydrated) return 0
    const pool = items.filter((w) => {
      const chatId = linkedChatIdForWork(w)
      return Boolean(chatId && knownChatIds.has(chatId))
    })
    if (key === "all") return Math.min(pool.length, WORK_QUEUE_DISPLAY_LIMIT)
    return Math.min(pool.filter((i) => i.status === key).length, WORK_QUEUE_DISPLAY_LIMIT)
  }

  return (
    <PageContainer>
      <PageHeader
        title="Work queue"
        icon={Inbox}
        description={`Live Copilot chats only — newest first, up to ${WORK_QUEUE_DISPLAY_LIMIT}. Click a row to open that chat.`}
        action={
          <Button onClick={startEmailTriage} className="inline-flex items-center gap-2">
            <Plus className="size-4" />
            Summarize recent emails
          </Button>
        }
      />

      <div className="dream-in">
        <div className="mb-4 flex flex-wrap gap-1.5">
          <Filter className="size-3.5 self-center text-muted-foreground mr-1" />
          {filters.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                status === f.key
                  ? "border-navy/40 bg-navy/10 text-navy font-semibold"
                  : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground",
              )}
            >
              {f.label}
              <span className="ml-1.5 tabular-nums opacity-70">{liveCountFor(f.key)}</span>
            </button>
          ))}
        </div>

        <div className="overflow-hidden rounded-xl border border-border/60 bg-card/40">
          {liveItems.length ? (
            liveItems.map((item) => <WorkRow key={item.id} item={item} />)
          ) : (
            <p className="py-12 text-center text-sm text-muted-foreground">
              {!hydrated || !sessionHydrated
                ? "Loading work queue…"
                : items.length === 0 || liveItems.length === 0
                  ? "No live Copilot chats in the queue. Run a substantial chat and it will appear here."
                  : "No work items match this filter."}
            </p>
          )}
        </div>
      </div>
    </PageContainer>
  )
}

export default function WorkPage() {
  return (
    <Suspense>
      <WorkQueueContent />
    </Suspense>
  )
}
