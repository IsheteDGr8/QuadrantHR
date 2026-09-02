"use client"

import { useEffect, useRef, useState } from "react"
import { Activity, ChevronRight, Loader2, Square, X } from "lucide-react"
import {
  useAgentRuntime,
  fmtClock,
  STATUS_LABEL,
  type RunStatus,
} from "@/lib/agent-runtime"
import { PHASE_ICON, ProgressBar } from "@/components/agent-primitives"
import {
  ApiSection,
  DatabaseSection,
  ErrorsSection,
  FilesSection,
  LogsSection,
  McpSection,
  MemorySection,
  SkillsSection,
  StepsSection,
  SubAgentsSection,
  TasksSection,
  TimelineSection,
  ToolsSection,
} from "@/components/agent-sections"
import { cn } from "@/lib/utils"

const PHASES: RunStatus[] = ["thinking", "planning", "executing", "finished"]

const STATUS_STYLES: Record<RunStatus, { dot: string; text: string; ring: string; chip: string }> = {
  idle: {
    dot: "bg-muted-foreground",
    text: "text-foreground",
    ring: "ring-border",
    chip: "bg-secondary text-muted-foreground",
  },
  thinking: {
    dot: "bg-warning",
    text: "text-foreground",
    ring: "ring-warning/30",
    chip: "bg-warning/10 text-warning",
  },
  planning: {
    dot: "bg-warning",
    text: "text-foreground",
    ring: "ring-warning/30",
    chip: "bg-warning/10 text-warning",
  },
  executing: {
    dot: "bg-navy",
    text: "text-foreground",
    ring: "ring-navy/25",
    chip: "bg-navy/10 text-navy",
  },
  finished: {
    dot: "bg-success",
    text: "text-foreground",
    ring: "ring-success/30",
    chip: "bg-success/10 text-success",
  },
  error: {
    dot: "bg-destructive",
    text: "text-destructive",
    ring: "ring-destructive/30",
    chip: "bg-destructive/10 text-destructive",
  },
}

function overallProgress(status: RunStatus, tasks: { progress?: number }[]): number {
  if (status === "finished") return 100
  if (tasks.length > 0) {
    const avg = tasks.reduce((sum, t) => sum + (t.progress ?? 0), 0) / tasks.length
    return Math.max(status === "idle" ? 0 : 8, Math.round(avg))
  }
  return { idle: 0, thinking: 6, planning: 20, executing: 45, finished: 100, error: 100 }[status]
}

/** Header button that opens the live activity panel; pulses while running. */
export function AgentActivityToggle() {
  const { isRunning, hasRun, panelOpen, togglePanel, status } = useAgentRuntime()
  const styles = STATUS_STYLES[status]
  return (
    <button
      onClick={togglePanel}
      aria-label="Toggle agent activity panel"
      aria-pressed={panelOpen}
      className={cn(
        "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[13px] font-medium transition-all",
        panelOpen
          ? "border-primary/25 bg-accent text-foreground shadow-sm"
          : "border-border bg-card text-muted-foreground hover:border-border hover:bg-secondary hover:text-foreground",
      )}
    >
      {isRunning ? (
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
      ) : (
        <Activity className={cn("h-4 w-4", hasRun ? styles.text : "text-muted-foreground")} />
      )}
      <span className="hidden sm:inline">Activity</span>
      {(isRunning || (hasRun && !panelOpen)) && (
        <span className={cn("h-1.5 w-1.5 rounded-full", styles.dot, isRunning && "animate-pulse")} />
      )}
    </button>
  )
}

