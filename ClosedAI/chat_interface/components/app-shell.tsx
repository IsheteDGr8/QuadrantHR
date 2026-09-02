"use client"

import { useEffect, useRef, useState } from "react"
import { PanelLeftOpen } from "lucide-react"
import { toast } from "sonner"
import { AppSidebar } from "@/components/app-sidebar"
import { ChatArea } from "@/components/chat-area"
import { McpConnectionsPage } from "@/components/pages/mcp/page"
import { SkillsPage } from "@/components/pages/skills/page"
import { MarketplaceDashboard } from "@/components/pages/marketplace/page"
import { MemoryPage } from "@/components/pages/memory-page"
import { SettingsPage } from "@/components/pages/settings-page"
import IntakePage from "@/components/pages/intake-page"
import WorkPage from "@/components/pages/work-page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useNavigation } from "@/lib/navigation"
import { useChat } from "@/lib/chat-store"

const SIDEBAR_MIN_WIDTH = 240
const SIDEBAR_MAX_WIDTH = 420
const SIDEBAR_DEFAULT_WIDTH = 320

export function AppShell() {
  const { view, setView } = useNavigation()
  const {
    sessionHydrated,
    conversations,
    selectConversation,
    openSharedChat,
  } = useChat()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH)
  const [isDragging, setIsDragging] = useState(false)
  const deepLinkDone = useRef(false)

  // Share / chat deep-links must run here — ChatArea is unmounted when the
  // default view is Intake/Work Queue, so links never opened the conversation.
  useEffect(() => {
    if (!sessionHydrated || deepLinkDone.current) return
    if (typeof window === "undefined") return

    const params = new URLSearchParams(window.location.search)
    const sharedId = params.get("shared")
    const chatId = params.get("chat")
    if (!sharedId && !chatId) return

    // Switch to chat immediately so the conversation UI is visible.
    setView("chat")

    if (sharedId) {
      deepLinkDone.current = true
      void (async () => {
        try {
          const res = await fetch(`/api/share?id=${encodeURIComponent(sharedId)}`)
          if (!res.ok) {
            toast.error("Shared chat not found")
            return
          }
          const data = await res.json()
          openSharedChat({
            shareId: data.shareId || sharedId,
            title: data.title || "Shared chat",
            messages: data.messages || [],
          })
          toast.success("Opened shared chat")
        } catch {
          toast.error("Could not open shared chat")
        }
      })()
      return
    }

    if (chatId) {
      if (conversations.some((c) => c.id === chatId)) {
        deepLinkDone.current = true
        selectConversation(chatId)
        return
      }
      deepLinkDone.current = true
      toast.error("This chat isn't available on this device", {
        description: "Ask for a new Share link — shared links use a snapshot that works anywhere.",
      })
    }
  }, [sessionHydrated, conversations, selectConversation, openSharedChat, setView])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const next = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, e.clientX))
      setSidebarWidth(next)
    }
    const stopDragging = () => setIsDragging(false)

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", stopDragging)

    return () => {
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", stopDragging)
    }
  }, [isDragging])

  const isChat = view === "chat"

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {view === "marketplace" ? (
        <MarketplaceDashboard />
      ) : (
        <>
          <div
            style={{ width: sidebarOpen ? sidebarWidth : 0 }}
            className={cn(
              "shrink-0 overflow-hidden",
              !isDragging && "transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
            )}
          >
            <AppSidebar open={sidebarOpen} width={sidebarWidth} onCollapse={() => setSidebarOpen(false)} />
          </div>

          {/* Draggable divider */}
          {sidebarOpen && (
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize sidebar"
              onMouseDown={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDoubleClick={() => setSidebarWidth(SIDEBAR_DEFAULT_WIDTH)}
              className="group relative z-20 flex w-2 shrink-0 cursor-col-resize items-stretch justify-center"
            >
              <span
                className={cn(
                  "pointer-events-none h-full rounded-full transition-all duration-200",
                  isDragging ? "w-1 bg-primary/40" : "w-px bg-sidebar-border group-hover:w-1 group-hover:bg-primary/30",
                )}
              />
            </div>
          )}

          {isChat ? (
            <ChatArea sidebarOpen={sidebarOpen} onOpenSidebar={() => setSidebarOpen(true)} />
          ) : (
            <main className="relative flex flex-1 flex-col overflow-y-auto bg-background">
              {!sidebarOpen && (
                <div className="absolute left-4 top-4 z-20">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-foreground"
                    onClick={() => setSidebarOpen(true)}
                    aria-label="Open sidebar"
                  >
                    <PanelLeftOpen className="h-4 w-4" />
                  </Button>
                </div>
              )}
              {view === "intake" && <IntakePage />}
              {view === "work" && <WorkPage />}
              {view === "mcp" && <McpConnectionsPage />}
              {view === "skills" && <SkillsPage />}
              {view === "memory" && <MemoryPage />}
              {view === "settings" && <SettingsPage />}
            </main>
          )}
        </>
      )}
    </div>
  )
}
