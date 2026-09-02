import { NextResponse } from "next/server"
import { isCosmosConfigured } from "@/lib/cosmos-server"
import { createTicket } from "@/lib/tasks-repo"
import { DEMO_INTAKE_TICKETS } from "@/lib/demo-intake-tickets"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

/**
 * Upsert presentation sample tickets into Cosmos so Tasks "By decision"
 * shows content in all three lanes (auto / assist / human).
 */
export async function POST() {
  if (!isCosmosConfigured()) {
    return NextResponse.json({ error: "Cosmos not configured" }, { status: 503 })
  }
  try {
    const created = []
    for (const ticket of DEMO_INTAKE_TICKETS) {
      created.push(await createTicket(ticket))
    }
    return NextResponse.json({
      ok: true,
      count: created.length,
      byDisposition: {
        auto: created.filter((t) => t.disposition === "auto").length,
        assist: created.filter((t) => t.disposition === "assist").length,
        human: created.filter((t) => t.disposition === "human").length,
      },
    })
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Seed failed" },
      { status: 500 },
    )
  }
}
