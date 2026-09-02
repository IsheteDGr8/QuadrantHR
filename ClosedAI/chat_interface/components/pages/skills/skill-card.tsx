"use client"

import { useState } from "react"
import { ChevronDown, Maximize2, Play } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { categoryIcon } from "./skill-data"
import type { Skill } from "./skill-types"
import { cn } from "@/lib/utils"

/* Compact skill card: keeps the skills-card look but collapses the (often long)
   description behind an accordion so each row stays small. Carries a Run button
   (like the automation cards) that fires the skill in chat, plus the enable
   switch and a link into the full detail panel. */
export function SkillCard({
  skill,
  toggling,
  onToggle,
  onRun,
  onOpenDetails,
}: {
  skill: Skill
  toggling: boolean
  onToggle: () => void
  onRun: () => void
  onOpenDetails: () => void
}) {
  const [open, setOpen] = useState(false)
  const Icon = categoryIcon(skill.category)
  const panelId = `skill-desc-${skill.id}`
  const triggerLabel = skill.isKeywordTriggered ? "Auto" : skill.triggerType

  return (
    <div className="group rounded-xl border border-border/60 bg-card/40 transition-colors duration-150 hover:border-border hover:bg-card/70">
      <div className="flex items-center gap-3 p-4">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-secondary/60">
          <Icon className="h-[18px] w-[18px] text-muted-foreground" />
        </span>

        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls={panelId}
          className="min-w-0 flex-1 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <span className="block truncate text-[15px] font-semibold text-foreground">{skill.name}</span>
          <span className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
            <span className="truncate">{skill.category}</span>
            <span className="shrink-0 rounded-full border border-border/60 bg-secondary/40 px-1.5 py-0.5 text-[10px] font-medium">
              {triggerLabel}
            </span>
          </span>
        </button>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onRun}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground"
          >
            <Play className="h-3 w-3" />
            Run
          </button>
          <Switch
            checked={skill.enabled}
            onCheckedChange={() => {
              if (!toggling) onToggle()
            }}
            disabled={toggling}
            aria-label={`Toggle ${skill.name}`}
          />
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            aria-controls={panelId}
            aria-label={open ? `Collapse ${skill.name}` : `Expand ${skill.name}`}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", open && "rotate-180")} />
          </button>
        </div>
      </div>

      {open && (
        <div id={panelId} className="dream-in border-t border-border/60 px-4 pb-4 pt-3">
          <p className="text-[13px] leading-relaxed text-muted-foreground">{skill.description}</p>
          <div className="mt-3 flex items-center justify-end">
            <button
              type="button"
              onClick={onOpenDetails}
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <Maximize2 className="h-3.5 w-3.5" />
              View details
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
