"use client"

import * as React from "react"
import { createPortal } from "react-dom"
import {
  Bell,
  Cake,
  CalendarHeart,
  CheckCircle2,
  Mail,
  RefreshCw,
  ShieldAlert,
  Stamp,
  TriangleAlert,
} from "lucide-react"
import { useNavigation, type View } from "@/lib/navigation"
import { cn } from "@/lib/utils"

export type AlertKind =
  | "email_important"
  | "birthday"
  | "anniversary"
  | "work_auth"
  | "needs_approval"
  | "urgent_task"

export type HrAlert = {
  id: string
  kind: AlertKind
  severity: "critical" | "high" | "info"
  title: string
  body: string
  href?: string
  at: string
}

const KIND_META: Record<
  AlertKind,
  { label: string; icon: typeof Bell; tone: string }
> = {
  email_important: {
    label: "Important email",
    icon: Mail,
    tone: "bg-[#FF6B4A]/12 text-[#C24E2E]",
  },
  birthday: {
    label: "Birthday",
    icon: Cake,
    tone: "bg-rose-500/10 text-rose-700",
  },
  anniversary: {
    label: "Anniversary",
    icon: CalendarHeart,
    tone: "bg-violet-500/10 text-violet-700",
  },
  work_auth: {
    label: "Work auth",
    icon: Stamp,
    tone: "bg-amber-500/10 text-amber-800",
  },
  needs_approval: {
    label: "Needs you",
    icon: ShieldAlert,
    tone: "bg-orange-500/10 text-orange-800",
  },
  urgent_task: {
    label: "Urgent task",
    icon: TriangleAlert,
    tone: "bg-red-500/10 text-red-700",
  },
}

function hrefToView(href?: string): View | null {
  if (!href) return null
  if (href.startsWith("/work")) return "work"
  if (href.startsWith("/intake")) return "intake"
  return null
}

const PANEL_WIDTH = 360

