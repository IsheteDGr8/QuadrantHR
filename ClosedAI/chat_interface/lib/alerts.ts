import "server-only"

import { getContainer, isCosmosConfigured } from "@/lib/cosmos-server"
import { listTickets } from "@/lib/tasks-repo"
import { listWorkItems } from "@/lib/work-repo"
import { redactPii } from "@/lib/pii-redact"

export type AlertKind =
  | "email_important"
  | "birthday"
  | "anniversary"
  | "work_auth"
  | "needs_approval"
  | "urgent_task"

export type HrAlert = {
  id: string
  kind: AlertKind
  severity: "critical" | "high" | "info"
  title: string
  body: string
  href?: string
  /** ISO timestamp when this alert was generated. */
  at: string
}

const EMPLOYEES =
  process.env.COSMOS_CONTAINER || process.env.COSMOS_CONTAINER_NAME || "employees"

function mmdd(d: Date): string {
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

function daysUntilMonthDay(month: number, day: number, from = new Date()): number {
  const year = from.getFullYear()
  let next = new Date(year, month - 1, day)
  const start = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  if (next < start) next = new Date(year + 1, month - 1, day)
  return Math.round((next.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
}

function parseYmd(raw: unknown): { y: number; m: number; d: number } | null {
  if (typeof raw !== "string" || !raw.trim()) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw.trim())
  if (!m) return null
  return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) }
}

