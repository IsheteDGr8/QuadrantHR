"use client"

import * as React from "react"
import type { IntakeItem } from "@/lib/intake-data"
import { ensureWorkHydrated, useWorkStore } from "@/lib/work-store"
import type { WorkItem } from "@/lib/hr-data"
import { parseChatIdFromWorkRef } from "@/lib/chat-work-bridge"

export interface TaskStats {
  open: number
  needsJudgement: number
  readyToRelease: number
  arrivedToday: number
  autoAbsorbed: number
}

interface UseTasksResult {
  items: IntakeItem[]
  stats: TaskStats
  loading: boolean
  /** True when Cosmos is unreachable / not configured (empty list, not dummy data). */
  usingFallback: boolean
  refresh: () => void
}

const EMPTY_STATS: TaskStats = {
  open: 0,
  needsJudgement: 0,
  readyToRelease: 0,
  arrivedToday: 0,
  autoAbsorbed: 0,
}

function workApprovalToIntake(w: WorkItem): IntakeItem {
  const chatId = parseChatIdFromWorkRef(w.externalRef)
  return {
    id: `APR-${w.id}`,
    subject: w.title,
    requester: w.subject?.name
      ? w.subject
      : { name: "Vera", role: "Copilot", initials: "V" },
    channel: "chat",
    clusterId: "copilot-approvals",
    topic: "Copilot · needs your action",
    urgency: w.priority === "urgent" ? "urgent" : w.priority === "high" ? "high" : "normal",
    age: w.updated || "just now",
    ageMinutes: 0,
    due: "Now",
    state: "waiting",
    disposition: "assist",
    confidence: 90,
    snippet:
      w.summary ||
      (chatId
        ? `Waiting on your approval in Copilot chat (${chatId}).`
        : "Waiting on your approval to continue this run."),
    suggestion: "Open the linked Copilot chat to approve or decline.",
    linkedWorkId: w.id,
  }
}

function computeClientStats(items: IntakeItem[]): TaskStats {
  const open = items.filter((i) => i.state !== "handled")
  return {
    open: open.length,
    needsJudgement: open.filter((i) => i.disposition === "human").length,
    readyToRelease: items.filter((i) => i.disposition === "auto" && i.state === "new").length,
    arrivedToday: open.length,
    autoAbsorbed: items.filter((i) => i.disposition === "auto").length,
  }
}

function mergeTicketsWithApprovals(
  tickets: IntakeItem[],
  approvals: WorkItem[],
): IntakeItem[] {
  const uniqueTickets = dedupeIntakeItems(tickets)
  const linked = new Set(
    uniqueTickets.map((t) => t.linkedWorkId).filter(Boolean) as string[],
  )
  const fromWork = approvals
    .filter((w) => w.status === "needs_approval")
    .filter((w) => !linked.has(w.id))
    .map(workApprovalToIntake)

  return dedupeIntakeItems([...uniqueTickets, ...fromWork])
}

function dedupeIntakeItems(items: IntakeItem[]): IntakeItem[] {
  const seen = new Set<string>()
  const out: IntakeItem[] = []
  for (const item of items) {
    if (!item?.id || seen.has(item.id)) continue
    seen.add(item.id)
    out.push(item)
  }
  return out
}

/**
 * Loads real intake tickets from Cosmos and merges Copilot runs that need
 * human approval. Never falls back to bundled demo tickets.
 */
export function useTasks(): UseTasksResult {
  const [tickets, setTickets] = React.useState<IntakeItem[]>([])
  const [stats, setStats] = React.useState<TaskStats>(EMPTY_STATS)
  const [loading, setLoading] = React.useState(true)
  const [usingFallback, setUsingFallback] = React.useState(false)

  const workItems = useWorkStore((s) => s.items)
  const workHydrated = useWorkStore((s) => s.hydrated)

  const load = React.useCallback(async () => {
    setLoading(true)
    ensureWorkHydrated()
    try {
      const res = await fetch("/api/tasks", { cache: "no-store" })
      const data = await res.json()
      if (res.ok && data.source === "db" && Array.isArray(data.tickets)) {
        setTickets(data.tickets as IntakeItem[])
        if (data.stats) setStats(data.stats as TaskStats)
        setUsingFallback(false)
      } else {
        setTickets([])
        setStats(EMPTY_STATS)
        setUsingFallback(true)
      }
    } catch {
      setTickets([])
      setStats(EMPTY_STATS)
      setUsingFallback(true)
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void load()
  }, [load])

  const items = React.useMemo(() => {
    const approvals = workHydrated ? workItems : []
    return mergeTicketsWithApprovals(tickets, approvals)
  }, [tickets, workItems, workHydrated])

  const mergedStats = React.useMemo(() => {
    if (items.length === tickets.length && stats.open >= 0 && !usingFallback) {
      // Recompute so work-queue approvals count toward open / assist.
      return computeClientStats(items)
    }
    return computeClientStats(items)
  }, [items, tickets.length, stats.open, usingFallback])

  return { items, stats: mergedStats, loading, usingFallback, refresh: load }
}
