"use client"

import { useState } from "react"
import { UserRound } from "lucide-react"
import { completeLocalSetup, useAuthProfile } from "@/lib/auth-profile"

export function ProfileSetup() {
  const profile = useAuthProfile()
  const [name, setName] = useState(profile?.name && profile.name !== "Employee" ? profile.name : "")
  const [email, setEmail] = useState(profile?.email || "")
  const [error, setError] = useState("")

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError("Enter the name you want shown in the app.")
      return
    }
    completeLocalSetup({ name, email })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F8F4E9] px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-stone-200 bg-white p-8 shadow-[0_24px_60px_-28px_rgba(20,30,45,0.35)]"
      >
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-[#1F4E79]/10 text-[#1F4E79]">
          <UserRound className="h-6 w-6" />
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#1F4E79]">Almost there</p>
        <h1 className="mt-1 font-[family-name:var(--font-heading)] text-2xl font-semibold tracking-tight text-stone-900">
          Set up your profile
        </h1>
        <p className="mt-2 text-sm text-stone-500">
          Google sign-in fills this automatically. For HR ID / local access, add a display name so the sidebar and settings show you — not a generic Employee.
        </p>

        <label className="mt-6 block text-xs font-semibold text-stone-600">Display name</label>
        <input
          className="mt-1.5 w-full rounded-lg border border-stone-200 bg-[#FBFCFE] px-3 py-2.5 text-sm text-stone-900 outline-none focus:border-[#1F4E79]"
          placeholder="e.g. Priya Nair"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
          autoFocus
        />

        <label className="mt-4 block text-xs font-semibold text-stone-600">Work email (optional)</label>
        <input
          className="mt-1.5 w-full rounded-lg border border-stone-200 bg-[#FBFCFE] px-3 py-2.5 text-sm text-stone-900 outline-none focus:border-[#1F4E79]"
          placeholder="you@closedai.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          type="email"
        />

        {error && <p className="mt-3 text-xs font-medium text-rose-600">{error}</p>}

        <button
          type="submit"
          className="mt-6 w-full rounded-lg bg-[#0f1c2e] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#16233A]"
        >
          Continue
        </button>
      </form>
    </div>
  )
}
