"use client"

import { useSyncExternalStore } from "react"

export const AUTH_TOKEN_KEY = "auth_token"
export const AUTH_PROFILE_KEY = "hr-copilot:auth-profile"

export type AuthProvider = "google" | "microsoft" | "local"

export type AuthProfile = {
  name: string
  email: string
  picture: string | null
  provider: AuthProvider
  needsSetup: boolean
}

type Listener = () => void

let cached: AuthProfile | null | undefined
const listeners = new Set<Listener>()

function notify() {
  cached = undefined
  for (const fn of listeners) fn()
}

function b64urlDecode(segment: string): string {
  const padded = segment.replace(/-/g, "+").replace(/_/g, "/")
  const pad = padded.length % 4 === 0 ? "" : "=".repeat(4 - (padded.length % 4))
  try {
    return decodeURIComponent(
      atob(padded + pad)
        .split("")
        .map((c) => `%${c.charCodeAt(0).toString(16).padStart(2, "0")}`)
        .join(""),
    )
  } catch {
    try {
      return atob(padded + pad)
    } catch {
      return ""
    }
  }
}

export function parseJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".")
  if (parts.length < 2) return null
  try {
    const json = b64urlDecode(parts[1])
    const parsed = JSON.parse(json) as unknown
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null
  } catch {
    return null
  }
}

function readStoredProfile(): AuthProfile | null {
  if (typeof window === "undefined") return null
  try {
    const raw = localStorage.getItem(AUTH_PROFILE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<AuthProfile>
    if (!parsed || typeof parsed !== "object") return null
    const name = typeof parsed.name === "string" ? parsed.name.trim() : ""
    const email = typeof parsed.email === "string" ? parsed.email.trim() : ""
    return {
      name,
      email,
      picture: typeof parsed.picture === "string" && parsed.picture ? parsed.picture : null,
      provider:
        parsed.provider === "google" || parsed.provider === "microsoft" ? parsed.provider : "local",
      needsSetup: Boolean(parsed.needsSetup) || !name,
    }
  } catch {
    return null
  }
}

function writeStoredProfile(profile: AuthProfile | null) {
  if (typeof window === "undefined") return
  if (!profile) {
    localStorage.removeItem(AUTH_PROFILE_KEY)
  } else {
    localStorage.setItem(AUTH_PROFILE_KEY, JSON.stringify(profile))
  }
  notify()
}

function profileFromGoogleToken(token: string): AuthProfile | null {
  const payload = parseJwtPayload(token)
  if (!payload) return null
  const email = typeof payload.email === "string" ? payload.email : ""
  const name =
    (typeof payload.name === "string" && payload.name.trim()) ||
    (typeof payload.given_name === "string" && payload.given_name.trim()) ||
    ""
  if (!name && !email) return null
  const picture = typeof payload.picture === "string" && payload.picture ? payload.picture : null
  return {
    name,
    email,
    picture,
    provider: "google",
    // If Google somehow didn't return a name, fall back to the setup step
    // rather than showing a generic label.
    needsSetup: !name,
  }
}

export function captureAuthTokenFromUrl(): string | null {
  if (typeof window === "undefined") return null
  const url = new URL(window.location.href)
  const token = url.searchParams.get("token")
  if (!token) return null
  localStorage.setItem(AUTH_TOKEN_KEY, token)
  const google = profileFromGoogleToken(token)
  if (google) writeStoredProfile(google)
  url.searchParams.delete("token")
  const clean = url.pathname + (url.search ? url.search : "") + url.hash
  window.history.replaceState({}, "", clean)
  return token
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(AUTH_TOKEN_KEY)
}

export function getAuthProfile(): AuthProfile | null {
  if (cached !== undefined) return cached
  const stored = readStoredProfile()
  if (stored) {
    cached = stored
    return stored
  }
  const token = getAuthToken()
  if (token && token !== "mock-jwt-token") {
    const google = profileFromGoogleToken(token)
    if (google) {
      writeStoredProfile(google)
      cached = google
      return google
    }
  }
  cached = stored
  return stored
}

export function signInLocal(input: { hrId: string; name?: string; email?: string }) {
  const hrId = input.hrId.trim()
  const name = (input.name || "").trim()
  const email = (input.email || "").trim()
  const profile: AuthProfile = {
    // Local sign-in never trusts the HR ID as a display name — the profile
    // setup step must collect a real name so the app never shows "Employee".
    name: name || "",
    email: email || (hrId.includes("@") ? hrId : ""),
    picture: null,
    provider: "local",
    needsSetup: !name,
  }
  localStorage.setItem(AUTH_TOKEN_KEY, `local:${hrId || "employee"}`)
  writeStoredProfile(profile)
  try {
    localStorage.setItem("hr-copilot:nav-view", "intake")
  } catch {
    /* ignore */
  }
}

export function applyMicrosoftLogin(input: {
  idToken: string
  name?: string
  email?: string
  picture?: string | null
}) {
  const name = (input.name || "").trim()
  const email = (input.email || "").trim()
  const profile: AuthProfile = {
    name,
    email,
    picture: input.picture ?? null,
    provider: "microsoft",
    // Entra almost always returns a display name; if it somehow doesn't,
    // route to setup rather than showing a generic label.
    needsSetup: !name,
  }
  if (typeof window !== "undefined") {
    localStorage.setItem(AUTH_TOKEN_KEY, input.idToken)
    try {
      localStorage.setItem("hr-copilot:nav-view", "intake")
    } catch {
      /* ignore */
    }
  }
  writeStoredProfile(profile)
}

export function completeLocalSetup(input: { name: string; email?: string }) {
  const current = getAuthProfile()
  const name = input.name.trim()
  if (!name) return
  const next: AuthProfile = {
    name,
    email: (input.email || "").trim() || current?.email || "",
    picture: current?.picture ?? null,
    provider: current?.provider ?? "local",
    needsSetup: false,
  }
  writeStoredProfile(next)
}

export function updateAuthProfile(patch: Partial<Pick<AuthProfile, "name" | "email" | "picture">>) {
  const current = getAuthProfile()
  if (!current) return
  const name = patch.name !== undefined ? patch.name.trim() : current.name
  const next: AuthProfile = {
    ...current,
    name: name || current.name,
    email: patch.email !== undefined ? patch.email.trim() : current.email,
    picture: patch.picture !== undefined ? patch.picture : current.picture,
    needsSetup: !name,
  }
  writeStoredProfile(next)
}

export function signOut() {
  if (typeof window === "undefined") return
  localStorage.removeItem(AUTH_TOKEN_KEY)
  localStorage.removeItem(AUTH_PROFILE_KEY)
  notify()
  window.location.assign("/")
}

function subscribe(listener: Listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): AuthProfile | null {
  return getAuthProfile()
}

function getServerSnapshot(): AuthProfile | null {
  return null
}

export function useAuthProfile(): AuthProfile | null {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}

export function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "U"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}
