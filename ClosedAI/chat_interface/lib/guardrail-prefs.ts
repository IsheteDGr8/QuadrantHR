"use client"

/**
 * Client-side guardrail preferences (Settings → Tool Permissions / Security).
 * Applied when creating a new HR Agent conversation via POST /api/chat.
 */

export type GuardrailPrefs = {
  /** Skip ConfirmRisky (dangerous). Default false. */
  autoApprove: boolean
  /** Prefer blocking mutating tools via policy + prompt. Default false for Vera demos. */
  readOnly: boolean
  /** Keep PII masking on in UI (always on server WS). Default true. */
  piiRedaction: boolean
}

const KEY = "hr-copilot:guardrail-prefs:v1"

const DEFAULTS: GuardrailPrefs = {
  autoApprove: false,
  readOnly: false,
  piiRedaction: true,
}

export function loadGuardrailPrefs(): GuardrailPrefs {
  if (typeof window === "undefined") return { ...DEFAULTS }
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw) as Partial<GuardrailPrefs>
    return {
      autoApprove: Boolean(parsed.autoApprove),
      readOnly: Boolean(parsed.readOnly),
      piiRedaction: parsed.piiRedaction !== false,
    }
  } catch {
    return { ...DEFAULTS }
  }
}

export function saveGuardrailPrefs(prefs: Partial<GuardrailPrefs>) {
  if (typeof window === "undefined") return
  const next = { ...loadGuardrailPrefs(), ...prefs }
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* ignore */
  }
  return next
}
