"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { useChat } from "@/lib/chat-store"
import { linkedChatIdForWork } from "@/lib/chat-work-bridge"
import { ensureWorkHydrated, useWorkStore } from "@/lib/work-store"

export type View = "chat" | "mcp" | "skills" | "marketplace" | "memory" | "settings" | "intake" | "work" | "automations" | "systems"
export type MarketplaceSection = "home" | "skills" | "mcp"

const VALID_VIEWS = new Set<View>([
  "chat",
  "mcp",
  "skills",
  "marketplace",
  "memory",
  "settings",
  "intake",
  "work",
  "automations",
  "systems",
])

const VIEW_STORAGE_KEY = "hr-copilot:nav-view"
const MARKETPLACE_SECTION_KEY = "hr-copilot:nav-marketplace-section"
/** Survives React Strict Mode remounts (in-memory pending is cleared too early). */
export const PENDING_CHAT_LAUNCH_KEY = "hr-copilot:pending-chat-launch"

export type PendingChatLaunch = {
  message: string
  newChat?: boolean
  chatId?: string
  /** When false, open chat with the message in the composer only — do not send. */
  autoSend?: boolean
  nonce: number
}

export function writePendingChatLaunch(launch: PendingChatLaunch) {
  try {
    sessionStorage.setItem(PENDING_CHAT_LAUNCH_KEY, JSON.stringify(launch))
  } catch {
    /* ignore */
  }
}

export function readPendingChatLaunch(): PendingChatLaunch | null {
  try {
    const raw = sessionStorage.getItem(PENDING_CHAT_LAUNCH_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PendingChatLaunch
    if (!parsed?.message || typeof parsed.message !== "string") return null
    return parsed
  } catch {
    return null
  }
}

export function clearPendingChatLaunchStorage() {
  try {
    sessionStorage.removeItem(PENDING_CHAT_LAUNCH_KEY)
  } catch {
    /* ignore */
  }
}

/** Path helpers for SPA view ↔ URL sync (reload restores the last page). */
function viewFromPathname(pathname: string): View | null {
  if (pathname === "/work" || pathname.startsWith("/work/")) return "work"
  if (pathname === "/intake" || pathname.startsWith("/intake/")) return "intake"
  if (pathname === "/automations" || pathname.startsWith("/automations/")) return "automations"
  if (pathname === "/systems" || pathname.startsWith("/systems/")) return "systems"
  return null
}

function pathForView(view: View, workId?: string | null): string {
  if (view === "work") return workId ? `/work/${workId}` : "/work"
  if (view === "intake") return "/intake"
  if (view === "automations") return "/automations"
  if (view === "systems") return "/systems"
  // Chat / skills / MCP / etc. use a dedicated shell route so `/` stays the public landing.
  return "/chat"
}

function syncUrlForView(view: View, workId?: string | null) {
  if (typeof window === "undefined") return
  const next = pathForView(view, workId)
  const cur = window.location.pathname
  if (cur === next) return
  // Keep /work?status=… while on the work list (no detail id)
  if (view === "work" && !workId && cur === "/work") return
  try {
    window.history.replaceState(window.history.state, "", next)
  } catch {
    /* ignore */
  }
}

function readStoredView(): View {
  if (typeof window === "undefined") return "intake"
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get("shared") || params.get("chat")) return "chat"

    const pathname = window.location.pathname
    // Explicit detail deep-links always win.
    if (pathname.startsWith("/work/") || pathname.startsWith("/intake/")) {
      return viewFromPathname(pathname) ?? "intake"
    }

    // Fresh login / Tasks entry: prefer the URL over a stale stored chat view.
    const fromPath = viewFromPathname(pathname)
    if (fromPath) return fromPath

    const raw = window.localStorage.getItem(VIEW_STORAGE_KEY)
    const stored = raw && VALID_VIEWS.has(raw as View) ? (raw as View) : null

    // Prefer last SPA page (chat/skills/…) over a stale /work URL left behind
    // when the UI switched views without a Next.js navigation.
    if (stored) return stored

    return "intake"
  } catch {
    return "intake"
  }
}

function readStoredMarketplaceSection(): MarketplaceSection {
  if (typeof window === "undefined") return "home"
  try {
    const raw = window.localStorage.getItem(MARKETPLACE_SECTION_KEY)
    if (raw === "home" || raw === "skills" || raw === "mcp") return raw
  } catch {
    /* ignore */
  }
  return "home"
}

