import { NextResponse } from "next/server"
import { isCosmosConfigured } from "@/lib/cosmos-server"
import { getWorkItem, upsertWorkItem, archiveWorkItem } from "@/lib/work-repo"
import type { WorkItem } from "@/lib/hr-data"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

type Ctx = { params: Promise<{ id: string }> }

export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params
  if (!isCosmosConfigured()) {
    return NextResponse.json({ error: "Cosmos not configured" }, { status: 503 })
  }
  const item = await getWorkItem(id)
  if (!item) return NextResponse.json({ error: "Not found" }, { status: 404 })
  return NextResponse.json({ item })
}

/** Full-document replace (the client store computes the new state and sends it). */
export async function PUT(req: Request, { params }: Ctx) {
  const { id } = await params
  if (!isCosmosConfigured()) {
    return NextResponse.json({ error: "Cosmos not configured" }, { status: 503 })
  }
  let body: WorkItem
  try {
    body = (await req.json()) as WorkItem
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }
  try {
    const item = await upsertWorkItem({ ...body, id })
    return NextResponse.json({ item })
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to save work item" },
      { status: 500 },
    )
  }
}

/** Confirm-complete & remove from the active queue (archives, keeps the record). */
export async function DELETE(_req: Request, { params }: Ctx) {
  const { id } = await params
  if (!isCosmosConfigured()) {
    return NextResponse.json({ error: "Cosmos not configured" }, { status: 503 })
  }
  const ok = await archiveWorkItem(id)
  if (!ok) return NextResponse.json({ error: "Not found" }, { status: 404 })
  return NextResponse.json({ ok: true })
}
