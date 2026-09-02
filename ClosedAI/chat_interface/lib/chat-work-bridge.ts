"use client"

import { useWorkStore, ensureWorkHydrated } from "@/lib/work-store"
import type { RunStep, WorkStatus } from "@/lib/hr-data"

/** Minimal activity signal — avoids importing chat-store (circular). */
export type WorkActivitySignal = {
  toolName?: string
  category?: string
  title?: string
  detail?: string
  status?: string
}

/**
 * Work Queue mirrors *substantial* Copilot runs only — not small talk.
 * One chat → one work_queue item, keyed by `Chat · <chatId>` in externalRef.
 */

function chatRef(chatId: string) {
  return `Chat · ${chatId}`
}

export function parseChatIdFromWorkRef(externalRef: string): string | null {
  const m = /^Chat · (.+)$/.exec(externalRef.trim())
  return m?.[1] ?? null
}

/** Resolve the real Copilot chat id for a work row (field or `Chat · …` ref). */
export function linkedChatIdForWork(item: {
  linkedChatId?: string
  externalRef: string
}): string | null {
  if (item.linkedChatId?.trim()) return item.linkedChatId.trim()
  return parseChatIdFromWorkRef(item.externalRef)
}

function findByChat(chatId: string) {
  return useWorkStore
    .getState()
    .items.find((w) => w.externalRef === chatRef(chatId) || w.id === `INT-${chatId}`)
}

