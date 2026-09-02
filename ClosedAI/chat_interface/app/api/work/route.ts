import { NextResponse } from "next/server"
import { isCosmosConfigured } from "@/lib/cosmos-server"
import { listWorkItems, upsertWorkItem } from "@/lib/work-repo"
import type { WorkItem } from "@/lib/hr-data"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET() {
  if (!isCosmosConfigured()) {
    return NextResponse.json({ source: "fallback", items: [] }, { status: 200 })
  }
  try {
    const items = await listWorkItems()
    return NextResponse.json({ source: "db", items })
  } catch (err) {
    return NextResponse.json(
      {
        source: "fallback",
        items: [],
        error: err instanceof Error ? err.message : "Failed to load work items",
      },
      { status: 200 },
    )
  }
}

export async function POST(req: Request) {
  if (!isCosmosConfigured()) {
    return NextResponse.json({ error: "Cosmos not configured" }, { status: 503 })
  }
  let body: WorkItem
  try {
    body = (await req.json()) as WorkItem
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }
  if (!body?.id) {
    return NextResponse.json({ error: "id is required" }, { status: 400 })
  }
  try {
    const item = await upsertWorkItem(body)
    return NextResponse.json({ item }, { status: 201 })
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to save work item" },
      { status: 500 },
    )
  }
}
