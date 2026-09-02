"use client"

import { create } from "zustand"
import type {
  ChatMessage,
  RunStep,
  WorkItem,
  WorkSource,
  WorkStatus,
} from "@/lib/hr-data"
import { WORK_QUEUE_DISPLAY_LIMIT } from "@/lib/hr-data"

const PERSIST_KEY = "hr-copilot:work-queue:v1"

/** Legacy demo ids — drop from any localStorage cache. */
const LEGACY_SEED_IDS = new Set([
  "WRK-2019",
  "WRK-2024",
  "WRK-2029",
  "WRK-2033",
  "WRK-2036",
  "WRK-2038",
  "WRK-2041",
])

function withoutLegacySeed(items: WorkItem[]): WorkItem[] {
  return items
    .filter((w) => !LEGACY_SEED_IDS.has(w.id))
    .map((w) => {
      if (w.linkedChatId) return w
      const m = /^Chat · (.+)$/.exec((w.externalRef || "").trim())
      if (!m) return w
      return { ...w, linkedChatId: m[1] }
    })
}

/**
 * The Work Queue only tracks real Copilot conversations. A row is legitimate
 * only when it maps to a chat (linkedChatId or a `Chat · <id>` externalRef).
 * Everything else (intake stubs, ad-hoc/demo rows, legacy items) is fake and
 * must never appear.
 */
function isChatLinkedWork(w: WorkItem): boolean {
  if (w.linkedChatId && w.linkedChatId.trim()) return true
  return /^Chat · .+/.test((w.externalRef || "").trim())
}

function chatIdOf(w: WorkItem): string | null {
  if (w.linkedChatId?.trim()) return w.linkedChatId.trim()
  const m = /^Chat · (.+)$/.exec((w.externalRef || "").trim())
  return m?.[1] ?? null
}

function isCorruptedChatId(id: string): boolean {
  return /REDACTED/i.test(id)
}

/** Keep only real chat-linked rows and normalize their linkedChatId. */
function onlyRealChatWork(items: WorkItem[]): WorkItem[] {
  return withoutLegacySeed(items).filter(isChatLinkedWork)
}

type WorkState = {
  items: WorkItem[]
  hydrated: boolean
  usingDb: boolean
  hydrate: () => void
  getItem: (id: string) => WorkItem | undefined
  listByStatus: (status: WorkStatus | "all") => WorkItem[]
  createWorkItem: (input: {
    title: string
    summary?: string
    source?: WorkSource
    category?: string
    subject?: WorkItem["subject"]
    priority?: WorkItem["priority"]
    externalRef?: string
    linkedChatId?: string
    intakeId?: string
    automation?: string
    steps?: RunStep[]
  }) => WorkItem
  updateWorkItem: (id: string, patch: Partial<WorkItem>) => void
  setStatus: (id: string, status: WorkStatus) => void
  appendMessage: (id: string, message: ChatMessage) => void
  resolveApproval: (
    workId: string,
    messageId: string,
    decision: "approved" | "declined",
  ) => void
  advanceStepAfterApproval: (workId: string, approved: boolean) => void
  createFromIntake: (input: {
    intakeId: string
    title: string
    summary: string
    subject: WorkItem["subject"]
    priority?: WorkItem["priority"]
    externalRef?: string
  }) => WorkItem
  /** Confirm a completed item and drop it from the active queue (archives in DB). */
  confirmComplete: (id: string) => void
  /** Drop rows whose Copilot chat no longer exists on this device. */
  pruneMissingChats: (knownChatIds: Set<string>) => void
}

function nextWorkId(items: WorkItem[]): string {
  let max = 2000
  for (const item of items) {
    const m = /^WRK-(\d+)$/i.exec(item.id)
    if (m) max = Math.max(max, Number(m[1]))
  }
  return `WRK-${max + 1}`
}

function nowLabel(): string {
  return "just now"
}

function statusRank(status: WorkStatus): number {
  if (status === "needs_approval") return 0
  if (status === "running") return 1
  if (status === "queued") return 2
  if (status === "blocked") return 3
  return 4
}

/** Newest first, then hard-cap so the queue stays scannable. */
function rankAndLimitWork(items: WorkItem[]): WorkItem[] {
  return [...items]
    .sort((a, b) => {
      const ta = Date.parse(a.updatedAt || "") || 0
      const tb = Date.parse(b.updatedAt || "") || 0
      if (tb !== ta) return tb - ta
      const wrk = (id: string) => {
        const m = /^WRK-(\d+)$/i.exec(id)
        return m ? Number(m[1]) : 0
      }
      const nd = wrk(b.id) - wrk(a.id)
      if (nd !== 0) return nd
      return statusRank(a.status) - statusRank(b.status)
    })
    .slice(0, WORK_QUEUE_DISPLAY_LIMIT)
}

function persist(items: WorkItem[]) {
  if (typeof window === "undefined") return
  try {
    const clean = onlyRealChatWork(items)
    window.localStorage.setItem(PERSIST_KEY, JSON.stringify({ items: clean }))
  } catch {
    /* ignore */
  }
}

