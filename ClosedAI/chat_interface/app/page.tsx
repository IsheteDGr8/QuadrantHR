"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { LandingPage } from "@/components/landing-page"
import { AUTH_TOKEN_KEY, captureAuthTokenFromUrl } from "@/lib/auth-profile"

/**
 * Public marketing landing. Authenticated users (or OAuth returns with
 * ?token=) go straight to Tasks (/intake).
 */
export default function Home() {
  const router = useRouter()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    try {
      captureAuthTokenFromUrl()
      if (localStorage.getItem(AUTH_TOKEN_KEY)) {
        try {
          localStorage.setItem("hr-copilot:nav-view", "intake")
        } catch {
          /* ignore */
        }
        router.replace("/intake")
        return
      }
    } finally {
      setReady(true)
    }
  }, [router])

  if (!ready) return null

  return <LandingPage />
}
