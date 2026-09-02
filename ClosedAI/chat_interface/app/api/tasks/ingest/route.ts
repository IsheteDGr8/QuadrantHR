import { NextResponse } from "next/server"
import { isCosmosConfigured } from "@/lib/cosmos-server"
import { ingestEmailTasks, ingestSystemEvents } from "@/lib/intake-ingest"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

/**
 * Pull new Tasks from connected sources.
 * Body: { sources?: ("system" | "email")[], emails?: [...] }
 */
export async function POST(req: Request) {
  if (!isCosmosConfigured()) {
    return NextResponse.json({ error: "Cosmos not configured" }, { status: 503 })
  }

  let body: {
    sources?: Array<"system" | "email">
    force?: boolean
    emails?: Array<{
      subject: string
      fromName?: string
      fromRole?: string
      snippet?: string
      urgency?: "urgent" | "high" | "normal" | "low"
    }>
  } = {}
  try {
    body = (await req.json()) as typeof body
  } catch {
    body = {}
  }

  const sources = body.sources?.length ? body.sources : (["system", "email"] as const)
  const created: unknown[] = []
  const errors: string[] = []

  if (sources.includes("system")) {
    try {
      created.push(...(await ingestSystemEvents()))
    } catch (err) {
      errors.push(err instanceof Error ? err.message : "system ingest failed")
    }
  }
  if (sources.includes("email")) {
    try {
      created.push(...(await ingestEmailTasks(body.emails, { force: Boolean(body.force) })))
    } catch (err) {
      errors.push(err instanceof Error ? err.message : "email ingest failed")
    }
  }

  return NextResponse.json({
    created: created.length,
    tickets: created,
    errors: errors.length ? errors : undefined,
  })
}