/** Short greetings / thanks that must never open a work item by themselves. */
export function isTrivialChatPrompt(text: string): boolean {
  const t = text.replace(/\s+/g, " ").trim().toLowerCase()
  if (!t) return true
  if (t.length > 80) return false
  const trivial = [
    /^(hi|hello|hey|yo|sup|hiya|howdy)([!.\s]*| there[!.\s]*| team[!.\s]*)?$/,
    /^(good\s+)?(morning|afternoon|evening)[!.\s]*$/,
    /^(thanks|thank you|thx|ty)[!.\s]*$/,
    /^(ok|okay|k|cool|great|got it|sounds good)[!.\s]*$/,
    /^(bye|goodbye|see you|cya)[!.\s]*$/,
    /^how are you[!?\s]*$/,
    /^what('s| is) up[!?\s]*$/,
  ]
  return trivial.some((re) => re.test(t))
}

const META_TOOLS = new Set(["finish", "think"])

/** Tools that mean real operational work (MCP, HR data, docs, outbound). */
function isSubstantialTool(name: string | undefined): boolean {
  if (!name || META_TOOLS.has(name)) return false
  if (name === "invoke_skill") return true
  if (name === "activate_integration") return true
  if (
    /^(employee_lookup|pto_balance|org_chart|benefits_lookup|policy_search|write_workspace_file)$/.test(
      name,
    )
  ) {
    return true
  }
  if (
    /^(query_cosmos|list_collections|count_documents|get_sample_documents|describe_container|find_implied_links|get_partition_key_info|get_indexing_policy|list_distinct_values|upsert_document|create_item|delete_item)$/.test(
      name,
    )
  ) {
    return true
  }
  if (/^(query|list_indexes|get_index)$/.test(name)) return true
  if (/^office_/.test(name)) return true
  if (
    /^(list_emails|list_slack_channels|send_email|send_slack_message|send_teams_message)$/.test(name)
  ) return true
  // Prefixed MCP names: gmail_*, cosmos-db_*, azure-ai-search_*, etc.
  if (/^[a-z0-9-]+_/i.test(name) && !META_TOOLS.has(name)) {
    const base = name.replace(/^[a-z0-9-]+_/i, "")
    if (base && base !== name) return isSubstantialTool(base) || true
  }
  return false
}

export function shouldPromoteToWorkQueue(
  activity: WorkActivitySignal[],
  opts?: { awaitingApproval?: boolean },
): boolean {
  if (opts?.awaitingApproval) return true

  const tools = activity.filter(
    (s) => s.toolName && !META_TOOLS.has(s.toolName),
  )
  const realSkillInvokes = tools.filter((s) => s.toolName === "invoke_skill")
  const skills = tools.filter(
    (s) => s.toolName === "invoke_skill" || s.category === "skill",
  )
  const substantial = tools.filter((s) => isSubstantialTool(s.toolName))
  const uniqueSubstantial = new Set(substantial.map((s) => s.toolName)).size

  // Real invoke_skill (not UI keyword hint) = domain work starting
  if (realSkillInvokes.length >= 1) return true
  // Multiple keyword/skill signals or MCP/data tools
  if (skills.length >= 2) return true
  if (uniqueSubstantial >= 2) return true
  if (substantial.length >= 3) return true
  // Single MCP/data/doc/email action is still "real work"
  if (substantial.some((s) => s.toolName !== "invoke_skill")) return true

  return false
}

function stepsFromActivity(activity: WorkActivitySignal[], status: WorkStatus): RunStep[] {
  const tools = activity.filter((s) => s.toolName && !META_TOOLS.has(s.toolName))
  const skills = tools.filter(
    (s) => s.toolName === "invoke_skill" || s.category === "skill",
  )
  const actions = tools.filter(
    (s) => s.toolName !== "invoke_skill" && s.category !== "skill",
  )
  const skillNames = [
    ...new Set(
      skills
        .map((s) => s.detail || s.title)
        .filter(Boolean)
        .map(String),
    ),
  ].slice(0, 3)
  const actionNames = [
    ...new Set(actions.map((s) => s.toolName).filter(Boolean) as string[]),
  ].slice(0, 4)

  const anyStarted = tools.length > 0
  const skillsDone =
    skills.length > 0 && skills.every((s) => s.status === "success" || s.status === "error")
  const skillsRunning = skills.some((s) => s.status === "running")
  const actionsDone =
    actions.length > 0 && actions.every((s) => s.status === "success" || s.status === "error")
  const actionsRunning = actions.some((s) => s.status === "running")

  const s1: RunStep = {
    id: "s1",
    label: "Understand request",
    detail: anyStarted ? "Request classified" : "Waiting to start",
    state: anyStarted ? "done" : status === "running" ? "active" : "pending",
  }

  let s2state: RunStep["state"] = "pending"
  if (skillsRunning) s2state = "active"
  else if (skillsDone || (actions.length > 0 && skills.length === 0 && anyStarted)) s2state = "done"
  else if (skills.length > 0) s2state = "active"

  const s2: RunStep = {
    id: "s2",
    label: "Gather context / skills",
    detail:
      skillNames.length > 0
        ? skillNames.join(" · ")
        : anyStarted
          ? "Loading domain guidance & data"
          : undefined,
    state: s2state,
  }

  let s3state: RunStep["state"] = "pending"
  if (actionsRunning) s3state = "active"
  else if (actionsDone) s3state = "done"
  else if (actions.length > 0) s3state = "active"
  else if (s2state === "done" && status === "running") s3state = "active"

  const s3: RunStep = {
    id: "s3",
    label: "Execute / tools",
    detail: actionNames.length ? actionNames.join(", ") : undefined,
    state: s3state,
    system: actionNames.length ? "MCP / client tools" : undefined,
  }

  let s4state: RunStep["state"] = "pending"
  if (status === "needs_approval") s4state = "approval"
  else if (status === "completed") s4state = "done"
  else if (status === "blocked") s4state = "failed"
  else if (actionsDone && status === "running") s4state = "active"

  const s4: RunStep = {
    id: "s4",
    label: "Confirm with HR",
    detail:
      status === "needs_approval"
        ? "Waiting for approval"
        : status === "completed"
          ? "Run finished"
          : undefined,
    state: s4state,
  }

  return [s1, s2, s3, s4]
}

function progressFromSteps(steps: RunStep[]): number {
  const weight = { done: 1, active: 0.5, approval: 0.7, failed: 0.3, pending: 0 }
  const sum = steps.reduce((acc, s) => acc + (weight[s.state] ?? 0), 0)
  return Math.min(100, Math.round((sum / steps.length) * 100))
}

function canvasForStatus(status: WorkStatus, source: string) {
  const label =
    status === "needs_approval"
      ? "Needs approval"
      : status === "running"
        ? "Running"
        : status === "completed"
          ? "Completed"
          : status === "blocked"
            ? "Blocked"
            : "Queued"
  const state =
    status === "blocked"
      ? ("warn" as const)
      : status === "completed"
        ? ("ok" as const)
        : ("pending" as const)
  return {
    kind: "checklist" as const,
    items: [
      { label: "Status", value: label, state },
      { label: "Source", value: source, state: "ok" as const },
    ],
  }
}

function applyItemPatch(
  chatId: string,
  patch: {
    title?: string
    summary?: string
    status: WorkStatus
    activity: WorkActivitySignal[]
    approvalNote?: string
  },
) {
  ensureWorkHydrated()
  const store = useWorkStore.getState()
  let item = findByChat(chatId)
  if (!item) {
    const title = (patch.title || "Agent run").trim().slice(0, 120)
    item = store.createWorkItem({
      title,
      summary:
        patch.summary?.trim() ||
        `Substantial Copilot run. Open chat ${chatId} for the full thread and tool trace.`,
      source: "adhoc",
      category: "Agent run",
      priority: patch.status === "needs_approval" ? "high" : "normal",
      externalRef: chatRef(chatId),
      linkedChatId: chatId,
      subject: { name: "Vera", role: "Copilot", initials: "V" },
      steps: stepsFromActivity(patch.activity, patch.status),
    })
  }

  const steps = stepsFromActivity(patch.activity, patch.status)
  const progress =
    patch.status === "completed" ? 100 : progressFromSteps(steps)

  store.updateWorkItem(item.id, {
    status: patch.status,
    progress,
    steps,
    linkedChatId: chatId,
    updatedAt: new Date().toISOString(),
    updated: "just now",
    canvas: canvasForStatus(patch.status, "Copilot"),
    ...(patch.title ? { title: patch.title.slice(0, 120) } : {}),
    ...(patch.summary ? { summary: patch.summary.slice(0, 500) } : {}),
  })

  if (patch.approvalNote) {
    const latest = store.getItem(item.id)
    const already = latest?.messages.some(
      (m) => m.approval && m.body.includes(patch.approvalNote!),
    )
    if (!already) {
      store.appendMessage(item.id, {
        id: `apr-${Date.now()}`,
        role: "agent",
        time: "now",
        body: `Waiting for your approval: ${patch.approvalNote}`,
        approval: {
          title: patch.approvalNote,
          description: "Approve or decline in the main Copilot chat.",
          target: "Copilot chat",
        },
      })
    }
  }

  // Mirror approvals into Tasks (intake) as a real DB ticket when possible.
  if (patch.status === "needs_approval" && typeof window !== "undefined") {
    const workId = item.id
    void fetch("/api/tasks", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        id: `IN-CHAT-${chatId}`.slice(0, 64),
        subject: patch.title || item.title,
        origin: "agent",
        channel: "chat",
        clusterId: "copilot-approvals",
        topic: "Copilot · needs your action",
        disposition: "assist",
        urgency: "high",
        due: "Now",
        state: "waiting",
        linkedWorkId: workId,
        snippet:
          patch.summary ||
          patch.approvalNote ||
          "Waiting on your approval to continue this Copilot run.",
        suggestion: "Open the linked Copilot chat to approve or decline.",
        requester: { name: "Vera", role: "Copilot", initials: "V" },
      }),
    }).catch(() => {})
  }

  return store.getItem(item.id)
}