function PhaseStepper() {
  const { status, phases } = useAgentRuntime()
  const currentIdx = PHASES.indexOf(status === "error" ? "executing" : status)
  return (
    <div className="flex items-center gap-0.5 rounded-xl border border-border/70 bg-card/80 p-1">
      {PHASES.map((p, i) => {
        const Icon = PHASE_ICON[p as keyof typeof PHASE_ICON]
        const done = currentIdx > i || status === "finished"
        const active = currentIdx === i && status !== "finished"
        const phase = phases[p]
        const dur = phase?.end != null && phase.start != null ? phase.end - phase.start : null
        return (
          <div key={p} className="flex min-w-0 flex-1 items-center">
            <div
              className={cn(
                "flex w-full items-center justify-center gap-1 rounded-lg px-1.5 py-1.5 text-[10px] font-semibold transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : done
                    ? "text-muted-foreground"
                    : "text-muted-foreground/60",
              )}
            >
              {active ? <Loader2 className="h-3 w-3 animate-spin" /> : <Icon className="h-3 w-3" />}
              <span className="capitalize">{p}</span>
              {dur != null && (
                <span className="hidden tabular-nums text-muted-foreground lg:inline">
                  {(dur / 1000).toFixed(1)}s
                </span>
              )}
            </div>
            {i < PHASES.length - 1 && (
              <ChevronRight
                className={cn(
                  "mx-0.5 h-3 w-3 shrink-0",
                  currentIdx > i ? "text-primary/50" : "text-border",
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function AgentExecutionPanel() {
  const {
    panelOpen,
    setPanelOpen,
    panelWidth,
    setPanelWidth,
    status,
    elapsedMs,
    events,
    isRunning,
    stopRun,
    prompt,
  } = useAgentRuntime()
  const styles = STATUS_STYLES[status]
  const tasks = events.filter((e) => e.category === "task")
  const progress = overallProgress(status, tasks)
  const [dragging, setDragging] = useState(false)
  const dragStartX = useRef(0)
  const dragStartW = useRef(panelWidth)

  useEffect(() => {
    if (!dragging) return
    const onMove = (e: MouseEvent) => {
      const delta = dragStartX.current - e.clientX
      setPanelWidth(dragStartW.current + delta)
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
  }, [dragging, setPanelWidth])

  return (
    <aside
      aria-hidden={!panelOpen}
      className={cn(
        "relative z-10 shrink-0 overflow-hidden border-l border-border",
        !dragging && "transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
      )}
      style={{ width: panelOpen ? panelWidth : 0 }}
    >
      {panelOpen && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize activity panel"
          onMouseDown={(e) => {
            e.preventDefault()
            dragStartX.current = e.clientX
            dragStartW.current = panelWidth
            setDragging(true)
          }}
          className="absolute inset-y-0 left-0 z-20 w-1.5 cursor-col-resize hover:bg-primary/20"
        />
      )}

      <div className="panel-surface flex h-full flex-col backdrop-blur-xl" style={{ width: panelWidth }}>
        <div className="shrink-0 border-b border-border/80 bg-card/60 px-4 py-3.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2.5">
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold ring-1",
                  styles.chip,
                  styles.ring,
                )}
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", styles.dot, isRunning && "animate-pulse")} />
                {STATUS_LABEL[status]}
              </div>
              <span className="text-[12px] tabular-nums text-muted-foreground">{fmtClock(elapsedMs)}</span>
            </div>
            <div className="flex items-center gap-1">
              {isRunning && (
                <button
                  onClick={stopRun}
                  aria-label="Stop run"
                  className="flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                >
                  <Square className="h-3 w-3" />
                  Stop
                </button>
              )}
              <button
                onClick={() => setPanelOpen(false)}
                aria-label="Close activity panel"
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-3.5 flex items-center gap-3">
            <ProgressBar value={progress} className="flex-1" />
            <span className="text-[11px] font-medium tabular-nums text-muted-foreground">{progress}%</span>
          </div>

          <div className="mt-3">
            <PhaseStepper />
          </div>

          {prompt && (
            <p className="mt-3 truncate rounded-lg border border-border/60 bg-secondary/40 px-2.5 py-1.5 text-[11px] text-muted-foreground">
              <span className="font-semibold text-foreground/70">Objective</span>
              <span className="mx-1.5 text-border">·</span>
              {prompt}
            </p>
          )}
        </div>

        <div className="scroll-slim min-h-0 flex-1 overflow-y-auto">
          {status === "idle" ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border bg-card shadow-sm">
                <Activity className="h-5 w-5 text-primary" />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-foreground">No active run</p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                  Send Vera a message to watch tools, skills, and progress stream in live.
                </p>
              </div>
            </div>
          ) : (
            <>
              <TimelineSection />
              <TasksSection />
              <StepsSection />
              <ToolsSection />
              <SubAgentsSection />
              <McpSection />
              <SkillsSection />
              <MemorySection />
              <DatabaseSection />
              <FilesSection />
              <ApiSection />
              <ErrorsSection />
              <LogsSection />
            </>
          )}
        </div>
      </div>
    </aside>
  )
}
