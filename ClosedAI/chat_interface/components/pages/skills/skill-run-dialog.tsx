"use client"

import { useMemo, useState } from "react"
import {
  ArrowLeft,
  MessageSquare,
  MessageSquarePlus,
  Search,
  Star,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { useChat } from "@/lib/chat-store"
import { cn } from "@/lib/utils"
import type { Skill } from "./skill-types"
import { buildTryInChatPrompt } from "./skill-catalog"

type LaunchTarget =
  | { kind: "new" }
  | { kind: "existing"; chatId: string }

interface SkillRunDialogProps {
  skill: Skill | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onLaunch: (message: string, target: LaunchTarget) => void
}

export function SkillRunDialog({ skill, open, onOpenChange, onLaunch }: SkillRunDialogProps) {
  const conversations = useChat((s) => s.conversations)
  const activeId = useChat((s) => s.activeId)
  const [query, setQuery] = useState("")
  const [pickingExisting, setPickingExisting] = useState(false)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return conversations.filter((c) => !q || c.title.toLowerCase().includes(q))
  }, [conversations, query])

  const resetAndClose = (next: boolean) => {
    if (!next) {
      setQuery("")
      setPickingExisting(false)
    }
    onOpenChange(next)
  }

  const launch = (target: LaunchTarget) => {
    if (!skill) return
    onLaunch(buildTryInChatPrompt(skill), target)
    resetAndClose(false)
  }

  return (
    <Dialog open={open} onOpenChange={resetAndClose}>
      <DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-[400px]">
        <DialogHeader className="space-y-2 px-7 pb-2 pt-7 text-left">
          <DialogTitle className="font-[family-name:var(--font-brand)] text-xl font-semibold tracking-tight text-foreground">
            {skill?.name ?? "Skill"}
          </DialogTitle>
          <DialogDescription className="text-[13px] leading-relaxed text-muted-foreground">
            Run this in a new chat, or continue in one you already have.
          </DialogDescription>
        </DialogHeader>

        {!pickingExisting ? (
          <div className="space-y-3 px-7 pb-7 pt-5">
            <button
              type="button"
              onClick={() => launch({ kind: "new" })}
              className="flex w-full items-center gap-4 rounded-xl border border-border px-4 py-4 text-left transition-colors hover:bg-secondary/50"
            >
              <MessageSquarePlus className="h-5 w-5 shrink-0 text-foreground" />
              <span className="min-w-0">
                <span className="block text-[14px] font-medium text-foreground">New chat</span>
                <span className="mt-1 block text-[12px] text-muted-foreground">
                  Start fresh with this skill
                </span>
              </span>
            </button>

            <button
              type="button"
              onClick={() => setPickingExisting(true)}
              className="flex w-full items-center gap-4 rounded-xl border border-border px-4 py-4 text-left transition-colors hover:bg-secondary/50"
            >
              <MessageSquare className="h-5 w-5 shrink-0 text-foreground" />
              <span className="min-w-0">
                <span className="block text-[14px] font-medium text-foreground">Existing chat</span>
                <span className="mt-1 block text-[12px] text-muted-foreground">
                  Pick from your conversations
                </span>
              </span>
            </button>
          </div>
        ) : (
          <div className="flex max-h-[420px] flex-col">
            <div className="space-y-4 px-7 pb-4 pt-3">
              <button
                type="button"
                onClick={() => {
                  setPickingExisting(false)
                  setQuery("")
                }}
                className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back
              </button>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search chats…"
                  className="w-full rounded-xl border border-border bg-transparent py-3 pl-10 pr-4 text-[13px] text-foreground outline-none placeholder:text-muted-foreground focus:border-foreground/25"
                />
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-2">
              {filtered.length === 0 ? (
                <div className="px-3 py-12 text-center">
                  <p className="text-[13px] text-muted-foreground">
                    {conversations.length === 0 ? "No chats yet." : "No matches."}
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-5"
                    onClick={() => launch({ kind: "new" })}
                  >
                    New chat instead
                  </Button>
                </div>
              ) : (
                <ul className="space-y-1 pb-2">
                  {filtered.map((c) => {
                    const isActive = c.id === activeId
                    return (
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => launch({ kind: "existing", chatId: c.id })}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-secondary/60",
                            isActive && "bg-secondary/50",
                          )}
                        >
                          {c.favorite ? (
                            <Star className="h-4 w-4 shrink-0 fill-amber-400/90 text-amber-400/90" />
                          ) : (
                            <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                          )}
                          <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">
                            {c.title}
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>

            <div className="px-7 py-4">
              <Button
                variant="ghost"
                className="w-full justify-center text-muted-foreground"
                onClick={() => launch({ kind: "new" })}
              >
                New chat instead
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
