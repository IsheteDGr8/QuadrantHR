import { NextRequest, NextResponse } from "next/server"
import fs from "node:fs"
import path from "node:path"
import crypto from "node:crypto"

export const runtime = "nodejs"

type SharedMessage = {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  createdAt?: number
  timestamp?: number
  status?: string
  metadata?: Record<string, unknown>
}

type SharePayload = {
  shareId: string
  title: string
  sourceChatId?: string
  messages: SharedMessage[]
  createdAt: string
}

const SHARE_DIR = path.join(process.cwd(), ".next", "cache", "shared-chats")

function ensureDir() {
  try {
    fs.mkdirSync(SHARE_DIR, { recursive: true })
  } catch {
    /* ignore */
  }
}

function sharePath(id: string) {
  const safe = id.replace(/[^a-zA-Z0-9_-]/g, "")
  return path.join(SHARE_DIR, `${safe}.json`)
}

/** Create a shareable snapshot of a chat. */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const title = typeof body?.title === "string" && body.title.trim() ? body.title.trim() : "Shared chat"
    const sourceChatId = typeof body?.sourceChatId === "string" ? body.sourceChatId : undefined
    const messages = Array.isArray(body?.messages) ? body.messages : []

    if (messages.length === 0) {
      return NextResponse.json({ error: "Nothing to share yet" }, { status: 400 })
    }

    const shareId = crypto.randomBytes(8).toString("hex")
    const payload: SharePayload = {
      shareId,
      title,
      sourceChatId,
      messages: messages.map((m: SharedMessage) => ({
        id: String(m.id || crypto.randomUUID()),
        role: m.role === "user" || m.role === "system" ? m.role : "assistant",
        content: typeof m.content === "string" ? m.content : "",
        createdAt: typeof m.createdAt === "number" ? m.createdAt : Date.now(),
        timestamp: typeof m.timestamp === "number" ? m.timestamp : Date.now(),
        status: typeof m.status === "string" ? m.status : "received",
        metadata: m.metadata && typeof m.metadata === "object" ? m.metadata : undefined,
      })),
      createdAt: new Date().toISOString(),
    }

    ensureDir()
    fs.writeFileSync(sharePath(shareId), JSON.stringify(payload), "utf8")
    return NextResponse.json({ shareId, title: payload.title })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create share" },
      { status: 500 },
    )
  }
}

/** Load a shared chat snapshot. */
export async function GET(request: NextRequest) {
  const shareId = request.nextUrl.searchParams.get("id")?.trim()
  if (!shareId) {
    return NextResponse.json({ error: "id is required" }, { status: 400 })
  }
  const safe = shareId.replace(/[^a-zA-Z0-9_-]/g, "")
  if (!safe) {
    return NextResponse.json({ error: "Invalid id" }, { status: 400 })
  }

  try {
    const file = sharePath(safe)
    if (!fs.existsSync(file)) {
      return NextResponse.json({ error: "Shared chat not found" }, { status: 404 })
    }
    const payload = JSON.parse(fs.readFileSync(file, "utf8")) as SharePayload
    return NextResponse.json(payload)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load share" },
      { status: 500 },
    )
  }
}
