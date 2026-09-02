import type { LucideIcon } from "lucide-react"

export type SkillScope = "global" | "workspace" | "agent"
export type TriggerType = "Trigger-based" | "Always active" | "Keyword" | "Manual"
export type ActivityStatus = "success" | "error" | "warning" | "info"

export interface SkillPermissionFlags {
  requireConfirmation: boolean
  allowFileWrite: boolean
  allowNetwork: boolean
  allowDbMutations: boolean
  allowShellCommands: boolean
}

export interface ToolOverride {
  tool: string
  allowed: boolean
  requiresConfirmation: boolean
}

export interface SkillPermissions {
  flags: SkillPermissionFlags
  toolOverrides: Record<string, ToolOverride>
}

export interface SkillVariable {
  key: string
  label: string
  description: string
  required: boolean
}

export interface SkillActivity {
  id: string
  action: string
  detail: string
  time: string
  ts: number
  status: ActivityStatus
}

export interface Skill {
  id: string
  /** Display title derived from slug */
  name: string
  /** Backend skill id, e.g. hr-onboarding */
  slug?: string
  description: string
  category: string
  scope: SkillScope
  triggerType: TriggerType
  keywords: string[]
  enabled: boolean
  version: string
  author: string
  maturity?: string
  requiredTools: string[]
  instructions: string
  /** Full markdown from backend (includes frontmatter) */
  contentMarkdown?: string
  variables: SkillVariable[]
  added: string
  lastUsed: string
  lastUsedTs: number
  runCount: number
  successRate: number
  avgDurationMs: number
  errors24h: number
  permissions: SkillPermissions
  activity: SkillActivity[]
  /** Loaded from HRAgent backend catalog (read-only) */
  isCatalog?: boolean
  skillType?: 'repo' | 'knowledge' | 'agentskills'
  source?: string
  isKeywordTriggered?: boolean
}

export interface SkillTemplate {
  id: string
  name: string
  description: string
  category: string
  triggerType: TriggerType
  instructions: string
  requiredTools: string[]
  variables: SkillVariable[]
  icon: LucideIcon
}

export const CATEGORIES = ["Engineering", "Productivity", "Research", "Communication", "Data", "Custom"]
export const CATEGORY_FILTERS = ["All categories", ...CATEGORIES]
export const SCOPE_FILTERS = ["All scopes", "global", "workspace", "agent"]
export const TRIGGER_FILTERS = ["All triggers", "Trigger-based", "Always active", "Keyword", "Manual"]
export const STATUS_FILTERS = ["All", "Enabled", "Disabled"]
export const SORT_OPTIONS = ["Name", "Runs", "Success rate", "Errors (24h)", "Last used"]

export const SCOPE_META: Record<SkillScope, { label: string; className: string }> = {
  global: { label: "Global", className: "text-navy" },
  workspace: { label: "Workspace", className: "text-warning" },
  agent: { label: "Agent", className: "text-violet-400" },
}
