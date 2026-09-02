/** Keyword-triggered skills mirrored from the backend (skills/skill.py). Only
 *  skills with YAML `triggers:` auto-inject on the server; the UI uses the same
 *  whole-token matching so the activity panel shows activations immediately. */

export interface KeywordSkillTrigger {
  name: string
  keywords: string[]
}

/** Skills with keyword triggers (mirrored from skill YAML `triggers:`). */
export const KEYWORD_SKILL_TRIGGERS: KeywordSkillTrigger[] = [
  {
    name: 'hr-onboarding',
    keywords: [
      'onboard',
      'onboarding',
      'new hire',
      'new employee',
      'onboarding checklist',
      'set up new employee',
    ],
  },
  {
    name: 'hr-ticketing',
    keywords: [
      'ticket',
      'ticketing',
      'helpdesk',
      'intake',
      'case management',
      'escalate ticket',
      'HR request',
      'triage',
    ],
  },
]

/** Whole-token, case-insensitive match — same rules as backend `_keyword_matches`. */
function keywordMatches(keyword: string, messageLower: string): boolean {
  const kw = keyword.toLowerCase().trim()
  if (!kw) return false
  const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(?<![a-z0-9])${escaped}(?![a-z0-9])`, 'i').test(messageLower)
}

/** Return skill names whose keyword triggers match the user message. */
export function matchKeywordSkills(text: string): string[] {
  const lower = text.toLowerCase()
  const matched: string[] = []
  for (const { name, keywords } of KEYWORD_SKILL_TRIGGERS) {
    if (keywords.some((kw) => keywordMatches(kw, lower))) matched.push(name)
  }
  return matched
}
