"use client"

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  Download,
  Expand,
  FileText,
  Loader2,
  Maximize2,
  Minimize2,
  PanelRight,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  downloadWorkspaceFile,
  fileBasename,
  fileExt,
  friendlyFileTitle,
  isPdf,
  isTextPreviewable,
  workspaceFileUrl,
} from "@/lib/workspace-files"

/** dock = side sheet · popup = centered modal · fullscreen = edge-to-edge */
export type DocPreviewMode = "dock" | "popup" | "fullscreen"

type DocumentPreviewProps = {
  filePath: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  /** How the viewer opens. Canvas should use "popup"; chat can use "dock". */
  initialMode?: DocPreviewMode
}

const MIN_DOCK_WIDTH = 480
const MAX_DOCK_RATIO = 0.88

function CsvTable({ text }: { text: string }) {
  const rows = text
    .trim()
    .split(/\r?\n/)
    .map((line) => {
      const cells: string[] = []
      let cur = ""
      let inQuotes = false
      for (let i = 0; i < line.length; i++) {
        const ch = line[i]
        if (ch === '"') {
          if (inQuotes && line[i + 1] === '"') {
            cur += '"'
            i++
          } else inQuotes = !inQuotes
        } else if (ch === "," && !inQuotes) {
          cells.push(cur)
          cur = ""
        } else cur += ch
      }
      cells.push(cur)
      return cells
    })
    .filter((r) => r.some((c) => c.trim()))

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">Empty spreadsheet</p>
  }

  const [header, ...body] = rows
  return (
    <div className="overflow-auto rounded-xl border border-black/5 bg-white shadow-sm">
      <table className="w-full min-w-max border-collapse text-left text-[13px]">
        <thead>
          <tr className="bg-[#1c1917] text-[#fafaf9]">
            {header.map((cell, i) => (
              <th
                key={i}
                className="sticky top-0 whitespace-nowrap px-3.5 py-2.5 font-[family-name:var(--font-heading)] text-[11px] font-semibold uppercase tracking-[0.06em]"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr
              key={ri}
              className={cn(
                "border-t border-stone-100 transition-colors",
                ri % 2 === 0 ? "bg-stone-50/80" : "bg-white",
                "hover:bg-amber-50/70",
              )}
            >
              {header.map((_, ci) => (
                <td key={ci} className="whitespace-nowrap px-3.5 py-2 text-stone-700">
                  {row[ci] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TextDocumentBody({
  filePath,
  roomy,
}: {
  filePath: string
  roomy?: boolean
}) {
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const ext = fileExt(filePath)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setText(null)
    fetch(workspaceFileUrl(filePath))
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 404 ? "Document not found" : "Could not load document")
        return res.text()
      })
      .then((body) => {
        if (!cancelled) {
          setText(body)
          setLoading(false)
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [filePath])

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-stone-500">
        <Loader2 className="h-6 w-6 animate-spin text-amber-700/70" />
        <p className="text-sm">Opening document…</p>
      </div>
    )
  }

  if (error || text == null) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-8 text-center">
        <p className="font-[family-name:var(--font-heading)] text-lg text-stone-800">Couldn’t open this file</p>
        <p className="text-sm text-stone-500">{error || "Unknown error"}</p>
      </div>
    )
  }

  const pad = roomy ? "px-10 py-8 md:px-14 lg:px-20" : "px-8 py-7 md:px-10"

  // Parent body pane owns overflow scrolling (popup/dock need a flex-constrained
  // scrollport). Don't put h-full+overflow-auto here — that only works when the
  // outer shell has a definite height (fullscreen), which the popup does not.
  if (ext === ".csv") {
    return (
      <div className={pad}>
        <CsvTable text={text} />
      </div>
    )
  }

  if (ext === ".json") {
    let pretty = text
    try {
      pretty = JSON.stringify(JSON.parse(text), null, 2)
    } catch {
      /* keep raw */
    }
    return (
      <div className={pad}>
        <pre className="overflow-x-auto rounded-xl border border-stone-200/80 bg-stone-950 p-5 text-[13px] leading-relaxed text-amber-50/95 shadow-inner">
          {pretty}
        </pre>
      </div>
    )
  }

  if (ext === ".md") {
    return (
      <article
        className={cn(
          "doc-prose",
          pad,
          roomy && "mx-auto max-w-4xl",
        )}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      </article>
    )
  }

  return (
    <div className={pad}>
      <pre className="mx-auto max-w-4xl whitespace-pre-wrap font-mono text-[13px] leading-relaxed text-stone-800">
        {text}
      </pre>
    </div>
  )
}

function UnsupportedBody({ filePath }: { filePath: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-100 to-orange-50 shadow-inner ring-1 ring-amber-900/10">
        <FileText className="h-7 w-7 text-amber-900/70" />
      </div>
      <div className="space-y-1.5">
        <p className="font-[family-name:var(--font-heading)] text-lg text-stone-900">
          Preview isn’t available for {fileExt(filePath).slice(1).toUpperCase() || "this"} files
        </p>
        <p className="max-w-sm text-sm text-stone-500">
          Download the file to open it in your usual app.
        </p>
      </div>
    </div>
  )
}

function PaperGrain() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 opacity-[0.35] mix-blend-multiply"
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.45'/%3E%3C/svg%3E\")",
      }}
    />
  )
}

