import { NextResponse } from "next/server"
import { isCosmosConfigured } from "@/lib/cosmos-server"
import { handleTicketsForWork } from "@/lib/tasks-repo"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

type Ctx = { params: Promise<{ workId: string }> }

/** Mark intake tickets linked to a work item as handled. */
export async function DELETE(_req: Request, ctx: Ctx) {
  if (!isCosmosConfigured()) {
    return NextResponse.json({ ok: true, updated: 0 })
  }
  const { workId } = await ctx.params
  if (!workId) {
    return NextResponse.json({ error: "workId required" }, { status: 400 })
  }
  try {
    const updated = await handleTicketsForWork(workId)
    return NextResponse.json({ ok: true, updated })
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to update tickets" },
      { status: 500 },
    )
  }
}
