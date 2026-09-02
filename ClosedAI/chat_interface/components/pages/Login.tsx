"use client"

import React, { useEffect, useState } from "react"
import { Lock, Eye, EyeOff, ArrowRight, ShieldCheck, Check } from "lucide-react"
import { signInLocal } from "@/lib/auth-profile"
import { isEntraConfigured, signInWithEntra } from "@/lib/entra"

// Same-origin Next.js route — no separate :8000 auth backend required.
const GOOGLE_LOGIN_URL = "/api/auth/google/login"

function MicrosoftIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 21 21" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  )
}

function GoogleIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

const TRUST_POINTS = [
  "Answers grounded in your company's verified policies",
  "Enterprise SSO with Microsoft Entra ID & Google Workspace",
  "Every sensitive action gated behind human approval",
]

export function Login() {
  const [hrId, setHrId] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [msLoading, setMsLoading] = useState(false)
  const [error, setError] = useState("")
  const entraEnabled = isEntraConfigured()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const authError = params.get("auth_error")
    if (authError) {
      setError(`Sign-in failed (${authError}). Try again, or use an HR ID below.`)
    }
  }, [])

  function handleGoogleLogin() {
    setLoading(true)
    window.location.href = GOOGLE_LOGIN_URL
  }

  async function handleMicrosoftLogin() {
    setError("")
    setMsLoading(true)
    try {
      await signInWithEntra()
      window.location.assign("/intake")
    } catch (err) {
      const message = err instanceof Error ? err.message : "Microsoft sign-in failed."
      // MSAL throws a user-cancelled error when the popup is closed; keep that quiet.
      if (!/user_cancelled|popup_window_error|interaction_in_progress/i.test(message)) {
        setError(message)
      }
      setMsLoading(false)
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    if (!hrId.trim() || !password.trim()) {
      setError("Enter your HR ID and password to continue.")
      return
    }
    signInLocal({ hrId })
    window.location.assign("/intake")
  }

  return (
    <div className="flex min-h-screen bg-[#0f1c2e] font-[family-name:var(--font-body)]">
      {/* Brand panel */}
      <aside className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-[#0f1c2e] p-12 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.6]"
          style={{
            backgroundImage:
              "radial-gradient(60% 50% at 20% 0%, rgba(45,106,159,0.22), transparent 70%), radial-gradient(50% 45% at 100% 100%, rgba(31,78,121,0.28), transparent 72%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />

        <div className="relative z-10 flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/25 bg-white/10 text-sm font-bold text-white">
            C
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-white">
            ClosedAI <span className="font-normal text-white/55">HR Copilot</span>
          </span>
        </div>

        <div className="relative z-10 max-w-md">
          <h1 className="font-[family-name:var(--font-heading)] text-[34px] font-semibold leading-[1.15] tracking-tight text-white">
            HR answers your team can trust.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-white/70">
            Sign in to ask about policies, leave balances, benefits, and onboarding — grounded in your company's real data, not guesswork.
          </p>
          <ul className="mt-8 space-y-3">
            {TRUST_POINTS.map((point) => (
              <li key={point} className="flex items-start gap-3 text-[13.5px] text-white/80">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10 text-white">
                  <Check className="h-3 w-3" />
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative z-10 flex items-center gap-2 text-[12px] text-white/50">
          <ShieldCheck className="h-4 w-4" />
          Secured with Microsoft Entra ID &amp; Google Workspace SSO
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex flex-1 items-center justify-center bg-[#f7f6f2] px-6 py-12">
        <div className="w-full max-w-[380px]">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#0f1c2e] text-sm font-bold text-white">
                C
              </div>
              <span className="text-[15px] font-semibold tracking-tight text-[#0f1c2e]">ClosedAI HR Copilot</span>
            </div>
          </div>

          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#1F4E79]">Welcome back</p>
          <h2 className="mt-1.5 font-[family-name:var(--font-heading)] text-[26px] font-semibold tracking-tight text-[#16233A]">
            Sign in to continue
          </h2>
          <p className="mt-2 text-[13.5px] text-[#5B6B7C]">
            Use your Google Workspace account for the fastest access.
          </p>

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={loading}
            className="mt-7 flex w-full items-center justify-center gap-2.5 rounded-xl border border-[#dfe3e8] bg-white py-3 text-[14px] font-semibold text-[#16233A] shadow-sm transition-colors hover:bg-[#fafbfc] disabled:opacity-60"
          >
            <GoogleIcon size={18} />
            Continue with Google
          </button>

          <button
            type="button"
            onClick={handleMicrosoftLogin}
            disabled={msLoading || !entraEnabled}
            title={entraEnabled ? undefined : "Set NEXT_PUBLIC_ENTRA_CLIENT_ID to enable Microsoft sign-in"}
            className="mt-3 flex w-full items-center justify-center gap-2.5 rounded-xl border border-[#dfe3e8] bg-white py-3 text-[14px] font-semibold text-[#16233A] shadow-sm transition-colors hover:bg-[#fafbfc] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <MicrosoftIcon size={18} />
            {msLoading ? "Opening Microsoft…" : "Continue with Microsoft"}
          </button>

          <div className="my-6 flex items-center gap-3">
            <span className="h-px flex-1 bg-[#e5e2da]" />
            <span className="text-[11px] font-medium uppercase tracking-wide text-[#9aa5b1]">or use HR ID</span>
            <span className="h-px flex-1 bg-[#e5e2da]" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-[12px] font-semibold text-[#374559]">HR ID</label>
              <input
                className="w-full rounded-xl border border-[#dfe3e8] bg-white px-3.5 py-2.5 text-[14px] text-[#16233A] outline-none transition-colors focus:border-[#1F4E79] focus:ring-2 focus:ring-[#1F4E79]/15"
                placeholder="e.g. CAI-04821"
                value={hrId}
                onChange={(e) => setHrId(e.target.value)}
                autoComplete="username"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-[12px] font-semibold text-[#374559]">Password</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9aa5b1]" />
                <input
                  className="w-full rounded-xl border border-[#dfe3e8] bg-white px-3.5 py-2.5 pl-10 pr-10 text-[14px] text-[#16233A] outline-none transition-colors focus:border-[#1F4E79] focus:ring-2 focus:ring-[#1F4E79]/15"
                  type={showPw ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9aa5b1] transition-colors hover:text-[#5B6B7C]"
                  aria-label={showPw ? "Hide password" : "Show password"}
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-[12.5px] font-medium text-rose-700">{error}</p>
            )}

            <button
              type="submit"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#0f1c2e] py-3 text-[14px] font-semibold text-white transition-colors hover:bg-[#16233A]"
            >
              Sign in <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          <p className="mt-6 text-center text-[12px] text-[#9aa5b1]">
            Trouble signing in? Contact your <span className="font-semibold text-[#1F4E79]">IT Helpdesk</span>.
          </p>
        </div>
      </main>
    </div>
  )
}
