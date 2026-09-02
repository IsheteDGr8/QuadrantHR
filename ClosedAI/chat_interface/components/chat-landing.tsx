"use client"

import Image from "next/image"
import { useState, useEffect } from "react"
import { ClipboardCheck, Mail, UserPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ChatComposer } from "@/components/chat-composer"

const QUICK_ACTIONS = [
  {
    icon: ClipboardCheck,
    label: "Run a workforce audit",
    prompt: "Run a workforce audit covering headcount, open roles, and any compliance gaps. Summarize findings and recommend next actions.",
  },
  {
    icon: Mail,
    label: "Summarize recent emails",
    prompt:
      "Read the most recent 10 emails from the email inbox, summarize each one, and write the summary into a Markdown file. Highlight anything that needs a reply or follow-up.",
  },
  {
    icon: UserPlus,
    label: "Start onboarding",
    prompt: "Start the new-hire onboarding workflow for ",
  },
]

interface ChatLandingProps {
  /** External draft (e.g. intake → Copilot) — fills composer without sending. */
  prefill?: { text: string; nonce: number }
}

export function ChatLanding({ prefill: externalPrefill }: ChatLandingProps) {
  const [prefill, setPrefill] = useState<{ text: string; nonce: number }>()

  useEffect(() => {
    if (externalPrefill) {
      setPrefill(externalPrefill)
      return
    }
    // Fallback if ChatArea remounted before prop arrived
    try {
      const raw = sessionStorage.getItem("hr-copilot:pending-chat-launch")
      if (!raw) return
      const parsed = JSON.parse(raw) as { message?: string; autoSend?: boolean; nonce?: number }
      if (parsed?.message && parsed.autoSend === false) {
        setPrefill({ text: parsed.message, nonce: parsed.nonce ?? Date.now() })
      }
    } catch {
      /* ignore */
    }
  }, [externalPrefill])

  const applyQuickAction = (prompt: string) => {
    setPrefill({ text: prompt, nonce: Date.now() })
  }

  return (
    <div className="relative z-10 flex flex-1 flex-col items-center justify-center overflow-y-auto px-6 py-6">
      <div className="dream-in mb-5" style={{ animationDelay: "0.05s" }}>
        <div className="relative flex h-36 w-36 items-center justify-center sm:h-44 sm:w-44">
          <div
            aria-hidden
            className="absolute inset-0 rounded-full bg-[radial-gradient(circle,rgba(255,107,74,0.18)_0%,transparent_68%)] blur-2xl"
          />
          <Image
            src="/vera.png"
            alt="Vera"
            width={176}
            height={176}
            priority
            className="relative z-10 h-full w-full object-contain drop-shadow-[0_12px_28px_rgba(255,107,74,0.22)] animate-float"
          />
        </div>
      </div>

      <h1
        className="dream-in mb-8 text-center font-[var(--font-heading)] text-4xl font-semibold tracking-tight text-foreground text-balance"
        style={{ animationDelay: "0.1s" }}
      >
        What task can I complete for you?
      </h1>

      <div className="mb-8 flex flex-wrap items-center justify-center gap-3">
        {QUICK_ACTIONS.map(({ icon: Icon, label, prompt }, i) => (
          <Button
            key={label}
            variant="secondary"
            onClick={() => applyQuickAction(prompt)}
            className="dream-in gap-2 border border-border/70 bg-card font-medium text-secondary-foreground shadow-sm transition-colors duration-300 hover:border-primary/30 hover:bg-accent hover:text-accent-foreground"
            style={{ animationDelay: `${0.25 + i * 0.08}s` }}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Button>
        ))}
      </div>

      <div className="dream-in w-full" style={{ animationDelay: "0.5s" }}>
        <ChatComposer prefill={prefill} />
      </div>
    </div>
  )
}
