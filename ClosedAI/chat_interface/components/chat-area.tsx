"use client"

import { useEffect, useRef, useState } from "react"
import { X, ChevronDown, Share2, PanelLeftOpen, MessageSquarePlus } from "lucide-react"
import { toast } from "sonner"
import { ChatLanding } from "@/components/chat-landing"
import { ChatConversation } from "@/components/chat-conversation"
import { AgentExecutionPanel, AgentActivityToggle } from "@/components/agent-execution-panel"
import { SideCanvas, CanvasToggle } from "@/components/side-canvas"
import { OptionMenu } from "@/components/option-menu"
import { Button } from "@/components/ui/button"
import { useChat, MODELS } from "@/lib/chat-store"
import {
  clearPendingChatLaunchStorage,
  readPendingChatLaunch,
  useNavigation,
  type PendingChatLaunch,
} from "@/lib/navigation"

const AGENTS = ["Vera", "Research Agent", "Writing Agent", "Support Agent"]

/** Prevents double-send / double-newChat across React Strict Mode remounts. */
const appliedLaunchNonces = new Set<number>()

interface ChatAreaProps {
  sidebarOpen: boolean
  onOpenSidebar: () => void
}

export function ChatArea({ sidebarOpen, onOpenSidebar }: ChatAreaProps) {
  const {
    activeConversation,
    activeId,
    newChat,
    selectConversation,
    model,
    setModel,
    sendMessage,
    conversations,
  } = useChat()
  const { pendingChatLaunch, consumePendingChatLaunch } = useNavigation()
  const [agent, setAgent] = useState(AGENTS[0])
  const [composerPrefill, setComposerPrefill] = useState<{ text: string; nonce: number }>()
  const applyingRef = useRef(false)
  const inChat = activeConversation.length > 0

  // Apply intake/skills launch whenever one is pending (context or sessionStorage).
  useEffect(() => {
    const launch: PendingChatLaunch | null =
      pendingChatLaunch ?? readPendingChatLaunch()
    if (!launch?.message) return
    if (applyingRef.current) return

    const nonce = launch.nonce || Date.now()
    const alreadyApplied = appliedLaunchNonces.has(nonce)

    // Always restore draft text into the composer (survives Strict Mode remount).
    if (launch.autoSend === false) {
      setComposerPrefill({ text: launch.message, nonce })
    }

    if (alreadyApplied) return
    appliedLaunchNonces.add(nonce)
    applyingRef.current = true

    try {
      if (launch.chatId) selectConversation(launch.chatId)
      else if (launch.newChat !== false) newChat()

      consumePendingChatLaunch()

      if (launch.autoSend === false) {
        // Keep storage briefly so a Strict Mode remount can re-hydrate the textarea;
        // clear on the next tick after state commit.
        window.setTimeout(() => clearPendingChatLaunchStorage(), 500)
      } else {
        clearPendingChatLaunchStorage()
        void sendMessage(launch.message)
      }
    } finally {
      applyingRef.current = false
    }
  }, [
    pendingChatLaunch,
    consumePendingChatLaunch,
    newChat,
    selectConversation,
    sendMessage,
  ])

  const shareChat = async () => {
    if (!activeId) {
      toast.error("Start a chat first to share it")
      return
    }
    if (activeConversation.length === 0) {
      toast.error("Send a message before sharing")
      return
    }
    try {
      const title =
        conversations.find((c) => c.id === activeId)?.title || "Shared chat"
      const res = await fetch("/api/share", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sourceChatId: activeId,
          title,
          messages: activeConversation.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            createdAt: m.createdAt ?? m.timestamp?.getTime?.() ?? Date.now(),
            status: m.status,
            metadata: m.metadata,
          })),
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || "Share failed")
      }
      const { shareId } = await res.json()
      const url = new URL(window.location.href)
      url.searchParams.delete("chat")
      url.searchParams.set("shared", shareId)
      url.hash = ""
      const link = url.toString()
      await navigator.clipboard.writeText(link)
      window.history.replaceState({}, "", link)
      toast.success("Chat link copied", {
        description: "Opening this link loads this conversation.",
      })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not copy link")
    }
  }

  return (
    <main className="relative flex flex-1 flex-col overflow-hidden">
      <div className="absolute inset-0 bg-background" />
      <div className="absolute inset-0 overflow-hidden">
        <div className="shader-orb shader-orb-1" />
        <div className="shader-orb shader-orb-2" />
        <div className="shader-orb shader-orb-3" />
      </div>
      <div className="grid-background absolute inset-0 opacity-[0.12]" />

      <header className="relative z-10 flex items-center justify-between border-b border-border/50 px-6 py-4">
        <div className="flex items-center gap-3">
          {!sidebarOpen && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-foreground"
              onClick={onOpenSidebar}
              aria-label="Open sidebar"
            >
              <PanelLeftOpen className="h-4 w-4" />
            </Button>
          )}

          {inChat ? (
            <div className="flex items-center gap-3">
              <button
                aria-label="Close chat"
                onClick={newChat}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
              <OptionMenu
                label="Switch agent"
                options={AGENTS}
                value={agent}
                onChange={setAgent}
                trigger={
                  <button className="flex items-center gap-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src="/vera.png" alt="" className="h-5 w-5 object-contain" />
                    <span className="text-[15px] font-medium text-foreground">{agent}</span>
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  </button>
                }
              />
            </div>
          ) : (
            <OptionMenu
              label="Model"
              options={MODELS.map((m) => m.label)}
              value={model}
              onChange={setModel}
              trigger={
                <Button className="gap-2 border border-border/50 bg-secondary text-foreground backdrop-blur-sm transition-colors duration-300 hover:bg-secondary/70">
                  {model}
                  <ChevronDown className="h-4 w-4" />
                </Button>
              }
            />
          )}
        </div>

        <div className="flex items-center gap-2">
          <CanvasToggle />
          <AgentActivityToggle />
          {inChat ? (
            <>
              <button
                onClick={shareChat}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-[13px] font-medium text-foreground shadow-sm transition-colors hover:bg-secondary"
              >
                <Share2 className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Share</span>
              </button>
              <button
                onClick={newChat}
                className="inline-flex items-center gap-1.5 rounded-lg border border-navy/20 bg-navy px-2.5 py-1.5 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-navy/90"
              >
                <MessageSquarePlus className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">New</span>
              </button>
            </>
          ) : null}
        </div>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {inChat ? (
            <ChatConversation prefill={composerPrefill} />
          ) : (
            <ChatLanding prefill={composerPrefill} />
          )}
        </div>
        <SideCanvas />
        <AgentExecutionPanel />
      </div>
    </main>
  )
}
