"use client"

import { useEffect, useRef, useState } from "react"
import { LayoutPanelLeft, PanelRightClose, Sparkles, X } from "lucide-react"
import { useCanvas } from "@/lib/canvas-store"
import { useChat } from "@/lib/chat-store"
import { UiBlockCanvas } from "@/components/ui-block-canvas"
import { cn } from "@/lib/utils"
import type { CanvasStatePayload } from "@/lib/canvas-types"

/**
 * Right-hand Side Canvas: a downstream consumer of completed conversation
 * events. It renders generated ui-block state from /api/canvas/state.
 */
export function SideCanvas() {
  const open = useCanvas((s) => s.open)
  const width = useCanvas((s) => s.width)
  const setOpen = useCanvas((s) => s.setOpen)
  const setWidth = useCanvas((s) => s.setWidth)
  const setServerBlockCount = useCanvas((s) => s.setServerBlockCount)
  const backendConversationId = useChat((s) => s.backendConversationId)
  const [serverCanvas, setServerCanvas] = useState<CanvasStatePayload | null>(null)
  const [dragging, setDragging] = useState(false)
  const dragStartX = useRef(0)
  const dragStartW = useRef(width)

  const hasServerBlocks = !!serverCanvas?.blocks.length
  const evaluating = serverCanvas?.status === "evaluating"

  useEffect(() => {
    if (!backendConversationId) {
      setServerCanvas(null)
      setServerBlockCount(0)
      setOpen(false)
      return
    }

    // Clear previous chat's canvas immediately so we don't flash the wrong one.
    setServerCanvas(null)
    setServerBlockCount(0)

    // Instant restore from last known canvas for this conversation (survives
    // chat switches even if the server cache was cold).
    const cacheKey = `hr-copilot:canvas:${backendConversationId}`
    try {
      const raw = window.localStorage.getItem(cacheKey)
      if (raw) {
        const cached = JSON.parse(raw) as CanvasStatePayload
        if (cached?.blocks?.length) {
          setServerCanvas(cached)
          setServerBlockCount(cached.blocks.length)
          setOpen(true)
        }
      }
    } catch {
      /* ignore */
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null
    let intervalMs = 1000

    const poll = async () => {
      try {
        const res = await fetch(
          `/api/canvas/state?conversationId=${encodeURIComponent(backendConversationId)}`,
        )
        if (!res.ok) return
        const data = (await res.json()) as CanvasStatePayload
        if (cancelled) return
        setServerCanvas(data)
        setServerBlockCount(data.blocks.length)
        if (data.blocks.length > 0) {
          setOpen(true)
          try {
            window.localStorage.setItem(cacheKey, JSON.stringify(data))
          } catch {
            /* ignore */
          }
        }
        intervalMs = data.status === "evaluating" ? 750 : 2500
      } catch {
        /* ignore poll errors */
      } finally {
        if (!cancelled) timer = setTimeout(poll, intervalMs)
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [backendConversationId, setOpen, setServerBlockCount])

  useEffect(() => {
    if (hasServerBlocks) setOpen(true)
  }, [hasServerBlocks, setOpen])

  useEffect(() => {
    if (!dragging) return
    const onMove = (e: MouseEvent) => {
      const delta = dragStartX.current - e.clientX
      setWidth(dragStartW.current + delta)
    }
    const onUp = () => setDragging(false)
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
    return () => {
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
    }
  }, [dragging, setWidth])

  return (
    <aside
      aria-hidden={!open}
      className={cn(
        "relative z-10 shrink-0 overflow-hidden border-l border-border",
        !dragging && "transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
      )}
      style={{ width: open ? width : 0 }}
    >
      {/* Resize handle */}
      {open && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize canvas"
          onMouseDown={(e) => {
            e.preventDefault()
            dragStartX.current = e.clientX
            dragStartW.current = width
            setDragging(true)
          }}
          className="absolute inset-y-0 left-0 z-20 w-1.5 cursor-col-resize hover:bg-primary/20"
        />
      )}

      <div className="panel-surface flex h-full flex-col backdrop-blur-xl" style={{ width }}>
        <div className="shrink-0 border-b border-border/80 bg-card/70 px-4 py-3.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-border bg-accent/60 text-primary shadow-sm">
                <LayoutPanelLeft className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-[13px] font-semibold text-foreground">Canvas</span>
                  {evaluating && (
                    <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                      Building…
                    </span>
                  )}
                  {hasServerBlocks && !evaluating && (
                    <span className="rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
                      {serverCanvas.blocks.length}
                    </span>
                  )}
                </div>
                <p className="truncate text-[11px] text-muted-foreground">
                  Drag the left edge to resize
                </p>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close side canvas"
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="scroll-slim min-h-0 flex-1 overflow-y-auto p-4">
          {hasServerBlocks ? (
            <div className="dream-in space-y-3">
              <UiBlockCanvas
                blocks={serverCanvas.blocks}
                conversationId={serverCanvas.conversationId}
                turnId={serverCanvas.turnId}
              />
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-border bg-card shadow-sm">
                <Sparkles className="h-5 w-5 text-primary/70" />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-foreground">
                  {evaluating ? "Composing the canvas…" : "Nothing to review yet"}
                </p>
                <p className="mt-1.5 max-w-[240px] text-[12px] leading-relaxed text-muted-foreground">
                  {evaluating
                    ? "Vera is assembling a visual summary of this turn."
                    : "Approvals, tables, emails, and rich results land here when they add value."}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}

export function CanvasToggle() {
  const open = useCanvas((s) => s.open)
  const serverBlockCount = useCanvas((s) => s.serverBlockCount)
  const toggle = useCanvas((s) => s.toggle)
  const inChat = useChat((s) => s.activeConversation.length > 0)

  // Always offer Canvas in an active chat so you can reopen after closing it or
  // returning to a previous conversation (block count may lag while state polls).
  if (!inChat) return null

  return (
    <button
      onClick={toggle}
      aria-label="Toggle side canvas"
      aria-pressed={open}
      className={cn(
        "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[13px] font-medium transition-all",
        open
          ? "border-primary/25 bg-accent text-foreground shadow-sm"
          : "border-border bg-card text-muted-foreground hover:bg-secondary hover:text-foreground",
      )}
    >
      <PanelRightClose className="h-4 w-4" />
      <span className="hidden sm:inline">Canvas</span>
      {serverBlockCount > 0 && (
        <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-primary/10 px-1 text-[10px] font-semibold tabular-nums text-primary">
          {serverBlockCount}
        </span>
      )}
    </button>
  )
}
