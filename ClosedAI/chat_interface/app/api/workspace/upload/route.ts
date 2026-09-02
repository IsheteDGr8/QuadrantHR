import { NextRequest, NextResponse } from "next/server"
import path from "node:path"
import fs from "node:fs"

const REPO_ROOT = path.resolve(process.cwd(), "..")
const WORKSPACE_DIR = path.join(REPO_ROOT, "HRAgent_Main", "workspace")

const ALLOWED_EXTENSIONS = new Set([
  ".pdf",
  ".docx",
  ".xlsx",
  ".pptx",
  ".txt",
  ".md",
  ".png",
  ".jpg",
  ".jpeg",
])

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const file = formData.get("file")
  const subdirRaw = (formData.get("subdir") as string | null) || "uploads"
  const subdir = subdirRaw.replace(/[^a-zA-Z0-9_\-/]/g, "").replace(/^\/+/, "")

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Missing file" }, { status: 400 })
  }

  const safeName = path.basename(file.name)
  const ext = path.extname(safeName).toLowerCase()
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return NextResponse.json({ error: `Unsupported file type: ${ext}` }, { status: 400 })
  }

  const destDir = path.resolve(WORKSPACE_DIR, subdir)
  if (!destDir.startsWith(WORKSPACE_DIR)) {
    return NextResponse.json({ error: "Invalid upload directory" }, { status: 400 })
  }

  fs.mkdirSync(destDir, { recursive: true })
  const destPath = path.join(destDir, safeName)
  const buffer = Buffer.from(await file.arrayBuffer())
  fs.writeFileSync(destPath, buffer)

  const relativePath = path.join(subdir, safeName).replace(/\\/g, "/")
  return NextResponse.json({
    path: relativePath,
    filename: safeName,
    size: buffer.length,
  })
}
