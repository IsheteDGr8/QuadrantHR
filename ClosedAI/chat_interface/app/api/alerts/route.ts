import { NextResponse } from "next/server"
import { collectHrAlerts } from "@/lib/alerts"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET() {
  try {
    const data = await collectHrAlerts()
    return NextResponse.json(data)
  } catch (err) {
    return NextResponse.json(
      {
        alerts: [],
        generatedAt: new Date().toISOString(),
        error: err instanceof Error ? err.message : "Failed to load alerts",
      },
      { status: 200 },
    )
  }
}