export function HrAlertsBell({ className }: { className?: string }) {
  const { setView } = useNavigation()
  const [open, setOpen] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [alerts, setAlerts] = React.useState<HrAlert[]>([])
  const [panelPos, setPanelPos] = React.useState<{ top: number; left: number } | null>(null)
  const [dismissed, setDismissed] = React.useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set()
    try {
      const raw = window.localStorage.getItem("hr-copilot:alerts-dismissed")
      if (!raw) return new Set()
      return new Set(JSON.parse(raw) as string[])
    } catch {
      return new Set()
    }
  })
  const buttonRef = React.useRef<HTMLButtonElement>(null)
  const panelRef = React.useRef<HTMLDivElement>(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch("/api/alerts", { cache: "no-store" })
      const data = await res.json()
      setAlerts(Array.isArray(data.alerts) ? (data.alerts as HrAlert[]) : [])
    } catch {
      setAlerts([])
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void load()
    const id = window.setInterval(() => void load(), 60_000)
    return () => window.clearInterval(id)
  }, [load])

  const placePanel = React.useCallback(() => {
    const btn = buttonRef.current
    if (!btn) return
    const r = btn.getBoundingClientRect()
    const gap = 10
    let left = r.right + gap
    let top = r.top
    if (left + PANEL_WIDTH > window.innerWidth - 12) {
      left = Math.max(12, r.left - PANEL_WIDTH - gap)
    }
    const estimatedHeight = Math.min(480, window.innerHeight - 24)
    if (top + estimatedHeight > window.innerHeight - 12) {
      top = Math.max(12, window.innerHeight - 12 - estimatedHeight)
    }
    setPanelPos({ top, left })
  }, [])

  React.useEffect(() => {
    if (!open) {
      setPanelPos(null)
      return
    }
    placePanel()
    const onResize = () => placePanel()
    window.addEventListener("resize", onResize)
    window.addEventListener("scroll", onResize, true)
    return () => {
      window.removeEventListener("resize", onResize)
      window.removeEventListener("scroll", onResize, true)
    }
  }, [open, placePanel])

  React.useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (buttonRef.current?.contains(t) || panelRef.current?.contains(t)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDoc)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const visible = alerts.filter((a) => !dismissed.has(a.id))
  const count = visible.length

  const persistDismissed = (next: Set<string>) => {
    setDismissed(next)
    try {
      window.localStorage.setItem(
        "hr-copilot:alerts-dismissed",
        JSON.stringify([...next].slice(-200)),
      )
    } catch {
      /* ignore */
    }
  }

  const dismiss = (id: string) => {
    const next = new Set(dismissed)
    next.add(id)
    persistDismissed(next)
  }

  const dismissAll = () => {
    const next = new Set(dismissed)
    for (const a of visible) next.add(a.id)
    persistDismissed(next)
  }

  const openAlert = (a: HrAlert) => {
    const view = hrefToView(a.href)
    if (view) setView(view)
    dismiss(a.id)
    setOpen(false)
  }

  const panel =
    open && panelPos && typeof document !== "undefined"
      ? createPortal(
          <div
            ref={panelRef}
            style={{ top: panelPos.top, left: panelPos.left, width: PANEL_WIDTH }}
            className="fixed z-[200] overflow-hidden rounded-2xl border border-[#FFD9C8] bg-white shadow-[0_24px_60px_-24px_rgba(92,43,26,0.55)]"
            role="dialog"
            aria-label="HR pulse alerts"
          >
            <div className="flex items-center justify-between border-b border-[#FFE8DE] bg-gradient-to-r from-[#FFF8F4] to-white px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#3D2218]">HR pulse</p>
                <p className="truncate text-[11px] text-[#A06B55]">
                  Birthdays, mail, approvals &amp; deadlines
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => void load()}
                  disabled={loading}
                  aria-label="Refresh alerts"
                  className="rounded-md p-1.5 text-[#A06B55] hover:bg-[#FFE8DE] hover:text-[#5C2B1A]"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
                </button>
                {count > 0 && (
                  <button
                    type="button"
                    onClick={dismissAll}
                    className="rounded-md px-2 py-1 text-[11px] font-medium text-[#A06B55] hover:bg-[#FFE8DE] hover:text-[#5C2B1A]"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="max-h-[min(420px,calc(100vh-48px))] overflow-y-auto">
              {loading && visible.length === 0 ? (
                <div className="space-y-2 p-4">
                  <div className="h-12 animate-pulse rounded-xl bg-[#FFF6F0]" />
                  <div className="h-12 animate-pulse rounded-xl bg-[#FFF6F0]" />
                </div>
              ) : visible.length === 0 ? (
                <div className="flex flex-col items-center px-6 py-10 text-center">
                  <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[#FFF6F0] text-[#FF6B4A]">
                    <CheckCircle2 className="h-5 w-5" />
                  </span>
                  <p className="text-sm font-semibold text-[#3D2218]">All clear</p>
                  <p className="mt-1 text-[12px] leading-relaxed text-[#A06B55]">
                    No urgent birthdays, approvals, or important mail right now.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-[#FFE8DE]">
                  {visible.map((a) => {
                    const meta = KIND_META[a.kind]
                    const Icon = meta.icon
                    return (
                      <li key={a.id}>
                        <button
                          type="button"
                          onClick={() => openAlert(a)}
                          className="flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-[#FFF8F4]"
                        >
                          <span
                            className={cn(
                              "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                              meta.tone,
                            )}
                          >
                            <Icon className="h-3.5 w-3.5" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-2">
                              <span className="text-[10px] font-semibold uppercase tracking-wide text-[#A06B55]">
                                {meta.label}
                              </span>
                              {a.severity === "critical" && (
                                <span className="rounded bg-red-100 px-1.5 py-0.5 text-[9px] font-bold uppercase text-red-700">
                                  Critical
                                </span>
                              )}
                            </span>
                            <span className="mt-0.5 block truncate text-[13px] font-semibold text-[#3D2218]">
                              {a.title}
                            </span>
                            <span className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-[#8B6454]">
                              {a.body}
                            </span>
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </div>,
          document.body,
        )
      : null

  return (
    <div className={cn("relative", className)}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => {
          setOpen((o) => !o)
          if (!open) void load()
        }}
        aria-label={count ? `${count} HR alerts` : "HR alerts"}
        aria-expanded={open}
        className={cn(
          "relative flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors",
          "hover:bg-sidebar-accent hover:text-sidebar-foreground",
          open && "bg-sidebar-accent text-sidebar-foreground",
        )}
      >
        <Bell className="h-4 w-4" />
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#FF6B4A] px-1 text-[10px] font-bold leading-none text-white shadow-sm">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>
      {panel}
    </div>
  )
}