interface NavigationContextValue {
  view: View
  setView: (view: View) => void
  marketplaceSection: MarketplaceSection
  setMarketplaceSection: (s: MarketplaceSection) => void
  marketplaceOrigin: View
  selectedWorkId: string | null
  setSelectedWorkId: (id: string | null) => void
  selectedClusterId: string | null
  setSelectedClusterId: (id: string | null) => void
  selectedIntakeItemId: string | null
  navigateToWorkDetail: (workId: string) => void
  /** Open the real Copilot conversation linked to a Work Queue row. */
  navigateToLinkedChat: (chatId: string) => boolean
  navigateToClusterDetail: (clusterId: string, itemId?: string) => void
  pendingChatLaunch: PendingChatLaunch | null
  startChatWithMessage: (
    message: string,
    options?: { newChat?: boolean; chatId?: string; autoSend?: boolean },
  ) => void
  /** Open a new chat with draft text in the composer (user can edit before sending). */
  startChatWithDraft: (message: string, options?: { newChat?: boolean; chatId?: string }) => void
  consumePendingChatLaunch: () => PendingChatLaunch | null
}

const NavigationContext = createContext<NavigationContextValue | null>(null)

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [view, setViewState] = useState<View>("intake")
  const [marketplaceSection, setMarketplaceSection] = useState<MarketplaceSection>("home")
  const [marketplaceOrigin, setMarketplaceOrigin] = useState<View>("skills")
  const [selectedWorkId, setSelectedWorkId] = useState<string | null>(null)
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null)
  const [selectedIntakeItemId, setSelectedIntakeItemId] = useState<string | null>(null)
  const [pendingChatLaunch, setPendingChatLaunch] = useState<PendingChatLaunch | null>(null)
  const [hydrated, setHydrated] = useState(false)
  const prevViewRef = useRef<View>(view)

  // Client-only restore after mount (SSR can't read localStorage).
  useEffect(() => {
    const restored = readStoredView()
    setViewState(restored)
    setMarketplaceSection(readStoredMarketplaceSection())
    syncUrlForView(restored)
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (!hydrated) return
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, view)
    } catch {
      /* ignore */
    }
    syncUrlForView(view, selectedWorkId)
  }, [view, selectedWorkId, hydrated])

  useEffect(() => {
    if (!hydrated) return
    try {
      window.localStorage.setItem(MARKETPLACE_SECTION_KEY, marketplaceSection)
    } catch {
      /* ignore */
    }
  }, [marketplaceSection, hydrated])

  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search)
      if (params.get("shared") || params.get("chat")) {
        setViewState("chat")
        syncUrlForView("chat")
      }
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    if (view === "marketplace" && prevViewRef.current !== "marketplace") {
      setMarketplaceOrigin(prevViewRef.current)
    }
    if (prevViewRef.current === "marketplace" && view !== "marketplace") {
      setMarketplaceSection("home")
    }
    prevViewRef.current = view
  }, [view])

  const handleSetView = useCallback((v: View) => {
    setViewState(v)
    if (v !== "work") setSelectedWorkId(null)
    if (v !== "intake") {
      setSelectedClusterId(null)
      setSelectedIntakeItemId(null)
    }
    syncUrlForView(v)
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, v)
    } catch {
      /* ignore */
    }
  }, [])

  const navigateToWorkDetail = useCallback((workId: string) => {
    // Never open a stub work-detail chat. Jump to the real Copilot conversation
    // when one is linked; otherwise land on the Work Queue list.
    ensureWorkHydrated()
    const item = useWorkStore.getState().getItem(workId)
    const chatId = item ? linkedChatIdForWork(item) : null
    if (chatId) {
      const chat = useChat.getState()
      if (chat.conversations.some((c) => c.id === chatId)) {
        chat.selectConversation(chatId)
        setSelectedWorkId(null)
        setViewState("chat")
        try {
          window.localStorage.setItem(VIEW_STORAGE_KEY, "chat")
          const url = new URL(window.location.href)
          url.pathname = "/chat"
          url.searchParams.set("chat", chatId)
          url.searchParams.delete("shared")
          window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`)
        } catch {
          syncUrlForView("chat")
        }
        return
      }
    }
    setSelectedWorkId(null)
    setViewState("work")
    syncUrlForView("work")
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, "work")
    } catch {
      /* ignore */
    }
  }, [])

  const navigateToLinkedChat = useCallback((chatId: string) => {
    const id = chatId.trim()
    if (!id) return false
    const chat = useChat.getState()
    const exists = chat.conversations.some((c) => c.id === id)
    if (!exists) return false
    chat.selectConversation(id)
    setSelectedWorkId(null)
    setViewState("chat")
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, "chat")
      const url = new URL(window.location.href)
      url.pathname = "/chat"
      url.searchParams.set("chat", id)
      url.searchParams.delete("shared")
      window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`)
    } catch {
      syncUrlForView("chat")
    }
    return true
  }, [])

  const navigateToClusterDetail = useCallback((clusterId: string, itemId?: string) => {
    setSelectedClusterId(clusterId)
    setSelectedIntakeItemId(itemId ?? null)
    setViewState("intake")
    try {
      const path = itemId
        ? `/intake/${clusterId}?item=${encodeURIComponent(itemId)}`
        : `/intake/${clusterId}`
      window.history.replaceState(window.history.state, "", path)
      window.localStorage.setItem(VIEW_STORAGE_KEY, "intake")
    } catch {
      syncUrlForView("intake")
    }
  }, [])

  const handleSetMarketplaceSection = useCallback((s: MarketplaceSection) => {
    setMarketplaceSection(s)
  }, [])

  const startChatWithMessage = useCallback(
    (message: string, options?: { newChat?: boolean; chatId?: string; autoSend?: boolean }) => {
      const launch: PendingChatLaunch = {
        message: message.trim(),
        newChat: options?.chatId ? false : (options?.newChat ?? true),
        chatId: options?.chatId,
        autoSend: options?.autoSend !== false,
        nonce: Date.now(),
      }
      if (!launch.message && options?.autoSend !== false) return
      writePendingChatLaunch(launch)
      setPendingChatLaunch(launch)
      setViewState("chat")
      syncUrlForView("chat")
      try {
        window.localStorage.setItem(VIEW_STORAGE_KEY, "chat")
      } catch {
        /* ignore */
      }
    },
    [],
  )

  const startChatWithDraft = useCallback(
    (message: string, _options?: { newChat?: boolean; chatId?: string }) => {
      const text = message.trim()
      if (!text) return
      // Write draft into the zustand chat store (survives view switches / remounts),
      // then flip to the chat view so ChatComposer can pick it up.
      useChat.getState().openChatWithDraft(text)
      setViewState("chat")
      syncUrlForView("chat")
      try {
        window.localStorage.setItem(VIEW_STORAGE_KEY, "chat")
      } catch {
        /* ignore */
      }
    },
    [],
  )

  const consumePendingChatLaunch = useCallback(() => {
    const fromState = pendingChatLaunch
    const fromStore = readPendingChatLaunch()
    const launch = fromState ?? fromStore
    setPendingChatLaunch(null)
    // Keep sessionStorage until ChatArea finishes applying (Strict Mode remount).
    return launch
  }, [pendingChatLaunch])

  const value = useMemo(
    () => ({
      view,
      setView: handleSetView,
      marketplaceSection,
      setMarketplaceSection: handleSetMarketplaceSection,
      marketplaceOrigin,
      selectedWorkId,
      setSelectedWorkId,
      selectedClusterId,
      setSelectedClusterId,
      selectedIntakeItemId,
      navigateToWorkDetail,
      navigateToLinkedChat,
      navigateToClusterDetail,
      pendingChatLaunch,
      startChatWithMessage,
      startChatWithDraft,
      consumePendingChatLaunch,
    }),
    [
      view,
      handleSetView,
      marketplaceSection,
      handleSetMarketplaceSection,
      marketplaceOrigin,
      selectedWorkId,
      selectedClusterId,
      selectedIntakeItemId,
      navigateToWorkDetail,
      navigateToLinkedChat,
      navigateToClusterDetail,
      pendingChatLaunch,
      startChatWithMessage,
      startChatWithDraft,
      consumePendingChatLaunch,
    ],
  )

  return <NavigationContext.Provider value={value}>{children}</NavigationContext.Provider>
}

export function useNavigation() {
  const ctx = useContext(NavigationContext)
  if (!ctx) throw new Error("useNavigation must be used within a NavigationProvider")
  return ctx
}

