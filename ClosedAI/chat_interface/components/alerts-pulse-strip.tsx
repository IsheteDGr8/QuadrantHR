"use client"

import * as React from "react"
import { Bell, ChevronRight } from "lucide-react"
import type { HrAlert } from "@/components/hr-alerts-bell"
import { useNavigation } from "@/lib/navigation"
import { cn } from "@/lib/utils"

/** Compact alert strip for the Tasks dashboard — surfaces the top pulses inline. */
export function AlertsPulseStrip({ className }: { className?: string }) {
  const { setView } = useNavigation()
  const [alerts, setAlerts] = React.useState<HrAlert[]>([])

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const res = await fetch("/api/alerts", { cache: "no-store" })
        const data = await res.json()
        if (!cancelled && Array.isArray(data.alerts)) {
          setAlerts((data.alerts as HrAlert[]).slice(0, 3))
        }
      } catch {
        /* ignore */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (alerts.length === 0) return null

  return (
    <div
      className={cn(
        "mb-5 overflow-hidden rounded-2xl border border-[#FFD9C8] bg-gradient-to-r from-[#FFF8F4] via-white to-[#FFF6F0]",
        className,
      )}
    >
      <div className="flex items-center gap-2 border-b border-[#FFE8DE]/80 px-4 py-2.5">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#FF6B4A]/15 text-[#FF6B4A]">
          <Bell className="h-3.5 w-3.5" />
        </span>
        <p className="text-xs font-semibold uppercase tracking-wider text-[#8B6454]">
          Needs your attention
        </p>
        <span className="ml-auto rounded-full bg-[#FF6B4A]/10 px-2 py-0.5 text-[11px] font-semibold text-[#C24E2E]">
          {alerts.length}
        </span>
      </div>
      <ul className="divide-y divide-[#FFE8DE]/70">
        {alerts.map((a) => (
          <li key={a.id}>
            <button
              type="button"
              onClick={() => {
                if (a.href?.startsWith("/work")) setView("work")
                else setView("intake")
              }}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-[#FFF6F0]"
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 shrink-0 rounded-full",
                  a.severity === "critical"
                    ? "bg-red-500"
                    : a.severity === "high"
                      ? "bg-[#FF6B4A]"
                      : "bg-[#FFB89A]",
                )}
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-[#3D2218]">
                  {a.title}
                </span>
                <span className="block truncate text-[11px] text-[#A06B55]">{a.body}</span>
              </span>
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[#C9A090]" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
