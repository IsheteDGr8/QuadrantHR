import "server-only"

import { getContainer, CONTAINERS } from "@/lib/cosmos-server"
import type { WorkItem } from "@/lib/hr-data"
import { redactPii } from "@/lib/pii-redact"

/**
 * Persisted work item. We partition by `/id` (not `/status`) because status is
 * mutable — partitioning on a changing field would strand documents in old
 * partitions on every status transition.
 */
export type StoredWorkItem = WorkItem & {
  createdAt?: string
  updatedAt?: string
  /** Set when HR confirms a completed item; hidden from the active queue. */
  archived?: boolean
}

const PARTITION_KEY = "/id"

/** Legacy bundled demo ids — never show these as live work. */
const LEGACY_SEED_IDS = new Set([
  "WRK-2019",
  "WRK-2024",
  "WRK-2029",
  "WRK-2033",
  "WRK-2036",
  "WRK-2038",
  "WRK-2041",
])

async function workContainer() {
  return getContainer(CONTAINERS.workItems, PARTITION_KEY)
}

function redactWorkItem(item: StoredWorkItem): StoredWorkItem {
  return {
    ...item,
    // NOTE: never redact `id`, `externalRef`, or `linkedChatId` — those are structural
    // identifiers (e.g. "Chat · chat-1787342643339-xl7h5"). The 13-digit timestamp inside
    // a chat id trips the credit-card detector and would corrupt the link to the real chat.
    title: redactPii(item.title),
    summary: redactPii(item.summary),
    messages: (item.messages || []).map((m) => ({
      ...m,
      body: redactPii(m.body),
      approval: m.approval
        ? {
            ...m.approval,
            title: redactPii(m.approval.title),
            description: redactPii(m.approval.description),
          }
        : m.approval,
    })),
    canvas: item.canvas
      ? {
          ...item.canvas,
          items: (item.canvas.items || []).map((c) => ({
            ...c,
            label: redactPii(c.label),
            value: redactPii(c.value),
          })),
        }
      : item.canvas,
    steps: (item.steps || []).map((s) => ({
      ...s,
      label: redactPii(s.label),
      detail: s.detail != null ? redactPii(s.detail) : s.detail,
    })),
  }
}

/** Archive leftover demo seed docs so they never reappear in the active queue. */
async function archiveLegacySeedItems(): Promise<void> {
  const container = await workContainer()
  await Promise.all(
    [...LEGACY_SEED_IDS].map(async (id) => {
      try {
        const { resource } = await container.item(id, id).read<StoredWorkItem>()
        if (!resource || resource.archived) return
        await container.items.upsert({
          ...resource,
          archived: true,
          status: "completed",
          updatedAt: new Date().toISOString(),
        })
      } catch {
        /* missing — fine */
      }
    }),
  )
}

export async function listWorkItems(): Promise<StoredWorkItem[]> {
  await archiveLegacySeedItems()
  const container = await workContainer()
  const { resources } = await container.items
    .query<StoredWorkItem>(
      "SELECT * FROM c WHERE (NOT IS_DEFINED(c.archived)) OR c.archived = false ORDER BY c._ts DESC",
    )
    .fetchAll()
  return resources
    .filter((item) => !LEGACY_SEED_IDS.has(item.id))
    .map(redactWorkItem)
}

export async function getWorkItem(id: string): Promise<StoredWorkItem | null> {
  if (LEGACY_SEED_IDS.has(id)) return null
  const container = await workContainer()
  try {
    const { resource } = await container.item(id, id).read<StoredWorkItem>()
    if (!resource || resource.archived) return null
    return redactWorkItem(resource)
  } catch {
    return null
  }
}

/** Full-document upsert. Callers pass the complete, already-computed item. */
export async function upsertWorkItem(item: WorkItem): Promise<StoredWorkItem> {
  const container = await workContainer()
  const existingRaw = await container.item(item.id, item.id).read<StoredWorkItem>().catch(() => null)
  const existing = existingRaw?.resource ?? null
  const now = new Date().toISOString()
  // Use the field-aware redactor (not redactPiiDeep) so structural identifiers
  // — id / externalRef / linkedChatId — are preserved and never PII-mangled.
  const safe = redactWorkItem(item as StoredWorkItem)
  const doc: StoredWorkItem = {
    ...safe,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
    archived: (item as StoredWorkItem).archived ?? existing?.archived ?? false,
  }
  const { resource } = await container.items.upsert(doc)
  return redactWorkItem((resource as StoredWorkItem) ?? doc)
}

/** Confirm-complete: archive so it drops off the active queue but is retained. */
export async function archiveWorkItem(id: string): Promise<boolean> {
  const container = await workContainer()
  let existing: StoredWorkItem | null = null
  try {
    const { resource } = await container.item(id, id).read<StoredWorkItem>()
    existing = resource ?? null
  } catch {
    return false
  }
  if (!existing) return false
  await container.items.upsert({
    ...existing,
    archived: true,
    status: "completed",
    updatedAt: new Date().toISOString(),
  })
  return true
}