/**
 * Promote / refresh the Work Queue item when this turn is doing real work.
 * No-ops for trivial chats unless an item already exists (then status/steps update).
 */
export function syncWorkFromChatActivity(input: {
  chatId: string
  title: string
  summary?: string
  activity: WorkActivitySignal[]
  status: WorkStatus
  awaitingApproval?: boolean
  approvalTitle?: string
  force?: boolean
}) {
  if (typeof window === "undefined" || !input.chatId) return

  const existing = findByChat(input.chatId)
  const promote =
    input.force ||
    shouldPromoteToWorkQueue(input.activity, {
      awaitingApproval: input.awaitingApproval,
    })

  if (!promote && !existing) return
  if (!promote && existing && input.status === "completed") {
    // Trivial follow-up finished — leave existing item alone unless it was already tracked.
  }

  applyItemPatch(input.chatId, {
    title: input.title,
    summary: input.summary,
    status: input.status,
    activity: input.activity,
    approvalNote: input.approvalTitle,
  })
}

/** @deprecated Prefer syncWorkFromChatActivity — kept for intake/ad-hoc creators. */
export function ensureWorkForChat(input: {
  chatId: string
  title: string
  summary?: string
}) {
  if (typeof window === "undefined" || !input.chatId) return
  if (isTrivialChatPrompt(input.title) && isTrivialChatPrompt(input.summary || "")) {
    return findByChat(input.chatId)
  }
  return applyItemPatch(input.chatId, {
    title: input.title,
    summary: input.summary,
    status: "running",
    activity: [],
  })
}

export function setChatWorkStatus(chatId: string, status: WorkStatus) {
  if (typeof window === "undefined" || !chatId) return
  const item = findByChat(chatId)
  if (!item) return
  if (item.status === status) return
  if (item.status === "completed" && status === "running") return
  const store = useWorkStore.getState()
  store.updateWorkItem(item.id, {
    status,
    progress: status === "completed" ? 100 : item.progress,
    linkedChatId: chatId,
    updatedAt: new Date().toISOString(),
    updated: "just now",
    canvas: canvasForStatus(status, "Copilot"),
    steps:
      status === "completed"
        ? item.steps.map((s) =>
            s.state === "pending" || s.state === "active" || s.state === "approval"
              ? { ...s, state: "done" as const }
              : s,
          )
        : item.steps,
  })
}

export function noteChatApproval(chatId: string, title: string) {
  if (typeof window === "undefined" || !chatId) return
  syncWorkFromChatActivity({
    chatId,
    title: findByChat(chatId)?.title || title,
    activity: [],
    status: "needs_approval",
    awaitingApproval: true,
    approvalTitle: title,
    force: true,
  })
}

/** Drop leftover greeting-only queue rows (from older always-on mirroring). */
export function pruneTrivialChatWorkItems() {
  if (typeof window === "undefined") return
  ensureWorkHydrated()
  const store = useWorkStore.getState()
  for (const item of store.items) {
    if (!item.externalRef.startsWith("Chat ·")) continue
    if (item.category !== "Copilot chat" && item.category !== "Agent run") continue
    if (!isTrivialChatPrompt(item.title)) continue
    // No real tool trail in steps
    const didWork = item.steps.some(
      (s) =>
        (s.id === "s2" || s.id === "s3") &&
        (s.state === "done" || s.state === "active" || Boolean(s.detail)),
    )
    if (didWork) continue
    store.confirmComplete(item.id)
  }
}
