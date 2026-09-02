"use client"

import { useMemo, useState } from "react"
import {
  Blocks,
  RefreshCw,
  SearchX,
  Store,
  WifiOff,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  PageContainer,
  PageHeader,
  SearchBar,
  SegmentedTabs,
  Tag,
} from "@/components/management/shared"
import { SkillCard } from "./skill-card"
import { SkillDetailPanel } from "./skill-detail"
import { SkillRunDialog } from "./skill-run-dialog"
import {
  groupSkillsByCategory,
  HR_CATEGORIES,
  type HRCategory,
} from "./skill-catalog"
import type { Skill } from "./skill-types"
import { useSkills } from "@/lib/skills-store"
import { useNavigation } from "@/lib/navigation"
import { cn } from "@/lib/utils"

type StatusFilter = "all" | "enabled" | "disabled"

export function SkillsPage() {
  const { skills, dataSource, loadError, refresh, toggleSkill, togglingId } = useSkills()
  const { setView, startChatWithMessage } = useNavigation()

  const [query, setQuery] = useState("")
  const [status, setStatus] = useState<StatusFilter>("all")
  const [category, setCategory] = useState<HRCategory>("All")
  const [detailId, setDetailId] = useState<string | null>(null)
  const [runSkill, setRunSkill] = useState<Skill | null>(null)

  const loading = dataSource === "loading"

  const counts = useMemo(
    () => ({
      all: skills.length,
      enabled: skills.filter((s) => s.enabled).length,
      disabled: skills.filter((s) => !s.enabled).length,
    }),
    [skills],
  )

  const categoryCounts = useMemo(() => {
    const map: Record<string, number> = { All: skills.length }
    for (const s of skills) map[s.category] = (map[s.category] ?? 0) + 1
    return map
  }, [skills])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return skills.filter((s) => {
      const hay = `${s.name} ${s.slug ?? s.id} ${s.description}`.toLowerCase()
      const matchesQuery = !q || hay.includes(q)
      const matchesStatus =
        status === "all" || (status === "enabled" && s.enabled) || (status === "disabled" && !s.enabled)
      const matchesCategory = category === "All" || s.category === category
      return matchesQuery && matchesStatus && matchesCategory
    })
  }, [skills, query, status, category])

  const useSections = category === "All" && !query.trim() && status === "all"
  const sections = useMemo(() => groupSkillsByCategory(filtered), [filtered, useSections])

  const detail = useMemo(() => skills.find((s) => s.id === detailId) ?? null, [skills, detailId])

  const openRunDialog = (skill: Skill) => setRunSkill(skill)

  const activeCategories = HR_CATEGORIES.filter((c) => c === "All" || (categoryCounts[c] ?? 0) > 0)

  return (
    <PageContainer>
      <PageHeader
        title="Skills"
        icon={Blocks}
        description={
          dataSource === "live"
            ? `${counts.enabled} of ${skills.length} HR skills enabled. Toggle a skill to add or remove it from the agent (saved to your active agent profile).`
            : "HR skills from ~/.HRAgent/skills — enable/disable syncs with the agent backend."
        }
        action={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void refresh()} disabled={loading} className="gap-2">
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Refresh
            </Button>
            <Button variant="secondary" onClick={() => setView("marketplace")} className="gap-2">
              <Store className="h-4 w-4" />
              Marketplace
            </Button>
          </div>
        }
      />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="max-w-md flex-1 sm:flex-none sm:min-w-64">
          <SearchBar value={query} onChange={setQuery} placeholder="Search skills..." />
        </div>
        <SegmentedTabs
          tabs={[
            { id: "all", label: "All", count: counts.all },
            { id: "enabled", label: "Enabled", count: counts.enabled },
            { id: "disabled", label: "Disabled", count: counts.disabled },
          ]}
          value={status}
          onChange={setStatus}
        />
      </div>

      <div className="mb-5 flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {activeCategories.map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setCategory(cat)}
            className={cn(
              "flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-colors",
              category === cat
                ? "border-primary/40 bg-primary/10 text-foreground"
                : "border-border/60 bg-secondary/30 text-muted-foreground hover:border-border hover:text-foreground",
            )}
          >
            {cat}
            <Tag className="border-transparent bg-secondary px-1.5 py-0 text-[10px]">{categoryCounts[cat] ?? 0}</Tag>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-[74px] animate-pulse rounded-xl border border-border/60 bg-card/30" />
          ))}
        </div>
      ) : dataSource === "error" ? (
        <div className="dream-in flex flex-col items-center justify-center rounded-xl border border-dashed border-red-500/30 bg-red-500/5 px-6 py-16 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10">
            <WifiOff className="h-5 w-5 text-red-400" />
          </span>
          <p className="mt-4 text-sm font-medium text-foreground">Could not load skills</p>
          <p className="mt-1 max-w-md text-[13px] leading-relaxed text-muted-foreground">{loadError}</p>
          <Button variant="secondary" onClick={() => void refresh()} className="mt-5 gap-2">
            <RefreshCw className="h-4 w-4" />
            Retry
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="dream-in flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-card/30 px-6 py-16 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-border/60 bg-secondary/60">
            <SearchX className="h-5 w-5 text-muted-foreground" />
          </span>
          <p className="mt-4 text-sm font-medium text-foreground">No matching skills</p>
          <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">
            Try a different search or filter, or re-enable skills from the Marketplace.
          </p>
          <Button variant="secondary" onClick={() => setView("marketplace")} className="mt-5 gap-2">
            <Store className="h-4 w-4" />
            Browse marketplace
          </Button>
        </div>
      ) : useSections ? (
        <div className="flex flex-col gap-10">
          {sections.map((section) => (
            <section key={section.category}>
              <div className="mb-3 flex items-baseline justify-between gap-3">
                <h2 className="font-heading text-lg font-semibold text-foreground">{section.category}</h2>
                <span className="text-[12px] tabular-nums text-muted-foreground">{section.skills.length} skills</span>
              </div>
              <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
                {section.skills.map((s) => (
                  <SkillCard
                    key={s.id}
                    skill={s}
                    toggling={togglingId === s.id}
                    onToggle={() => toggleSkill(s.id)}
                    onRun={() => openRunDialog(s)}
                    onOpenDetails={() => setDetailId(s.id)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-2">
          {filtered.map((s) => (
            <SkillCard
              key={s.id}
              skill={s}
              toggling={togglingId === s.id}
              onToggle={() => toggleSkill(s.id)}
              onRun={() => openRunDialog(s)}
              onOpenDetails={() => setDetailId(s.id)}
            />
          ))}
        </div>
      )}

      <SkillDetailPanel
        skill={detail}
        toggling={detail ? togglingId === detail.id : false}
        onOpenChange={(open) => {
          if (!open) setDetailId(null)
        }}
        onToggle={(id) => void toggleSkill(id)}
        onTryInChat={openRunDialog}
      />

      <SkillRunDialog
        skill={runSkill}
        open={runSkill !== null}
        onOpenChange={(open) => {
          if (!open) setRunSkill(null)
        }}
        onLaunch={(message, target) => {
          if (target.kind === "new") {
            startChatWithMessage(message, { newChat: true })
          } else {
            startChatWithMessage(message, { chatId: target.chatId })
          }
        }}
      />
    </PageContainer>
  )
}
