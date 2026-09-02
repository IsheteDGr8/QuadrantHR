import type { BackendSkillInfo } from '@/lib/skills-api'
import { defaultPermissions } from './skill-data'
import type { Skill, TriggerType } from './skill-types'

export const HR_CATEGORIES = [
  'All',
  'AI & Governance',
  'Talent Acquisition',
  'Employee Lifecycle',
  'Performance & Learning',
  'Compensation & Benefits',
  'Analytics & Intelligence',
  'Org & Workforce',
  'Employee Experience',
  'HR Operations',
  'Global & M&A',
  'HR Technology',
] as const

export type HRCategory = (typeof HR_CATEGORIES)[number]

const CATEGORY_RULES: { category: HRCategory; patterns: RegExp[] }[] = [
  {
    category: 'AI & Governance',
    patterns: [/^hr-ai/, /^hr-genai/, /^hr-agentic/, /^hr-prompt-engineering/, /^hr-chatbot-design/],
  },
  {
    category: 'Talent Acquisition',
    patterns: [
      /^hr-talent-acquisition/,
      /^hr-talent-crm/,
      /^hr-talent-mapping/,
      /^hr-talent-supply/,
      /^hr-recruit/,
      /^hr-candidate/,
      /^hr-interviewing/,
      /^hr-offer/,
      /^hr-reference/,
      /^hr-executive-search/,
      /^hr-retained-search/,
      /^hr-search-strategy/,
      /^hr-market-mapping/,
      /^hr-passive-candidate/,
      /^hr-social-recruiting/,
      /^hr-employer-branding/,
      /^hr-executive-assessment/,
    ],
  },
  {
    category: 'Employee Lifecycle',
    patterns: [/^hr-onboarding/, /^hr-offboarding/, /^hr-employee-transfer/, /^hr-employee-lifecycle/, /^hr-internal-mobility/, /^hr-immigration/, /^hr-pto/],
  },
  {
    category: 'Performance & Learning',
    patterns: [
      /^hr-performance/,
      /^hr-coaching/,
      /^hr-leadership/,
      /^hr-learning/,
      /^hr-training/,
      /^hr-career/,
      /^hr-succession/,
      /^hr-competency/,
      /^hr-manager-effectiveness/,
    ],
  },
  {
    category: 'Compensation & Benefits',
    patterns: [/^hr-compensation/, /^hr-total-rewards/, /^hr-payroll/, /^hr-retirement/, /^hr-salary-benchmarking/, /^hr-people-budgeting/, /^hr-time-attendance/],
  },
  {
    category: 'Analytics & Intelligence',
    patterns: [
      /^hr-analytics/,
      /^hr-data$/,
      /^hr-kpi/,
      /^hr-predictive/,
      /^hr-workforce-intelligence/,
      /^hr-talent-intelligence/,
      /^hr-skills-intelligence/,
      /^hr-workforce-forecasting/,
      /^hr-workforce-economics/,
      /^hr-workforce-scenario/,
    ],
  },
  {
    category: 'Org & Workforce',
    patterns: [
      /^hr-workforce-planning/,
      /^hr-workforce-capability/,
      /^hr-workforce-transformation/,
      /^hr-workforce-scheduling/,
      /^hr-strategic-workforce/,
      /^hr-demand-planning/,
      /^hr-organizational/,
      /^hr-organization-/,
      /^hr-operating-model/,
      /^hr-job-/,
      /^hr-talent-management/,
    ],
  },
  {
    category: 'Employee Experience',
    patterns: [
      /^hr-employee-experience/,
      /^hr-employee-engagement/,
      /^hr-employee-listening/,
      /^hr-employee-communications/,
      /^hr-employee-journey/,
      /^hr-employee-self-service/,
      /^hr-wellbeing/,
      /^hr-culture/,
      /^hr-diversity/,
      /^hr-recognition/,
      /^hr-accessibility/,
    ],
  },
  {
    category: 'Global & M&A',
    patterns: [/^hr-global/, /^hr-ma-/, /^hr-mergers/, /^hr-post-merger/, /^hr-vietnam/],
  },
  {
    category: 'HR Technology',
    patterns: [
      /^hr-backend/,
      /^hr-frontend/,
      /^hr-fullstack/,
      /^hr-devops/,
      /^hr-cloud/,
      /^hr-software-architecture/,
      /^hr-system-/,
      /^hr-technology/,
      /^hr-digital-hr/,
      /^hr-automation/,
      /^hr-embedded/,
      /^hr-mobile/,
      /^hr-iot/,
      /^hr-blockchain/,
      /^hr-ar-vr/,
      /^hr-game-development/,
      /^hr-uiux/,
      /^hr-qa/,
      /^hr-security/,
      /^hr-hris/,
    ],
  },
  {
    category: 'HR Operations',
    patterns: [
      /^hr-people-operations/,
      /^hr-ticketing/,
      /^hr-policy/,
      /^hr-compliance/,
      /^hr-audit/,
      /^hr-vendor/,
      /^hr-shared-services/,
      /^hr-service-delivery/,
      /^hr-coordination/,
      /^hr-project-management/,
      /^hr-change-/,
      /^hr-crisis/,
      /^hr-risk/,
      /^hr-labor-relations/,
      /^hr-employee-relations/,
      /^hr-conflict/,
      /^hr-contingent/,
      /^hr-business-partner/,
      /^hr-consulting/,
      /^hr-management/,
      /^hr-people-leadership/,
      /^hr-strategic-planning/,
      /^hr-future-of-work/,
      /^hr-design-thinking/,
      /^hr-skills-taxonomy/,
      /^hr-skills-management/,
      /^hr-knowledge-management/,
    ],
  },
]