/**
 * Fire-and-forget DB writes. The zustand store stays the snappy source of truth
 * for the UI; these keep Cosmos in sync in the background. Only run when the
 * store loaded from the DB (usingDb), otherwise we'd write while offline.
 */
function syncItem(item: WorkItem) {
  if (typeof window === "undefined" || !useWorkStore.getState().usingDb) return
  void fetch(`/api/work/${item.id}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(item),
  }).catch(() => {})
}

function pushSync(id: string) {
  const item = useWorkStore.getState().getItem(id)
  if (item) syncItem(item)
}

function syncDelete(id: string) {
  if (typeof window === "undefined" || !useWorkStore.getState().usingDb) return
  void fetch(`/api/work/${id}`, { method: "DELETE" }).catch(() => {})
}

let hydrating = false

export const useWorkStore = create<WorkState>((set, get) => ({
  items: [],
  hydrated: false,
  usingDb: false,

  hydrate: () => {
    if (typeof window === "undefined" || get().hydrated || hydrating) return
    hydrating = true
    void (async () => {
      // 1. Prefer the database (including an empty queue — never invent demo rows).
      try {
        const res = await fetch("/api/work", { cache: "no-store" })
        const data = await res.json()
        if (res.ok && data.source === "db" && Array.isArray(data.items)) {
          const all = withoutLegacySeed(data.items as WorkItem[])
          const real = all.filter(isChatLinkedWork)
          // Purge any fake / chat-less rows left in Cosmos so they don't return.
          for (const fake of all.filter((w) => !isChatLinkedWork(w))) {
            void fetch(`/api/work/${fake.id}`, { method: "DELETE" }).catch(() => {})
          }
          set({ items: real, hydrated: true, usingDb: true })
          persist(real)
          hydrating = false
          return
        }
      } catch {
        /* fall through to local cache of *real* items only */
      }
      // 2. Offline cache of previously synced real items (strip legacy + fakes).
      try {
        const raw = window.localStorage.getItem(PERSIST_KEY)
        if (raw) {
          const parsed = JSON.parse(raw) as { items?: WorkItem[] }
          if (Array.isArray(parsed.items)) {
            const items = onlyRealChatWork(parsed.items)
            set({ items, hydrated: true, usingDb: false })
            persist(items)
            hydrating = false
            return
          }
        }
      } catch {
        /* ignore */
      }
      set({ items: [], hydrated: true, usingDb: false })
      hydrating = false
    })()
  },

  getItem: (id) => get().items.find((w) => w.id === id),

  listByStatus: (status) => {
    const items = get().items.filter(isChatLinkedWork)
    const filtered = status === "all" ? items : items.filter((w) => w.status === status)
    return rankAndLimitWork(filtered)
  },

  createWorkItem: (input) => {
    const id = nextWorkId(get().items)
    const nowIso = new Date().toISOString()
    const item: WorkItem = {
      id,
      title: input.title.trim() || "Untitled work",
      source: input.source ?? "adhoc",
      category: input.category ?? "Ad hoc",
      subject: input.subject ?? {
        name: "HR team",
        role: "Requester",
        initials: "HR",
      },
      status: "queued",
      automation: input.automation,
      priority: input.priority ?? "normal",
      sla: "Due in 1d",
      updated: nowLabel(),
      updatedAt: nowIso,
      externalRef: input.externalRef ?? (input.intakeId ? `Intake · ${input.intakeId}` : "Created in Copilot"),
      linkedChatId: input.linkedChatId,
      progress: 5,
      summary:
        input.summary?.trim() ||
        "New work item created from the Work Queue. Open the linked Copilot chat for the full thread.",
      steps: input.steps ?? [
        {
          id: "s1",
          label: "Triage request",
          detail: "Queued for Copilot",
          state: "active",
        },
        {
          id: "s2",
          label: "Gather context",
          state: "pending",
        },
        {
          id: "s3",
          label: "Execute / draft outcome",
          state: "pending",
        },
        {
          id: "s4",
          label: "Confirm with HR",
          state: "pending",
        },
      ],
      messages: [
        {
          id: "m1",
          role: "agent",
          time: nowLabel(),
          body: input.summary?.trim()
            ? `Opened ${id}.\n\n${input.summary.trim()}`
            : `Opened work item ${id}. Continue in the linked Copilot chat.`,
        },
      ],
      canvas: {
        kind: "checklist",
        items: [
          { label: "Status", value: "Queued", state: "pending" },
          { label: "Source", value: input.source ?? "adhoc", state: "ok" },
          ...(input.intakeId
            ? [{ label: "Intake", value: input.intakeId, state: "ok" as const }]
            : []),
        ],
      },
    }
    set((state) => {
      const items = [item, ...state.items]
      persist(items)
      return { items }
    })
    syncItem(item)
    return item
  },

  updateWorkItem: (id, patch) => {
    set((state) => {
      const items = state.items.map((w) =>
        w.id === id
          ? {
              ...w,
              ...patch,
              updated: nowLabel(),
              updatedAt: patch.updatedAt ?? new Date().toISOString(),
            }
          : w,
      )
      persist(items)
      return { items }
    })
    pushSync(id)
  },

  setStatus: (id, status) => {
    get().updateWorkItem(id, {
      status,
      progress:
        status === "completed"
          ? 100
          : status === "queued"
            ? 5
            : status === "running"
              ? 40
              : status === "needs_approval"
                ? 70
                : 50,
    })
  },

  appendMessage: (id, message) => {
    set((state) => {
      const items = state.items.map((w) =>
        w.id === id
          ? { ...w, messages: [...w.messages, message], updated: nowLabel() }
          : w,
      )
      persist(items)
      return { items }
    })
    pushSync(id)
  },

  resolveApproval: (workId, messageId, decision) => {
    const item = get().getItem(workId)
    if (!item) return
    const msg = item.messages.find((m) => m.id === messageId)
    // Persist decision on the message so Approve buttons don't return after reload.
    set((state) => {
      const items = state.items.map((w) => {
        if (w.id !== workId) return w
        return {
          ...w,
          updated: nowLabel(),
          messages: w.messages.map((m) =>
            m.id === messageId
              ? {
                  ...m,
                  approval: m.approval
                    ? { ...m.approval, description: `${decision}:${m.approval.description}` }
                    : m.approval,
                  body:
                    m.body +
                    (decision === "approved" ? "\n\n[Approved]" : "\n\n[Declined]"),
                }
              : m,
          ),
        }
      })
      persist(items)
      return { items }
    })
    get().appendMessage(workId, {
      id: `${messageId}-${decision}`,
      role: "agent",
      time: nowLabel(),
      body:
        decision === "approved"
          ? `Approved — continuing. ${msg?.approval?.target ? `Dispatching to ${msg.approval.target}.` : ""}`
          : "Declined. I've paused this step — tell me what to change.",
    })
    get().advanceStepAfterApproval(workId, decision === "approved")
    pushSync(workId)
  },

  advanceStepAfterApproval: (workId, approved) => {
    const item = get().getItem(workId)
    if (!item) return
    const steps: RunStep[] = item.steps.map((s) => ({ ...s }))
    const approvalIdx = steps.findIndex((s) => s.state === "approval")
    if (approvalIdx >= 0) {
      if (approved) {
        steps[approvalIdx] = { ...steps[approvalIdx]!, state: "done", duration: "now" }
        const next = steps.findIndex((s, i) => i > approvalIdx && s.state === "pending")
        if (next >= 0) steps[next] = { ...steps[next]!, state: "active" }
        const done = steps.filter((s) => s.state === "done").length
        const progress = Math.round((done / steps.length) * 100)
        const allDone = steps.every((s) => s.state === "done" || s.state === "failed")
        get().updateWorkItem(workId, {
          steps,
          progress,
          status: allDone ? "completed" : "running",
          canvas: {
            ...item.canvas,
            items: item.canvas.items.map((c) =>
              c.label === "Status"
                ? { ...c, value: allDone ? "Completed" : "Running", state: allDone ? "ok" : "pending" }
                : c,
            ),
          },
        })
      } else {
        steps[approvalIdx] = { ...steps[approvalIdx]!, state: "failed" }
        get().updateWorkItem(workId, {
          steps,
          status: "blocked",
          canvas: {
            ...item.canvas,
            items: item.canvas.items.map((c) =>
              c.label === "Status" ? { ...c, value: "Blocked", state: "warn" } : c,
            ),
          },
        })
      }
      return
    }
    get().setStatus(workId, approved ? "running" : "blocked")
  },

  createFromIntake: (input) => {
    const existing = get().items.find(
      (w) => w.externalRef.includes(input.intakeId) || w.id === `INT-${input.intakeId}`,
    )
    if (existing) return existing
    return get().createWorkItem({
      title: input.title,
      summary: input.summary,
      source: "ticketing",
      category: "Intake",
      subject: input.subject,
      priority: input.priority ?? "normal",
      externalRef: input.externalRef ?? `Intake · ${input.intakeId}`,
      intakeId: input.intakeId,
    })
  },

  confirmComplete: (id) => {
    set((state) => {
      const items = state.items.filter((w) => w.id !== id)
      persist(items)
      return { items }
    })
    syncDelete(id)
    // Close any Tasks intake tickets linked to this work item.
    if (typeof window !== "undefined") {
      void fetch(`/api/tasks/by-work/${encodeURIComponent(id)}`, {
        method: "DELETE",
      }).catch(() => {})
    }
  },

  pruneMissingChats: (knownChatIds) => {
    const orphans = get().items.filter((w) => {
      const chatId = chatIdOf(w)
      if (!chatId || isCorruptedChatId(chatId)) return true
      return !knownChatIds.has(chatId)
    })
    if (orphans.length === 0) return
    for (const w of orphans) {
      get().confirmComplete(w.id)
    }
  },
}))

/** Call once from Work Queue pages after mount. */
export function ensureWorkHydrated() {
  useWorkStore.getState().hydrate()
}
