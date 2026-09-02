"use client"

import { useMemo, type ReactNode } from "react"
import {
  BookOpen,
  CheckCircle2,
  CircleDot,
  Copy,
  FileText,
  Play,
  Sparkles,
  Zap,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  CATEGORY_TONES,
  DrawerShell,
  PanelSection,
  DetailRow,
  Tag,
} from "@/components/management/shared"
import { categoryIcon } from "./skill-data"
import { stripFrontmatter } from "./skill-catalog"
import type { Skill } from "./skill-types"

export interface SkillDetailPanelProps {
  skill: Skill | null
  toggling?: boolean
  onOpenChange: (open: boolean) => void
  onToggle: (id: string) => void
  onTryInChat: (skill: Skill) => void
}

export function SkillDetailPanel({ skill, toggling, onOpenChange, onToggle, onTryInChat }: SkillDetailPanelProps) {
  const Icon = skill ? categoryIcon(skill.category) : null

  const markdownBody = useMemo(() => {
    if (!skill) return ""
    if (skill.contentMarkdown) return stripFrontmatter(skill.contentMarkdown)
    return skill.instructions
  }, [skill])

  const copySlug = () => {
    if (!skill) return
    const slug = skill.slug ?? skill.id
    void navigator.clipboard.writeText(slug)
    toast.success(`Copied ${slug}`)
  }

  return (
    <DrawerShell
      open={skill !== null}
      onOpenChange={onOpenChange}
      eyebrow="HR Skill"
      icon={Icon ? <Icon className="h-5 w-5" /> : undefined}
      iconClassName={skill ? (CATEGORY_TONES[skill.category] ?? "border-border/60 bg-secondary/60 text-foreground") : undefined}
      title={skill?.name ?? ""}
      description={skill?.description}
      meta={
        skill ? (
          <>
            <Tag>{skill.slug ?? skill.id}</Tag>
            <Tag>{skill.category}</Tag>
            <Tag>v{skill.version}</Tag>
            {skill.isKeywordTriggered ? (
              <Tag className="border-amber-500/25 bg-amber-500/10 text-amber-300">
                <Zap className="mr-1 inline h-3 w-3" />
                Auto-trigger
              </Tag>
            ) : (
              <Tag>invoke_skill</Tag>
            )}
            {skill.maturity && <Tag className="capitalize">{skill.maturity}</Tag>}
          </>
        ) : undefined
      }
      footer={
        skill ? (
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Switch
                checked={skill.enabled}
                disabled={toggling}
                onCheckedChange={() => onToggle(skill.id)}
                aria-label={`Toggle ${skill.name}`}
              />
              <span className="text-[13px] text-muted-foreground">{skill.enabled ? "Enabled" : "Disabled"}</span>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={copySlug} className="gap-2">
                <Copy className="h-4 w-4" />
                Copy slug
              </Button>
              <Button onClick={() => onTryInChat(skill)} className="gap-2 bg-primary text-primary-foreground hover:opacity-90">
                <Play className="h-4 w-4" />
                Try in chat
              </Button>
            </div>
          </div>
        ) : undefined
      }
    >
      {skill && (
        <Tabs defaultValue="overview" className="flex flex-col">
          <div className="sticky top-0 z-10 border-b border-border/60 bg-card/95 px-6 pt-4 pb-2 backdrop-blur">
            <TabsList className="h-9 w-auto justify-start gap-0.5 self-start rounded-lg border border-border/60 bg-secondary/30 p-1">
              <TabTrigger value="overview">Overview</TabTrigger>
              <TabTrigger value="content">Content</TabTrigger>
              <TabTrigger value="triggers">Triggers</TabTrigger>
            </TabsList>
          </div>

          <TabsContent value="overview" className="px-6 pt-3 pb-6">
            <OverviewTab skill={skill} onTryInChat={() => onTryInChat(skill)} />
          </TabsContent>
          <TabsContent value="content" className="px-6 pt-3 pb-6">
            <ContentTab markdown={markdownBody} />
          </TabsContent>
          <TabsContent value="triggers" className="px-6 pt-3 pb-6">
            <TriggersTab skill={skill} />
          </TabsContent>
        </Tabs>
      )}
    </DrawerShell>
  )
}

function TabTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <TabsTrigger value={value} className="h-7 rounded-md px-3 text-[13px] data-[state=active]:bg-secondary data-[state=active]:text-foreground">
      {children}
    </TabsTrigger>
  )
}

function OverviewTab({ skill, onTryInChat }: { skill: Skill; onTryInChat: () => void }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3.5">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <div>
            <p className="text-[13px] font-medium text-foreground">How the agent uses this skill</p>
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
              {skill.isKeywordTriggered
                ? "This skill auto-activates when the user message matches its keyword triggers. Enable/disable is saved to your agent profile's disabled_skills list."
                : "Call invoke_skill with this slug to load procedural HR knowledge. Toggle enabled state to include or exclude this skill from the agent (saved to the backend)."}
            </p>
            <Button size="sm" variant="secondary" className="mt-3 gap-2" onClick={onTryInChat}>
              <Play className="h-3.5 w-3.5" />
              Try in chat
            </Button>
          </div>
        </div>
      </div>

      {skill.keywords.length > 0 && (
        <PanelSection title="Keyword triggers">
          <div className="flex flex-wrap gap-1.5">
            {skill.keywords.map((k) => (
              <Tag key={k}>{k}</Tag>
            ))}
          </div>
        </PanelSection>
      )}

      <PanelSection title="Details">
        <div className="divide-y divide-border/50">
          <DetailRow label="Slug" value={<code className="font-mono text-[12px] text-sky-400">{skill.slug ?? skill.id}</code>} />
          <DetailRow label="Author" value={skill.author} />
          <DetailRow label="Category" value={skill.category} />
          <DetailRow label="Type" value={skill.skillType ?? "knowledge"} />
          <DetailRow label="Format" value={skill.isCatalog ? "AgentSkills (SKILL.md)" : "Custom"} />
          {skill.source && (
            <DetailRow
              label="Source"
              value={<span className="break-all font-mono text-[11px] text-muted-foreground">{skill.source}</span>}
            />
          )}
        </div>
      </PanelSection>
    </div>
  )
}

function ContentTab({ markdown }: { markdown: string }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-muted-foreground">
        <FileText className="h-4 w-4" />
        <span className="text-[13px] font-medium text-foreground">Skill guide</span>
      </div>
      <div className="prose prose-sm max-w-none rounded-xl border border-border/60 bg-secondary/20 px-5 py-4 prose-headings:font-heading prose-headings:text-foreground prose-p:text-muted-foreground prose-li:text-muted-foreground prose-strong:text-foreground prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:text-foreground">
        <ReactMarkdown>{markdown}</ReactMarkdown>
      </div>
    </div>
  )
}

function TriggersTab({ skill }: { skill: Skill }) {
  if (skill.keywords.length === 0) {
    return (
      <div className="rounded-xl border border-border/60 bg-secondary/20 px-5 py-8 text-center">
        <BookOpen className="mx-auto h-8 w-8 text-muted-foreground/60" />
        <p className="mt-3 text-sm font-medium text-foreground">Manual invocation</p>
        <p className="mt-1 text-[13px] text-muted-foreground">
          No keyword triggers. The agent loads this skill when you ask it to use{" "}
          <code className="font-mono text-sky-400">invoke_skill(&quot;{skill.slug ?? skill.id}&quot;)</code>.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[13px] text-muted-foreground">
        These phrases activate the skill automatically when they appear as whole tokens in the user message.
      </p>
      <div className="flex flex-col divide-y divide-border/50 overflow-hidden rounded-lg border border-border/60">
        {skill.keywords.map((kw) => (
          <div key={kw} className="flex items-center gap-3 bg-secondary/20 px-4 py-3">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span className="text-[13px] font-medium text-foreground">{kw}</span>
          </div>
        ))}
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3.5 py-3">
        <CircleDot className="mt-0.5 h-4 w-4 text-amber-400" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Only {skill.keywords.length} skills in this catalog use auto-trigger. Most HR skills are loaded on demand via invoke_skill.
        </p>
      </div>
    </div>
  )
}