export function inferCategory(slug: string): HRCategory {
  for (const { category, patterns } of CATEGORY_RULES) {
    if (patterns.some((p) => p.test(slug))) return category
  }
  if (slug.startsWith('hr-')) return 'HR Operations'
  return 'HR Operations'
}

export function formatSkillTitle(slug: string): string {
  const base = slug.replace(/^hr-/, '').split('-').filter(Boolean)
  return base.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

interface ParsedFrontmatter {
  version?: string
  author?: string
  owner?: string
  maturity?: string
}

export function parseFrontmatter(content: string): ParsedFrontmatter {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/)
  if (!match) return {}

  const meta: ParsedFrontmatter = {}
  for (const line of match[1].split('\n')) {
    const m = line.match(/^([a-z_]+):\s*"?(.+?)"?\s*$/i)
    if (!m) continue
    const key = m[1].toLowerCase()
    const val = m[2].replace(/^["']|["']$/g, '').trim()
    if (key === 'version') meta.version = val
    if (key === 'author') meta.author = val
    if (key === 'owner') meta.owner = val
    if (key === 'maturity') meta.maturity = val
  }
  return meta
}

export function stripFrontmatter(content: string): string {
  return content.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '').trim()
}

function triggerType(triggers: string[]): TriggerType {
  if (triggers.length > 0) return 'Keyword'
  return 'Manual'
}

export function mapBackendSkill(info: BackendSkillInfo, disabledSlugs: Set<string>): Skill {
  const meta = parseFrontmatter(info.content)
  const hasTriggers = info.triggers.length > 0
  const slug = info.name

  return {
    id: slug,
    name: formatSkillTitle(slug),
    slug,
    description: info.description?.trim() || 'HR domain knowledge for the agent.',
    category: inferCategory(slug),
    scope: 'global',
    triggerType: triggerType(info.triggers),
    keywords: [...info.triggers],
    enabled: !disabledSlugs.has(slug),
    version: meta.version ?? '1.0.0',
    author: meta.author ?? meta.owner ?? 'HR skills pack',
    maturity: meta.maturity,
    requiredTools: [],
    instructions: stripFrontmatter(info.content),
    contentMarkdown: info.content,
    variables: [],
    added: 'Catalog',
    lastUsed: '—',
    lastUsedTs: 0,
    runCount: 0,
    successRate: 100,
    avgDurationMs: 0,
    errors24h: 0,
    permissions: defaultPermissions(),
    activity: [],
    isCatalog: true,
    skillType: info.type,
    source: info.source ?? undefined,
    isKeywordTriggered: hasTriggers,
  }
}

export function isHrSkill(slug: string): boolean {
  return slug.startsWith('hr-')
}

export function buildTryInChatPrompt(skill: Skill): string {
  const slug = skill.slug ?? skill.id
  return `Call invoke_skill("${slug}") first, then help me with a typical ${skill.name.toLowerCase()} task using that skill's guidance.`
}

/** Group skills by HR category for sectioned layouts. */
export function groupSkillsByCategory(skills: Skill[]): { category: HRCategory; skills: Skill[] }[] {
  const order = HR_CATEGORIES.filter((c) => c !== 'All') as HRCategory[]
  const buckets = new Map<HRCategory, Skill[]>()
  for (const cat of order) buckets.set(cat, [])
  for (const skill of skills) {
    const cat = (HR_CATEGORIES.includes(skill.category as HRCategory) ? skill.category : 'HR Operations') as HRCategory
    if (cat === 'All') continue
    const list = buckets.get(cat) ?? []
    list.push(skill)
    buckets.set(cat, list)
  }
  return order
    .map((category) => ({ category, skills: (buckets.get(category) ?? []).sort((a, b) => a.name.localeCompare(b.name)) }))
    .filter((g) => g.skills.length > 0)
}