function addDaysIso(from: Date, days: number): string {
  const d = new Date(from.getFullYear(), from.getMonth(), from.getDate() + days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

async function loadEmployees(): Promise<Array<Record<string, unknown>>> {
  if (!isCosmosConfigured()) return []
  try {
    const container = await getContainer(EMPLOYEES, "/employeeId")
    const { resources } = await container.items
      .query<Record<string, unknown>>({
        query:
          "SELECT TOP 200 c.id, c.employeeId, c.name, c.jobTitle, c.title, c.dateOfBirth, c.hireDate, c.workAuthorization FROM c",
      })
      .fetchAll()
    return resources
  } catch {
    try {
      const container = await getContainer(EMPLOYEES, "/id")
      const { resources } = await container.items
        .query<Record<string, unknown>>("SELECT TOP 200 * FROM c")
        .fetchAll()
      return resources
    } catch {
      return []
    }
  }
}

function birthdayAlerts(employees: Array<Record<string, unknown>>, now: Date): HrAlert[] {
  const out: HrAlert[] = []
  for (const emp of employees) {
    const dob = parseYmd(emp.dateOfBirth)
    if (!dob) continue
    const days = daysUntilMonthDay(dob.m, dob.d, now)
    if (days > 7) continue
    const name = String(emp.name || "Employee")
    const role = String(emp.jobTitle || emp.title || "Team member")
    const when = days === 0 ? "today" : days === 1 ? "tomorrow" : `in ${days} days`
    out.push({
      id: `bday-${emp.employeeId || emp.id}-${dob.m}-${dob.d}`,
      kind: "birthday",
      severity: days === 0 ? "high" : "info",
      title: days === 0 ? `${name}'s birthday is today` : `${name}'s birthday ${when}`,
      body: redactPii(`${role} · wish them well or schedule a note from HR.`),
      href: "/intake",
      at: now.toISOString(),
    })
  }
  return out
}

function anniversaryAlerts(employees: Array<Record<string, unknown>>, now: Date): HrAlert[] {
  const out: HrAlert[] = []
  for (const emp of employees) {
    const hire = parseYmd(emp.hireDate)
    if (!hire) continue
    const days = daysUntilMonthDay(hire.m, hire.d, now)
    if (days > 3) continue
    const years = now.getFullYear() - hire.y
    if (years < 1) continue
    const name = String(emp.name || "Employee")
    out.push({
      id: `anniv-${emp.employeeId || emp.id}-${years}`,
      kind: "anniversary",
      severity: days === 0 ? "high" : "info",
      title:
        days === 0
          ? `${name} — ${years}-year work anniversary today`
          : `${name} hits ${years} years in ${days} day${days === 1 ? "" : "s"}`,
      body: "Consider a recognition note or manager nudge.",
      href: "/intake",
      at: now.toISOString(),
    })
  }
  return out
}

function workAuthAlerts(employees: Array<Record<string, unknown>>, now: Date): HrAlert[] {
  const out: HrAlert[] = []
  for (const emp of employees) {
    const auth =
      (emp.workAuthorization as Record<string, unknown> | undefined) ||
      (emp.work_authorization as Record<string, unknown> | undefined) ||
      {}
    const exp =
      (typeof auth.expirationDate === "string" && auth.expirationDate) ||
      (typeof auth.expiration_date === "string" && auth.expiration_date) ||
      ""
    if (!exp) continue
    const end = Date.parse(exp)
    if (Number.isNaN(end)) continue
    const days = Math.ceil((end - now.getTime()) / (1000 * 60 * 60 * 24))
    if (days < 0 || days > 60) continue
    const name = String(emp.name || "Employee")
    const visa = String(auth.visaType || auth.visa_type || auth.status || "work permit")
    out.push({
      id: `visa-${emp.employeeId || emp.id}-${exp}`,
      kind: "work_auth",
      severity: days <= 14 ? "critical" : "high",
      title: `${name}'s ${visa} expires in ${days}d`,
      body: redactPii(`Expiration ${exp}. Start renewal packet / counsel outreach.`),
      href: "/intake",
      at: now.toISOString(),
    })
  }
  return out
}

function isEmailTicket(t: {
  origin?: string
  channel?: string
}): boolean {
  return t.origin === "email" || t.channel === "email"
}

async function emailAlerts(now: Date): Promise<HrAlert[]> {
  try {
    const tickets = await listTickets()
    return tickets
      .filter(
        (t) =>
          isEmailTicket(t) &&
          t.state !== "handled" &&
          (t.urgency === "urgent" || t.urgency === "high" || t.disposition === "human"),
      )
      .slice(0, 8)
      .map((t) => ({
        id: `email-${t.id}`,
        kind: "email_important" as const,
        severity: (t.urgency === "urgent" ? "critical" : "high") as HrAlert["severity"],
        title: redactPii(t.subject),
        body: redactPii(
          `From ${t.requester.name} · ${t.snippet || "Needs HR attention."}`,
        ),
        href: "/intake",
        at: now.toISOString(),
      }))
  } catch {
    return []
  }
}

async function workQueueAlerts(now: Date): Promise<HrAlert[]> {
  try {
    const items = await listWorkItems()
    return items
      .filter((w) => w.status === "needs_approval")
      .slice(0, 6)
      .map((w) => ({
        id: `apr-${w.id}`,
        kind: "needs_approval" as const,
        severity: "high" as const,
        title: `Approval waiting — ${redactPii(w.title)}`,
        body: redactPii(w.summary || "Open the work item to approve or decline."),
        href: "/work",
        at: now.toISOString(),
      }))
  } catch {
    return []
  }
}

async function urgentTaskAlerts(now: Date): Promise<HrAlert[]> {
  try {
    const tickets = await listTickets()
    return tickets
      .filter(
        (t) =>
          t.state !== "handled" &&
          t.urgency === "urgent" &&
          !isEmailTicket(t),
      )
      .slice(0, 5)
      .map((t) => ({
        id: `urg-${t.id}`,
        kind: "urgent_task" as const,
        severity: "critical" as const,
        title: redactPii(t.subject),
        body: redactPii(`${t.id} · due ${t.due}`),
        href: "/intake",
        at: now.toISOString(),
      }))
  } catch {
    return []
  }
}

/**
 * Curated demo pulse when live Cosmos windows are empty (common with random
 * hire/DOB seeds). Ids are day-stable so dismissals last until tomorrow.
 */
function demoPulseAlerts(now: Date): HrAlert[] {
  const dayKey = mmdd(now)
  const visaExp = addDaysIso(now, 11)
  return [
    {
      id: `demo-visa-${dayKey}`,
      kind: "work_auth",
      severity: "critical",
      title: `Priya Nair's H-1B expires in 11d`,
      body: `Expiration ${visaExp}. Start renewal packet / counsel outreach.`,
      href: "/intake",
      at: now.toISOString(),
    },
    {
      id: `demo-email-${dayKey}`,
      kind: "email_important",
      severity: "critical",
      title: "URGENT: Benefits enrollment ends Friday",
      body: "From Benefits Ops · Open enrollment reminder — 14 employees still incomplete.",
      href: "/intake",
      at: now.toISOString(),
    },
    {
      id: `demo-urg-${dayKey}`,
      kind: "urgent_task",
      severity: "critical",
      title: "Missing I-9 for start date Monday",
      body: "IN-demo · due Today — complete Section 2 before first day.",
      href: "/intake",
      at: now.toISOString(),
    },
    {
      id: `demo-apr-${dayKey}`,
      kind: "needs_approval",
      severity: "high",
      title: "Approval waiting — Send onboarding packet to new hire",
      body: "Documents ready in Work Queue — approve portal send or email.",
      href: "/work",
      at: now.toISOString(),
    },
    {
      id: `demo-bday-${dayKey}`,
      kind: "birthday",
      severity: "high",
      title: "Marcus Cole's birthday is today",
      body: "Engineering · wish them well or schedule a note from HR.",
      href: "/intake",
      at: now.toISOString(),
    },
    {
      id: `demo-bday2-${dayKey}`,
      kind: "birthday",
      severity: "info",
      title: "Elena Vasquez's birthday in 2 days",
      body: "People Ops · wish them well or schedule a note from HR.",
      href: "/intake",
      at: now.toISOString(),
    },
    {
      id: `demo-anniv-${dayKey}`,
      kind: "anniversary",
      severity: "info",
      title: "Jordan Lee hits 5 years in 1 day",
      body: "Consider a recognition note or manager nudge.",
      href: "/intake",
      at: now.toISOString(),
    },
    {
      id: `demo-email2-${dayKey}`,
      kind: "email_important",
      severity: "high",
      title: "Manager escalation: PTO denial dispute",
      body: "From Alex Rivera · Employee contesting denied leave — needs human review.",
      href: "/intake",
      at: now.toISOString(),
    },
  ]
}

const SEVERITY_RANK: Record<HrAlert["severity"], number> = {
  critical: 0,
  high: 1,
  info: 2,
}

const DEMO_MIN = 6

export async function collectHrAlerts(): Promise<{ alerts: HrAlert[]; generatedAt: string }> {
  const now = new Date()
  const employees = await loadEmployees()
  const batches = await Promise.all([
    Promise.resolve(birthdayAlerts(employees, now)),
    Promise.resolve(anniversaryAlerts(employees, now)),
    Promise.resolve(workAuthAlerts(employees, now)),
    emailAlerts(now),
    workQueueAlerts(now),
    urgentTaskAlerts(now),
  ])
  let alerts = batches
    .flat()
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || a.title.localeCompare(b.title))

  // Keep the pulse useful for demos when live date windows miss.
  if (alerts.length < DEMO_MIN) {
    const seen = new Set(alerts.map((a) => a.kind))
    for (const demo of demoPulseAlerts(now)) {
      if (alerts.length >= DEMO_MIN + 2) break
      // Prefer filling missing kinds first, then top up.
      if (!seen.has(demo.kind) || alerts.length < DEMO_MIN) {
        alerts.push(demo)
        seen.add(demo.kind)
      }
    }
    alerts = alerts.sort(
      (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || a.title.localeCompare(b.title),
    )
  }

  return { alerts, generatedAt: now.toISOString() }
}
