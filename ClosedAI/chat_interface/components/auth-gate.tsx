"use client"

import { useEffect, useState, type ReactNode } from "react"
import { Login } from "@/components/pages/Login"
import { ProfileSetup } from "@/components/profile-setup"
import {
  AUTH_TOKEN_KEY,
  captureAuthTokenFromUrl,
  useAuthProfile,
} from "@/lib/auth-profile"

export function AuthGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [token, setToken] = useState<string | null>(null)
  const profile = useAuthProfile()

  useEffect(() => {
    try {
      captureAuthTokenFromUrl()
      setToken(localStorage.getItem(AUTH_TOKEN_KEY))
    } finally {
      setReady(true)
    }
  }, [])

  if (!ready) return null
  if (!token) return <Login />
  // A token with no usable profile (or an unfinished one) must set a name
  // before entering the app — never fall through to a generic "Employee".
  if (!profile || profile.needsSetup || !profile.name.trim()) return <ProfileSetup />
  return <>{children}</>
}
