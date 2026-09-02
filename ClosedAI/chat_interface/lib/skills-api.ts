/** Client for skills catalog + agent-profile disabled_skills (enable/disable). */

export interface BackendSkillInfo {
  name: string
  type: 'repo' | 'knowledge' | 'agentskills'
  content: string
  triggers: string[]
  source: string | null
  description: string | null
  is_agentskills_format: boolean
  disable_model_invocation: boolean
}

export interface BackendSkillsResponse {
  skills: BackendSkillInfo[]
  sources: Record<string, number>
}

export interface AgentProfileListResponse {
  profiles: { id: string; name: string; agent_kind: string }[]
  active_agent_profile_id: string | null
}

export interface AgentProfileDetailResponse {
  name: string
  profile: Record<string, unknown> & { disabled_skills?: string[] }
}

async function parseJson<T>(res: Response): Promise<T> {
  const data = (await res.json().catch(() => null)) as T | { error?: string; detail?: string }
  if (!res.ok) {
    const msg =
      (data && typeof data === 'object' && 'error' in data && data.error) ||
      (data && typeof data === 'object' && 'detail' in data && String(data.detail)) ||
      res.statusText
    if (res.status === 502 || res.status === 503 || /fetch|ECONNREFUSED|network/i.test(String(msg))) {
      throw new Error('offline')
    }
    throw new Error(String(msg))
  }
  return data as T
}

export async function fetchCatalogSkills(): Promise<BackendSkillsResponse> {
  const res = await fetch('/api/skills', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      load_public: false,
      load_user: true,
      load_project: true,
      load_org: false,
    }),
  })

  const data = await parseJson<BackendSkillsResponse>(res)
  if (!data.skills || !Array.isArray(data.skills)) {
    throw new Error('Invalid skills response')
  }
  return data
}

export async function fetchAgentProfileState(): Promise<{
  profileName: string
  disabledSkills: string[]
}> {
  const listRes = await fetch('/api/agent-profiles')
  const list = await parseJson<AgentProfileListResponse>(listRes)

  if (list.profiles.length === 0) {
    return { profileName: 'default', disabledSkills: [] }
  }

  const active =
    list.profiles.find((p) => p.id === list.active_agent_profile_id) ?? list.profiles[0]

  const detailRes = await fetch(`/api/agent-profiles/${encodeURIComponent(active.name)}`)
  const detail = await parseJson<AgentProfileDetailResponse>(detailRes)

  return {
    profileName: detail.name,
    disabledSkills: Array.isArray(detail.profile.disabled_skills) ? detail.profile.disabled_skills : [],
  }
}

export async function saveDisabledSkills(profileName: string, disabledSkills: string[]): Promise<void> {
  const detailRes = await fetch(`/api/agent-profiles/${encodeURIComponent(profileName)}`)
  const detail = await parseJson<AgentProfileDetailResponse>(detailRes)

  const nextProfile = {
    ...detail.profile,
    disabled_skills: disabledSkills,
  }

  const saveRes = await fetch(`/api/agent-profiles/${encodeURIComponent(profileName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(nextProfile),
  })

  await parseJson<{ name: string; message: string }>(saveRes)
}

export async function setSkillEnabled(slug: string, enabled: boolean): Promise<string[]> {
  const { profileName, disabledSkills } = await fetchAgentProfileState()
  const set = new Set(disabledSkills)

  if (enabled) {
    set.delete(slug)
  } else {
    set.add(slug)
  }

  const next = Array.from(set).sort()
  await saveDisabledSkills(profileName, next)
  return next
}
