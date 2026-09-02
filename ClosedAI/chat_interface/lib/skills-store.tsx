"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { toast } from "sonner"
import { defaultPermissions, todayLabel, uid } from "@/components/pages/skills/skill-data"
import { isHrSkill, mapBackendSkill } from "@/components/pages/skills/skill-catalog"
import type { Skill, SkillPermissionFlags, SkillPermissions, SkillTemplate } from "@/components/pages/skills/skill-types"
import { fetchAgentProfileState, fetchCatalogSkills, setSkillEnabled } from "@/lib/skills-api"

export type SkillsDataSource = "loading" | "live" | "error" | "empty"

interface SkillsContextValue {
  skills: Skill[]
  dataSource: SkillsDataSource
  loadError: string | null
  sourceCounts: Record<string, number>
  togglingId: string | null
  refresh: () => Promise<void>
  toggleSkill: (id: string) => Promise<void>
  enableSkill: (id: string) => Promise<void>
  deleteSkill: (id: string) => void
  duplicateSkill: (skill: Skill) => void
  saveSkill: (skill: Skill) => void
  saveInstructions: (id: string, instructions: string) => void
  savePermissions: (id: string, perms: SkillPermissions) => void
  runCompleted: (skill: Skill, ok: boolean) => void
  installTemplate: (tpl: SkillTemplate, config?: { flags?: SkillPermissionFlags }) => void
}

const SkillsContext = createContext<SkillsContextValue | null>(null)

export function SkillsProvider({ children }: { children: ReactNode }) {
  const [skills, setSkills] = useState<Skill[]>([])
  const [dataSource, setDataSource] = useState<SkillsDataSource>("loading")
  const [loadError, setLoadError] = useState<string | null>(null)
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({})
  const [togglingId, setTogglingId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setDataSource("loading")
    setLoadError(null)
    try {
      const [catalog, profile] = await Promise.all([fetchCatalogSkills(), fetchAgentProfileState()])
      const disabled = new Set(profile.disabledSkills)
      const mapped = catalog.skills
        .filter((s) => isHrSkill(s.name))
        .map((s) => mapBackendSkill(s, disabled))
        .sort((a, b) => a.name.localeCompare(b.name))

      setSkills(mapped)
      setSourceCounts(catalog.sources ?? {})
      setDataSource(mapped.length > 0 ? "live" : "empty")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load skills"
      setLoadError(msg === "offline" ? "HR Agent backend is unavailable. Start the server on port 8001." : msg)
      setDataSource("error")
      setSkills([])
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const patchSkill = (id: string, fn: (s: Skill) => Skill) =>
    setSkills((prev) => prev.map((s) => (s.id === id ? fn(s) : s)))

  const applyEnabledState = (disabledSlugs: string[]) => {
    const disabled = new Set(disabledSlugs)
    setSkills((prev) => prev.map((s) => ({ ...s, enabled: !disabled.has(s.slug ?? s.id) })))
  }

  const toggleSkill = async (id: string) => {
    const skill = skills.find((s) => s.id === id)
    if (!skill || togglingId) return

    const slug = skill.slug ?? skill.id
    const nextEnabled = !skill.enabled
    setTogglingId(id)
    patchSkill(id, (s) => ({ ...s, enabled: nextEnabled }))

    try {
      const disabled = await setSkillEnabled(slug, nextEnabled)
      applyEnabledState(disabled)
      toast(nextEnabled ? `${skill.name} enabled` : `${skill.name} disabled`)
    } catch (err) {
      patchSkill(id, (s) => ({ ...s, enabled: skill.enabled }))
      toast.error(err instanceof Error ? err.message : "Failed to update skill")
    } finally {
      setTogglingId(null)
    }
  }

  const enableSkill = async (id: string) => {
    const skill = skills.find((s) => s.id === id)
    if (!skill) return
    if (skill.enabled) {
      toast.info(`${skill.name} is already enabled`)
      return
    }
    await toggleSkill(id)
  }

  const deleteSkill = (id: string) => {
    toast.error("Disable a skill instead — catalog skills stay installed in ~/.HRAgent/skills")
  }

  const duplicateSkill = (skill: Skill) => {
    toast.info("Catalog skills are managed from the HR skills pack")
  }

  const saveSkill = (skill: Skill) => {
    toast.info("Catalog skill metadata is read-only")
  }

  const saveInstructions = (_id: string, _instructions: string) => {
    toast.info("Catalog skill instructions are read-only")
  }

  const savePermissions = (_id: string, _perms: SkillPermissions) => {
    toast.info("Catalog skill permissions are read-only")
  }

  const runCompleted = (skill: Skill, ok: boolean) => {
    patchSkill(skill.id, (s) => ({
      ...s,
      runCount: s.runCount + 1,
      lastUsed: "just now",
      lastUsedTs: Date.now(),
      activity: [
        {
          id: `a-${uid()}`,
          action: ok ? "Ran skill" : "Run failed",
          detail: ok ? "Executed via test preview" : "Test run failed",
          time: "just now",
          ts: Date.now(),
          status: ok ? ("success" as const) : ("error" as const),
        },
        ...s.activity,
      ],
    }))
    if (ok) toast.success(`${skill.name} run completed`)
    else toast.error(`${skill.name} run failed`)
  }

  const installTemplate = (tpl: SkillTemplate, config?: { flags?: SkillPermissionFlags }) => {
    toast.info(`Use the Skills page to enable "${tpl.name}" from the HR catalog`)
  }

  const value = useMemo<SkillsContextValue>(
    () => ({
      skills,
      dataSource,
      loadError,
      sourceCounts,
      togglingId,
      refresh,
      toggleSkill,
      enableSkill,
      deleteSkill,
      duplicateSkill,
      saveSkill,
      saveInstructions,
      savePermissions,
      runCompleted,
      installTemplate,
    }),
    [skills, dataSource, loadError, sourceCounts, togglingId, refresh],
  )

  return <SkillsContext.Provider value={value}>{children}</SkillsContext.Provider>
}

export function useSkills() {
  const ctx = useContext(SkillsContext)
  if (!ctx) throw new Error("useSkills must be used within a SkillsProvider")
  return ctx
}
