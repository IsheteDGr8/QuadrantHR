/** Helpers for workspace document chips, preview, and downloads. */

const FILE_EXT =
  "pdf|docx|xlsx|pptx|txt|json|csv|md|png|jpe?g|webp"

/** Match filenames/paths even after punctuation (em-dash, colon, etc.). */
const FILE_EXT_RE = new RegExp(
  `(?:^|[^a-zA-Z0-9_])((?:outputs|uploads)[/\\\\])?([a-zA-Z0-9_\\-.]+?\\.(?:${FILE_EXT}))\\b`,
  "gi",
)

const TEXT_PREVIEW_EXTS = new Set([".md", ".txt", ".csv", ".json"])

/** Tools that create downloadable workspace files. */
export const FILE_PRODUCING_TOOLS = new Set([
  "write_workspace_file",
  "office_fill_pdf_form",
  "office_fill_docx_form",
  "office_template_fill",
  "office_overlay_pdf_text",
])

export function fileBasename(filePath: string): string {
  return filePath.split(/[\\/]/).pop() || filePath
}

export function fileExt(filePath: string): string {
  const base = fileBasename(filePath)
  const i = base.lastIndexOf(".")
  return i >= 0 ? base.slice(i).toLowerCase() : ""
}

/** Prefer workspace-relative path; never expose absolute disk paths to the UI. */
export function normalizeWorkspacePath(raw: string): string | null {
  let clean = raw.trim().replace(/^[`'"]+|[`'"]+$/g, "").replace(/\\/g, "/")
  clean = clean.replace(/[.,!?;:'"]+$/g, "")
  if (!clean || clean.includes("://")) return null

  // Drop absolute / drive-letter / workspace prefix noise
  const workspaceIdx = clean.toLowerCase().lastIndexOf("/workspace/")
  if (workspaceIdx >= 0) clean = clean.slice(workspaceIdx + "/workspace/".length)
  clean = clean.replace(/^\/+/, "")
  if (/^[a-z]:\//i.test(clean)) {
    clean = fileBasename(clean)
  }

  const base = fileBasename(clean)
  if (!/\.(pdf|docx|xlsx|pptx|txt|csv|md|png|jpe?g|webp)$/i.test(base)) return null
  if (/\.json$/i.test(base)) return null

  // Keep outputs/uploads prefix when present; otherwise bare basename is fine
  // (the files API resolves by basename under outputs/).
  if (clean.startsWith("outputs/") || clean.startsWith("uploads/")) return clean
  if (clean.includes("/")) {
    // Other relative paths under workspace — keep if shallow
    const parts = clean.split("/").filter(Boolean)
    if (parts.length <= 3 && !parts.some((p) => p === ".." || p === ".")) return clean
    return base
  }
  return base
}

/** Human title for chips — never show outputs/ or uploads/. */
export function friendlyFileTitle(filePath: string): string {
  const base = fileBasename(filePath)
  const withoutExt = base.replace(/\.[^.]+$/, "")
  const spaced = withoutExt.replace(/[_-]+/g, " ").trim()
  if (!spaced) return base
  return spaced.replace(/\b\w/g, (c) => c.toUpperCase())
}

export function workspaceFileUrl(filePath: string, opts?: { download?: boolean }): string {
  const q = new URLSearchParams({ path: filePath })
  if (opts?.download) q.set("download", "1")
  else q.set("preview", "1")
  return `/api/workspace/files?${q.toString()}`
}

export function isTextPreviewable(filePath: string): boolean {
  return TEXT_PREVIEW_EXTS.has(fileExt(filePath))
}

export function isPdf(filePath: string): boolean {
  return fileExt(filePath) === ".pdf"
}

/** Collect unique workspace-relative paths mentioned in assistant text + metadata. */
export function extractFileRefs(content: string, extra?: string[]): string[] {
  const found = new Set<string>()
  for (const p of extra || []) {
    const n = normalizeWorkspacePath(p)
    if (n) found.add(n)
  }

  FILE_EXT_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = FILE_EXT_RE.exec(content)) !== null) {
    const prefix = m[1] || ""
    const name = m[2]
    if (!name) continue
    const n = normalizeWorkspacePath(prefix ? `${prefix}${name}` : name)
    if (n) found.add(n)
  }

  return uniqueFilePaths(Array.from(found))
}

/** Collapse paths that only differ by folder prefix (outputs/foo.md vs foo.md). */
export function uniqueFilePaths(paths: string[]): string[] {
  const byBase = new Map<string, string>()
  for (const raw of paths) {
    const n = normalizeWorkspacePath(raw) || raw.trim()
    if (!n) continue
    const base = fileBasename(n).toLowerCase()
    const prev = byBase.get(base)
    if (!prev || (n.includes("/") && !prev.includes("/"))) {
      byBase.set(base, n)
    }
  }
  return Array.from(byBase.values())
}

/** Pull file paths from a tool call's arguments. */
export function extractPathsFromToolParams(params: Record<string, unknown> | null | undefined): string[] {
  if (!params || typeof params !== "object") return []
  const keys = ["path", "output_path", "file_path", "filename", "filepath", "dest", "destination"]
  const out: string[] = []
  for (const key of keys) {
    const v = params[key]
    if (typeof v === "string") {
      const n = normalizeWorkspacePath(v)
      if (n) out.push(n)
    }
  }
  // attachments: string[]
  const attachments = params.attachments
  if (Array.isArray(attachments)) {
    for (const a of attachments) {
      if (typeof a === "string") {
        const n = normalizeWorkspacePath(a)
        if (n) out.push(n)
      }
    }
  }
  return out
}

/** Pull file paths from tool observation text / JSON. */
export function extractPathsFromObservation(observation: unknown): string[] {
  const text =
    typeof observation === "string"
      ? observation
      : (() => {
          try {
            return JSON.stringify(observation ?? "")
          } catch {
            return String(observation ?? "")
          }
        })()

  const found = new Set<string>()

  // Explicit JSON-ish path fields
  const fieldHits =
    text.matchAll(
      /"(?:path|output_path|file_path|filename)"\s*:\s*"([^"]+)"/gi,
    )
  for (const hit of fieldHits) {
    const n = normalizeWorkspacePath(hit[1])
    if (n) found.add(n)
  }

  FILE_EXT_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = FILE_EXT_RE.exec(text)) !== null) {
    const prefix = m[1] || ""
    const name = m[2]
    if (!name) continue
    const n = normalizeWorkspacePath(prefix ? `${prefix}${name}` : name)
    if (n) found.add(n)
  }

  return Array.from(found)
}

