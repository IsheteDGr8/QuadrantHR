import { NextResponse } from "next/server"
import { isCosmosConfigured } from "@/lib/cosmos-server"
import {
  listTickets,
  createTicket,
  computeStats,
  type CreateTicketInput,
} from "@/lib/tasks-repo"

// Cosmos calls can create containers on first hit — keep this on the Node runtime
// and never cache.
export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET() {
  if (!isCosmosConfigured()) {
    return NextResponse.json(
      { source: "fallback", error: "Cosmos not configured", tickets: [], stats: null },
      { status: 200 },
    )
  }
  try {
    const tickets = await listTickets()
    return NextResponse.json({ source: "db", tickets, stats: computeStats(tickets) })
  } catch (err) {
    return NextResponse.json(
      {
        source: "fallback",
        error: err instanceof Error ? err.message : "Failed to load tickets",
        tickets: [],
        stats: null,
      },
      { status: 200 },
    )
  }
}

export async function POST(req: Request) {
  if (!isCosmosConfigured()) {
    return NextResponse.json({ error: "Cosmos not configured" }, { status: 503 })
  }
  let body: CreateTicketInput
  try {
    body = (await req.json()) as CreateTicketInput
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }
  if (!body?.subject?.trim()) {
    return NextResponse.json({ error: "subject is required" }, { status: 400 })
  }
  try {
    const ticket = await createTicket(body)
    return NextResponse.json({ ticket }, { status: 201 })
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to create ticket" },
      { status: 500 },
    )
  }
}
