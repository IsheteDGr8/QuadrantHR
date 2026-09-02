import "server-only"

import { getContainer } from "@/lib/cosmos-server"
import { createTicket, listTickets, type TicketDoc } from "@/lib/tasks-repo"

const EMPLOYEES_CONTAINER = process.env.COSMOS_CONTAINER || process.env.COSMOS_CONTAINER_NAME || "employees"

function daysUntil(isoDate: string): number | null {
  const d = Date.parse(isoDate)
  if (Number.isNaN(d)) return null
  return Math.ceil((d - Date.now()) / (1000 * 60 * 60 * 24))
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return "??"
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase()
  return `${parts[0]![0] ?? ""}${parts[parts.length - 1]![0] ?? ""}`.toUpperCase()
}

/** Create intake tickets for employees whose work authorization expires soon. */
export async function ingestSystemEvents(withinDays = 90): Promise<TicketDoc[]> {
  const existing = await listTickets()
  const existingKeys = new Set(
    existing
      .filter((t) => t.origin === "system")
      .map((t) => `${t.requester.name}|${t.subject}`.toLowerCase()),
  )

  const container = await getContainer(EMPLOYEES_CONTAINER, "/employeeId")
  let docs: Array<Record<string, unknown>> = []
  try {
    const { resources } = await container.items
      .query<Record<string, unknown>>({
        query:
          "SELECT TOP 40 c.id, c.employeeId, c.name, c.jobTitle, c.title, c.workEmail, c.workAuthorization FROM c",
      })
      .fetchAll()
    docs = resources
  } catch {
    // Employees may partition differently; fall back to a small scan.
    try {
      const { resources } = await container.items
        .query<Record<string, unknown>>("SELECT TOP 40 * FROM c")
        .fetchAll()
      docs = resources
    } catch {
      docs = []
    }
  }

  const created: TicketDoc[] = []
  for (const doc of docs) {
    const auth =
      (doc.workAuthorization as Record<string, unknown> | undefined) ||
      (doc.work_authorization as Record<string, unknown> | undefined) ||
      {}
    const exp =
      (typeof auth.expirationDate === "string" && auth.expirationDate) ||
      (typeof auth.expiration_date === "string" && auth.expiration_date) ||
      (typeof doc.visaExpiration === "string" && doc.visaExpiration) ||
      ""
    if (!exp) continue
    const days = daysUntil(exp)
    if (days === null || days < 0 || days > withinDays) continue

    const name = String(doc.name || "Employee")
    const role = String(doc.jobTitle || doc.title || "Employee")
    const visa = String(
      auth.visaType || auth.visa_type || auth.status || doc.visaType || "work permit",
    )
    const subject = `Work authorization renewal — ${visa} expires in ${days}d`
    const key = `${name}|${subject}`.toLowerCase()
    if (existingKeys.has(key)) continue

    const ticket = await createTicket({
      subject,
      requester: { name, role, initials: initials(name) },
      channel: "system",
      clusterId: "relocation-visa",
      topic: `Work authorisation · ${visa}`,
      urgency: days <= 30 ? "urgent" : "high",
      due: days <= 14 ? "Today" : days <= 30 ? "This week" : "This month",
      disposition: "human",
      snippet: `${name}'s ${visa} expires on ${exp}. Immigration counsel typically needs an HR letter and recent payslips.`,
      suggestion: "Assemble renewal packet and decide filing route.",
      origin: "system",
    })
    created.push(ticket)
    existingKeys.add(key)
  }
  return created
}

/**
 * Create email-origin intake tickets from real messages only.
 * Does not invent demo inbox rows.
 */
export async function ingestEmailTasks(
  messages?: Array<{
    subject: string
    fromName?: string
    fromRole?: string
    snippet?: string
    urgency?: "urgent" | "high" | "normal" | "low"
  }>,
  _opts?: { force?: boolean },
): Promise<TicketDoc[]> {
  if (!messages || messages.length === 0) return []

  const existing = await listTickets()
  const created: TicketDoc[] = []
  const seenSubjects = new Set(
    existing
      .filter((t) => t.origin === "email")
      .map((t) => t.subject.trim().toLowerCase()),
  )
  for (const msg of messages) {
    const subjectKey = msg.subject.trim().toLowerCase()
    if (seenSubjects.has(subjectKey)) continue
    const name = msg.fromName || "Unknown sender"
    const ticket = await createTicket({
      subject: msg.subject,
      requester: {
        name,
        role: msg.fromRole || "Email",
        initials: initials(name),
      },
      channel: "email",
      clusterId: "uncategorised",
      topic: "Email · needs triage",
      urgency: msg.urgency || "normal",
      due: "This week",
      disposition: "assist",
      snippet: msg.snippet || "",
      suggestion: "Triage and draft a reply or route to the matching playbook.",
      origin: "email",
    })
    created.push(ticket)
    seenSubjects.add(subjectKey)
  }
  return created
}