/** Remove the composer-injected attachment footer from user bubble text. */
export function scrubUserContent(content: string): string {
  return content
    .replace(/(?:^|\n+)Attached files:\s*(?:\n\s*-\s*.+)+$/i, "")
    .replace(/(?:^|\n+)Attached files:\s*.+$/i, "")
    .trim()
}

/** Strip backend path / Azure jargon from assistant prose shown in chat. */
export function scrubAssistantContent(content: string): string {
  return content
    .replace(/\bDownload:\s*/gi, "")
    .replace(/`?(?:outputs|uploads)\/([^`\s)]+)`?/gi, (_, name: string) => {
      return fileBasename(name)
    })
    .replace(/\b(?:via\s+)?(?:our\s+)?MCP(?:\/Cosmos)?(?:\s+integration)?\b/gi, "")
    .replace(/\bCosmos(?:\s+DB)?\b/gi, "employee database")
    .replace(/\bAzure\s+Blob(?:\s+Storage)?\b/gi, "secure file storage")
    .replace(/\bblob storage\b/gi, "secure file storage")
    .replace(/\s{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
}

/** Force a real browser download (avoids inline preview hijacking). */
export async function downloadWorkspaceFile(filePath: string): Promise<void> {
  const res = await fetch(workspaceFileUrl(filePath, { download: true }))
  if (!res.ok) {
    throw new Error(res.status === 404 ? "File not found" : "Download failed")
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = fileBasename(filePath)
  a.rel = "noopener"
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
