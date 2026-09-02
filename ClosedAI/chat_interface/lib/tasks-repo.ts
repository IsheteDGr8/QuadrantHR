import "server-only"

import { getContainer, CONTAINERS } from "@/lib/cosmos-server"
import type { IntakeItem } from "@/lib/intake-data"
import { redactPii } from "@/lib/pii-redact"

/**
 * A stored intake ticket. Superset of the UI `IntakeItem` plus provenance so we
 * can tell helpdesk/email/system/agent items apart and order by time.
 */
export type TicketOrigin = "seed" | "helpdesk" | "email" | "system" | "agent" | "manual"

export interface TicketDoc extends IntakeItem {
  origin: TicketOrigin
  createdAt: string
  updatedAt: string
  /** Soft-delete / hide from active Tasks. */
  archived?: boolean
  /** Cosmos timestamp; used to keep the newest copy when state-partition dupes exist. */
  _ts?: number
}

const PARTITION_KEY = "/state"

/** Legacy bundled demo ticket ids — never show as live intake. */
const LEGACY_SEED_IDS = new Set([
  "IN-8827",
  "IN-8828",
  "IN-8829",
  "IN-8830",
  "IN-8831",
  "IN-8832",
  "IN-8833",
  "IN-8834",
  "IN-8835",
  "IN-8836",
  "IN-8837",
  "IN-8838",
  "IN-8839",
  "IN-8840",
  "IN-8841",
])

async function ticketsContainer() {
  return getContainer(CONTAINERS.intakeTickets, PARTITION_KEY)
}

function ticketRecency(doc: TicketDoc): number {
  if (typeof doc._ts === "number" && doc._ts > 0) return doc._ts
  const parsed = Date.parse(doc.updatedAt || doc.createdAt || "")
  return Number.isFinite(parsed) ? parsed : 0
}

/**
 * Partition key is `/state`, so upserts that change `state` used to leave a
 * ghost document in the old partition with the same id. Collapse those.
 */
function pickCanonicalTicket(copies: TicketDoc[]): TicketDoc {
  return [...copies].sort((a, b) => {
    if (!!a.archived !== !!b.archived) return a.archived ? 1 : -1
    return ticketRecency(b) - ticketRecency(a)
  })[0]
}

async function deleteTicketPartition(id: string, state: IntakeItem["state"]): Promise<void> {
  const container = await ticketsContainer()
  try {
    await container.item(id, state).delete()
  } catch {
    /* already gone */
  }
}

async function upsertTicketDoc(doc: TicketDoc, previousState?: IntakeItem["state"]): Promise<TicketDoc> {
  const container = await ticketsContainer()
  const { resource } = await container.items.upsert(doc)
  if (previousState && previousState !== doc.state) {
    await deleteTicketPartition(doc.id, previousState)
  }
  return redactTicket((resource as TicketDoc) ?? doc)
}

/** Drop extra copies of the same id (cross-partition ghosts) and delete them. */
export function dedupeTicketsById(docs: TicketDoc[]): TicketDoc[] {
  const groups = new Map<string, TicketDoc[]>()
  for (const doc of docs) {
    const list = groups.get(doc.id)
    if (list) list.push(doc)
    else groups.set(doc.id, [doc])
  }
  const out: TicketDoc[] = []
  for (const copies of groups.values()) {
    out.push(pickCanonicalTicket(copies))
  }
  return out
}

async function collapseDuplicateTicketPartitions(docs: TicketDoc[]): Promise<TicketDoc[]> {
  const groups = new Map<string, TicketDoc[]>()
  for (const doc of docs) {
    const list = groups.get(doc.id)
    if (list) list.push(doc)
    else groups.set(doc.id, [doc])
  }
  const kept: TicketDoc[] = []
  for (const copies of groups.values()) {
    const winner = pickCanonicalTicket(copies)
    kept.push(winner)
    if (copies.length < 2) continue
    await Promise.all(
      copies
        .filter((copy) => copy.state !== winner.state || copy.archived !== winner.archived)
        .map((copy) => deleteTicketPartition(copy.id, copy.state)),
    )
  }
  return kept
}

function redactTicket(doc: TicketDoc): TicketDoc {
  return {
    ...doc,
    subject: redactPii(doc.subject),
    topic: redactPii(doc.topic),
    snippet: redactPii(doc.snippet),
    suggestion: redactPii(doc.suggestion),
  }
}

function isLiveTicket(doc: TicketDoc): boolean {
  if (doc.archived) return false
  if (doc.origin === "seed") return false
  if (LEGACY_SEED_IDS.has(doc.id)) return false
  return true
}

/** Archive leftover demo seed docs so they never reappear. */
async function archiveLegacySeedTickets(): Promise<void> {
  const container = await ticketsContainer()
  const { resources } = await container.items
    .query<TicketDoc>("SELECT * FROM c WHERE c.origin = 'seed' OR STARTSWITH(c.id, 'IN-88')")
    .fetchAll()
    .catch(() => ({ resources: [] as TicketDoc[] }))

  await Promise.all(
    resources.map(async (doc) => {
      if (!LEGACY_SEED_IDS.has(doc.id) && doc.origin !== "seed") return
      if (doc.archived) return
      try {
        await upsertTicketDoc(
          {
            ...doc,
            archived: true,
            state: "handled",
            updatedAt: new Date().toISOString(),
          },
          doc.state,
        )
      } catch {
        /* ignore */
      }
    }),
  )
}

