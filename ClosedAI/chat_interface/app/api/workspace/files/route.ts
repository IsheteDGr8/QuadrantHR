import { NextRequest, NextResponse } from "next/server"
import path from "node:path"
import fs from "node:fs"

// Base directory for agent workspace files
const REPO_ROOT = path.resolve(process.cwd(), "..")
const WORKSPACE_DIR = path.join(REPO_ROOT, "HRAgent_Main", "workspace")

const MIME_TYPES: Record<string, string> = {
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".txt": "text/plain; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
}

const HRAGENT_MAIN = path.join(REPO_ROOT, "HRAgent_Main")

function resolveExistingFile(cleanPath: string): string | null {
  const basename = path.basename(cleanPath)
  const candidates = [
    path.resolve(WORKSPACE_DIR, cleanPath),
    path.resolve(WORKSPACE_DIR, "outputs", basename),
    path.resolve(WORKSPACE_DIR, basename),
    path.resolve(HRAGENT_MAIN, cleanPath),
    path.resolve(HRAGENT_MAIN, basename),
  ]

  for (const candidate of candidates) {
    const withinWorkspace = candidate.startsWith(WORKSPACE_DIR)
    const withinRepo = candidate.startsWith(REPO_ROOT)
    if (!withinWorkspace && !withinRepo) continue
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return candidate
    }
  }
  return null
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const rawPath = searchParams.get("path")
  const download = searchParams.get("download") === "1"

  if (!rawPath) {
    return NextResponse.json({ error: "Missing path parameter" }, { status: 400 })
  }

  // Sanitize path (remove trailing punctuation that might have been caught by loose UI regexes)
  let cleanPath = rawPath.replace(/[.,!?'"]+$/, "").trim()
  
  // If the path contains 'workspace' (e.g. from a truncated regex match), anchor to it
  const workspaceMatch = cleanPath.match(/workspace[\\/](.+)$/i)
  if (workspaceMatch) {
    cleanPath = workspaceMatch[1]
  }

  // Normalize path and resolve against workspace directory
  const resolvedPath = resolveExistingFile(cleanPath)

  if (!resolvedPath) {
    return NextResponse.json({ error: "File not found" }, { status: 404 })
  }

  const stat = fs.statSync(resolvedPath)
  if (!stat.isFile()) {
    return NextResponse.json({ error: "Target is not a file" }, { status: 400 })
  }
  const filename = path.basename(resolvedPath)
  const ext = path.extname(resolvedPath).toLowerCase()
  const contentType = MIME_TYPES[ext] || "application/octet-stream"

  const fileStream = fs.readFileSync(resolvedPath)

  // Prefer attachment only when explicitly downloading; inline for preview/PDF iframe.
  const disposition = download ? "attachment" : "inline"
  const safeAscii = filename.replace(/[^\x20-\x7E]/g, "_").replace(/"/g, "")
  const encoded = encodeURIComponent(filename)

  const headers = new Headers()
  headers.set("Content-Type", contentType)
  headers.set("Content-Length", String(stat.size))
  headers.set(
    "Content-Disposition",
    `${disposition}; filename="${safeAscii}"; filename*=UTF-8''${encoded}`,
  )
  if (!download) {
    headers.set("Cache-Control", "private, max-age=60")
  }

  return new NextResponse(fileStream, {
    status: 200,
    headers,
  })
}
