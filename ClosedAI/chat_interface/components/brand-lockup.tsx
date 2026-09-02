"use client"

import { cn } from "@/lib/utils"

interface BrandLockupProps {
  className?: string
  /** Compact for tight headers; default fits the sidebar. */
  size?: "sm" | "md"
}

/**
 * Product lockup: Vera mark + wordmark only (no tagline).
 */
export function BrandLockup({ className, size = "md" }: BrandLockupProps) {
  const mark = size === "sm" ? "h-8 w-8" : "h-9 w-9"
  const img = size === "sm" ? "h-6 w-6" : "h-7 w-7"
  const word = size === "sm" ? "text-[15px]" : "text-[17px]"

  return (
    <div className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <span
        className={cn(
          "relative flex shrink-0 items-center justify-center overflow-hidden rounded-xl border border-sidebar-border/70 bg-white/90 shadow-sm",
          mark,
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/vera.png" alt="" className={cn("object-contain", img)} />
      </span>
      <span
        className={cn(
          "truncate font-[family-name:var(--font-brand)] font-semibold tracking-[-0.03em] text-sidebar-foreground",
          word,
        )}
      >
        Vera
        <span className="ml-1.5 font-medium tracking-[0.06em] text-muted-foreground">HR</span>
      </span>
    </div>
  )
}