async function listTicketsRaw(): Promise<TicketDoc[]> {
  const container = await ticketsContainer()
  const { resources } = await container.items
    .query<TicketDoc>("SELECT * FROM c ORDER BY c._ts DESC")
    .fetchAll()
  return resources.map(redactTicket)
}

/** Active, non-demo intake tickets from Cosmos. */
export async function listTickets(): Promise<TicketDoc[]> {
  await archiveLegacySeedTickets()
  const all = await listTicketsRaw()
  const unique = await collapseDuplicateTicketPartitions(all)
  return unique.filter(isLiveTicket)
}

function nextTicketId(existing: TicketDoc[]): string {
  let max = 9000
  for (const t of existing) {
    const m = /^IN-(\d+)$/i.exec(t.id)
    if (m) max = Math.max(max, Number(m[1]))
  }
  return `IN-${max + 1}`
}

export interface CreateTicketInput {
  subject: string
  requester?: IntakeItem["requester"]
  channel?: IntakeItem["channel"]
  clusterId?: string
  topic?: string
  urgency?: IntakeItem["urgency"]
  due?: string
  disposition?: IntakeItem["disposition"]
  snippet?: string
  suggestion?: string
  origin?: TicketOrigin
  linkedWorkId?: string
  /** Stable id for upserts (e.g. chat approval tickets). */
  id?: string
  state?: IntakeItem["state"]
}

export async function createTicket(input: CreateTicketInput): Promise<TicketDoc> {
  const raw = await listTicketsRaw()
  const now = new Date().toISOString()

  // Idempotent upsert when linkedWorkId or explicit id is provided.
  if (input.linkedWorkId) {
    const existing = raw.find(
      (t) =>
        t.linkedWorkId === input.linkedWorkId &&
        !t.archived &&
        t.state !== "handled",
    )
    if (existing) {
      const patched: TicketDoc = {
        ...existing,
        subject: redactPii(input.subject.trim() || existing.subject),
        snippet: redactPii(input.snippet ?? existing.snippet),
        suggestion: redactPii(input.suggestion ?? existing.suggestion),
        urgency: input.urgency ?? existing.urgency,
        disposition: input.disposition ?? existing.disposition,
        state: input.state ?? existing.state,
        updatedAt: now,
        age: "just now",
        ageMinutes: 0,
      }
      return upsertTicketDoc(patched, existing.state)
    }
  }
  if (input.id) {
    const existing = raw.find((t) => t.id === input.id)
    if (existing && !existing.archived) {
      const patched: TicketDoc = {
        ...existing,
        subject: redactPii(input.subject.trim() || existing.subject),
        snippet: redactPii(input.snippet ?? existing.snippet),
        suggestion: redactPii(input.suggestion ?? existing.suggestion),
        linkedWorkId: input.linkedWorkId ?? existing.linkedWorkId,
        disposition: input.disposition ?? existing.disposition,
        state: input.state ?? existing.state,
        urgency: input.urgency ?? existing.urgency,
        updatedAt: now,
      }
      return upsertTicketDoc(patched, existing.state)
    }
  }

  const doc: TicketDoc = {
    id: input.id || nextTicketId(raw),
    subject: redactPii(input.subject.trim() || "Untitled request"),
    requester: input.requester ?? { name: "HR team", role: "Requester", initials: "HR" },
    channel: input.channel ?? "email",
    clusterId: input.clusterId ?? "uncategorised",
    topic: redactPii(input.topic ?? "New intake"),
    urgency: input.urgency ?? "normal",
    age: "just now",
    ageMinutes: 0,
    due: input.due ?? "This week",
    state: input.state ?? "new",
    disposition: input.disposition ?? "human",
    confidence: input.origin === "agent" ? 85 : 0,
    snippet: redactPii(input.snippet ?? ""),
    suggestion: redactPii(input.suggestion ?? ""),
    linkedWorkId: input.linkedWorkId,
    origin: input.origin === "seed" ? "manual" : (input.origin ?? "manual"),
    createdAt: now,
    updatedAt: now,
  }
  return upsertTicketDoc(doc)
}

/** Mark intake tickets linked to a work item as handled (e.g. after confirm-complete). */
export async function handleTicketsForWork(workId: string): Promise<number> {
  const raw = await listTicketsRaw()
  const targets = raw.filter((t) => t.linkedWorkId === workId && t.state !== "handled")
  await Promise.all(
    targets.map((t) =>
      upsertTicketDoc(
        {
          ...t,
          state: "handled",
          updatedAt: new Date().toISOString(),
        },
        t.state,
      ),
    ),
  )
  return targets.length
}

export function computeStats(items: TicketDoc[]) {
  const open = items.filter((i) => i.state !== "handled")
  return {
    open: open.length,
    needsJudgement: open.filter((i) => i.disposition === "human").length,
    readyToRelease: items.filter((i) => i.disposition === "auto" && i.state === "new").length,
    arrivedToday: open.length,
    autoAbsorbed: items.filter((i) => i.disposition === "auto").length,
  }
}