export function DocumentPreview({
  filePath,
  open,
  onOpenChange,
  initialMode = "popup",
}: DocumentPreviewProps) {
  const [mode, setMode] = useState<DocPreviewMode>(initialMode)
  const [dockWidth, setDockWidth] = useState(560)
  const [zoom, setZoom] = useState(1)
  const [downloading, setDownloading] = useState(false)
  const dragRef = useRef<{ startX: number; startW: number } | null>(null)
  const prevOpen = useRef(false)

  // Reset mode each time the viewer opens
  useEffect(() => {
    if (open && !prevOpen.current) {
      setMode(initialMode)
      setZoom(1)
    }
    prevOpen.current = open
  }, [open, initialMode])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (mode === "fullscreen") {
          setMode("popup")
        } else {
          onOpenChange(false)
        }
      }
      if ((e.key === "f" || e.key === "F") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setMode((m) => (m === "fullscreen" ? "popup" : "fullscreen"))
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onOpenChange, mode])

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  useEffect(() => {
    if (typeof window === "undefined") return
    const preferred = Math.min(Math.max(Math.floor(window.innerWidth * 0.42), MIN_DOCK_WIDTH), 720)
    setDockWidth(preferred)
  }, [])

  const onResizeMove = useCallback((e: MouseEvent) => {
    if (!dragRef.current) return
    const delta = dragRef.current.startX - e.clientX
    const maxW = Math.floor(window.innerWidth * MAX_DOCK_RATIO)
    const next = Math.min(Math.max(dragRef.current.startW + delta, MIN_DOCK_WIDTH), maxW)
    setDockWidth(next)
  }, [])

  const onResizeEnd = useCallback(() => {
    dragRef.current = null
    document.body.style.cursor = ""
    document.body.style.userSelect = ""
    window.removeEventListener("mousemove", onResizeMove)
    window.removeEventListener("mouseup", onResizeEnd)
  }, [onResizeMove])

  const onResizeStart = (e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startW: dockWidth }
    document.body.style.cursor = "ew-resize"
    document.body.style.userSelect = "none"
    window.addEventListener("mousemove", onResizeMove)
    window.addEventListener("mouseup", onResizeEnd)
  }

  if (!open || !filePath) return null

  const title = friendlyFileTitle(filePath)
  const extLabel = fileExt(filePath).replace(".", "").toUpperCase() || "FILE"
  const roomy = mode === "popup" || mode === "fullscreen"

  const handleDownload = async () => {
    setDownloading(true)
    try {
      await downloadWorkspaceFile(filePath)
    } catch {
      window.location.href = workspaceFileUrl(filePath, { download: true })
    } finally {
      setDownloading(false)
    }
  }

  const headerActions = (
    <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
      {isPdf(filePath) && (
        <>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-stone-600 hover:bg-stone-900/5 hover:text-stone-900"
            onClick={() => setZoom((z) => Math.max(0.6, Number((z - 0.1).toFixed(2))))}
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="w-10 text-center text-[11px] tabular-nums text-stone-500">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-stone-600 hover:bg-stone-900/5 hover:text-stone-900"
            onClick={() => setZoom((z) => Math.min(1.8, Number((z + 0.1).toFixed(2))))}
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <span className="mx-1 h-4 w-px bg-stone-300/80" />
        </>
      )}

      {mode !== "popup" && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-stone-600 hover:bg-stone-900/5 hover:text-stone-900"
          onClick={() => setMode("popup")}
          title="Open as popup"
        >
          <Expand className="h-3.5 w-3.5" />
          <span className="text-xs">Popup</span>
        </Button>
      )}

      {mode !== "dock" && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-stone-600 hover:bg-stone-900/5 hover:text-stone-900"
          onClick={() => setMode("dock")}
          title="Dock to side"
        >
          <PanelRight className="h-3.5 w-3.5" />
          <span className="text-xs">Dock</span>
        </Button>
      )}

      {mode !== "fullscreen" ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 rounded-md bg-amber-900/10 px-2.5 text-amber-950 hover:bg-amber-900/15"
          onClick={() => setMode("fullscreen")}
          title="Full screen"
        >
          <Maximize2 className="h-3.5 w-3.5" />
          <span className="text-xs font-medium">Full screen</span>
        </Button>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-stone-600 hover:bg-stone-900/5 hover:text-stone-900"
          onClick={() => setMode("popup")}
          title="Exit full screen"
        >
          <Minimize2 className="h-3.5 w-3.5" />
          <span className="text-xs">Exit</span>
        </Button>
      )}

      <Button
        type="button"
        onClick={handleDownload}
        disabled={downloading}
        className="ml-1 h-8 gap-1.5 rounded-lg bg-[#2c241b] px-3 text-xs font-medium text-[#f5e6d3] hover:bg-[#3d3226]"
      >
        {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
        Download
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-stone-600 hover:bg-stone-900/5 hover:text-stone-900"
        onClick={() => onOpenChange(false)}
        title="Close"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  )

  const header = (
    <header className="relative z-10 flex items-start gap-3 border-b border-stone-300/50 bg-[#faf7f1]/95 px-5 py-3.5 backdrop-blur-md">
      <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#2c241b] to-[#4a3728] text-[#f5e6d3] shadow-md shadow-stone-900/15">
        <FileText className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-[family-name:var(--font-heading)] text-[16px] font-semibold leading-snug tracking-tight text-stone-900">
          {title}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-stone-500">
          <span className="rounded-md bg-stone-900/5 px-1.5 py-0.5 font-semibold uppercase tracking-wider text-stone-600">
            {extLabel}
          </span>
          <span className="truncate">{fileBasename(filePath)}</span>
          {mode === "fullscreen" && (
            <span className="rounded-md bg-amber-900/10 px-1.5 py-0.5 text-amber-900/70">Full screen</span>
          )}
        </div>
      </div>
      {headerActions}
    </header>
  )

  const body = (
    <div className="relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain">
      {isPdf(filePath) ? (
        <div className={cn("min-h-full bg-stone-300/40", roomy ? "p-5 md:p-8" : "p-3")}>
          <div
            className="mx-auto origin-top rounded-lg bg-white shadow-lg shadow-stone-900/10 transition-transform"
            style={{
              width: `${zoom * 100}%`,
              maxWidth: roomy ? "960px" : "100%",
            }}
          >
            <iframe
              src={workspaceFileUrl(filePath)}
              className={cn(
                "w-full rounded-lg border-0 bg-white",
                mode === "fullscreen" ? "h-[calc(100vh-5.5rem)]" : "h-[calc(100vh-8.5rem)]",
              )}
              title={title}
            />
          </div>
        </div>
      ) : isTextPreviewable(filePath) ? (
        <TextDocumentBody filePath={filePath} roomy={roomy} />
      ) : (
        <UnsupportedBody filePath={filePath} />
      )}
    </div>
  )

  const panelStyle = {
    background: "linear-gradient(165deg, #f7f3ec 0%, #f3eee4 42%, #efe8dc 100%)",
  } as const

  let overlay: ReactNode

  if (mode === "fullscreen") {
    overlay = (
      <div
        className="fixed inset-0 z-[200] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-label="Document full screen"
        style={panelStyle}
      >
        <PaperGrain />
        {header}
        {body}
        <footer className="relative z-10 border-t border-stone-300/40 bg-[#faf7f1]/90 px-5 py-1.5 text-[11px] text-stone-500">
          Esc exits full screen · Ctrl/⌘+F toggles full screen
        </footer>
      </div>
    )
  } else if (mode === "popup") {
    overlay = (
      <div
        className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6 md:p-8"
        role="dialog"
        aria-modal="true"
        aria-label="Document popup"
      >
        <button
          type="button"
          className="absolute inset-0 bg-[#1c1917]/50 backdrop-blur-[4px]"
          aria-label="Close preview"
          onClick={() => onOpenChange(false)}
        />
        <div
          className="relative z-[1] flex h-[min(92vh,920px)] max-h-[min(94vh,960px)] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-stone-200/90 shadow-[0_32px_80px_rgba(28,25,23,0.28)]"
          style={panelStyle}
        >
          <PaperGrain />
          {header}
          {body}
          <footer className="relative z-10 border-t border-stone-300/40 bg-[#faf7f1]/90 px-5 py-1.5 text-[11px] text-stone-500">
            Click <span className="font-medium text-stone-800">Full screen</span> for edge-to-edge · Esc to close
          </footer>
        </div>
      </div>
    )
  } else {
    overlay = (
      <div className="fixed inset-0 z-[200] flex justify-end" role="dialog" aria-modal="true" aria-label="Document preview">
        <button
          type="button"
          className="absolute inset-0 bg-[#1c1917]/45 backdrop-blur-[3px]"
          aria-label="Close preview"
          onClick={() => onOpenChange(false)}
        />
        <aside
          className="doc-preview-panel relative z-[1] flex h-full flex-col overflow-hidden border-l border-stone-200/80 shadow-[-24px_0_60px_rgba(28,25,23,0.18)]"
          style={{ width: dockWidth, ...panelStyle }}
        >
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize preview"
            onMouseDown={onResizeStart}
            className="group absolute left-0 top-0 z-20 flex h-full w-3 -translate-x-1/2 cursor-ew-resize items-center justify-center"
          >
            <div className="h-16 w-1 rounded-full bg-stone-400/50 transition-all group-hover:h-24 group-hover:bg-amber-700/70" />
          </div>
          <PaperGrain />
          {header}
          {body}
          <footer className="relative z-10 border-t border-stone-300/40 bg-[#faf7f1]/80 px-5 py-2 text-[11px] text-stone-500 backdrop-blur-sm">
            Drag edge to resize · use Popup / Full screen for a larger view · Esc to close
          </footer>
        </aside>
      </div>
    )
  }

  // Portal to body so fixed positioning is never trapped by Canvas
  // (SideCanvas uses width transitions / overflow that create a containing block).
  if (typeof document === "undefined") return null
  return createPortal(overlay, document.body)
}
