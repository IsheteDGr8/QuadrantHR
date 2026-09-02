"use client"

import { useState } from "react"
import {
  Search,
  Plug,
  Blocks,
  Store,
  Brain,
  SlidersHorizontal,
  ChevronRight,
  ChevronDown,
  ChevronsUpDown,
  MoreHorizontal,
  Circle,
  CheckCircle2,
  Trash2,
  PanelLeftClose,
  Radar,
  Inbox,
  MessageSquarePlus,
  Star,
  User,
  Settings,
  LogOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { useChat } from "@/lib/chat-store"
import { useNavigation, type View } from "@/lib/navigation"
import { BrandLockup } from "@/components/brand-lockup"
import { HrAlertsBell } from "@/components/hr-alerts-bell"
import { initialsFromName, signOut, useAuthProfile } from "@/lib/auth-profile"

const PRIMARY_NAV: { icon: typeof Radar; label: string; view: View }[] = [
  { icon: Radar, label: "Tasks", view: "intake" },
  { icon: Inbox, label: "Work Queue", view: "work" },
  { icon: Blocks, label: "Skills", view: "skills" },
  { icon: Plug, label: "MCP Connections", view: "mcp" },
  { icon: Store, label: "MCP Marketplace", view: "marketplace" },
  { icon: Brain, label: "Memory", view: "memory" },
  { icon: SlidersHorizontal, label: "Settings", view: "settings" },
]

interface AppSidebarProps {
  open: boolean
  width: number
  onCollapse: () => void
}

export function AppSidebar({ open, width, onCollapse }: AppSidebarProps) {
  const {
    conversations,
    activeId,
    newChat,
    selectConversation,
    deleteConversation,
    toggleFavorite,
  } = useChat()
  const { view, setView } = useNavigation()
  const profile = useAuthProfile()
  const displayName = profile?.name?.trim() || "Employee"
  const displayEmail =
    profile?.email?.trim() ||
    (profile?.provider === "google"
      ? "Google account"
      : profile?.provider === "microsoft"
        ? "Microsoft account"
        : "Personal workspace")
  const initials = initialsFromName(displayName)
  const [query, setQuery] = useState("")
  const [favoritesOpen, setFavoritesOpen] = useState(true)
  const [recentOpen, setRecentOpen] = useState(true)
  const [showAllRecent, setShowAllRecent] = useState(false)

  const goNewChat = () => {
    setView("chat")
    newChat()
  }
  const goSelect = (id: string) => {
    setView("chat")
    selectConversation(id)
  }

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(query.toLowerCase()),
  )
  const favorites = filtered.filter((c) => c.favorite)
  const recent = filtered.filter((c) => !c.favorite)
  const visibleRecent = showAllRecent ? recent : recent.slice(0, 5)
  const hasMore = recent.length > 5

  return (
    <aside
      style={{ width }}
      className={cn(
        "sidebar-peach-wash flex h-full flex-col border-r border-sidebar-border/60 transition-[opacity,transform,filter] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
        open ? "translate-x-0 opacity-100 blur-0" : "-translate-x-6 opacity-0 blur-sm",
      )}
    >
      {/* Brand / logo */}
      <div className="flex items-center justify-between px-3 pt-4 pb-2">
        <div className="min-w-0 flex-1 rounded-lg px-2 py-1.5">
          <BrandLockup />
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <HrAlertsBell />
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground transition-all duration-300 hover:bg-sidebar-accent hover:text-sidebar-foreground active:scale-90"
            onClick={onCollapse}
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* New Chat */}
      <div className="px-3 pb-2 pt-1">
        <div className="flex items-stretch gap-1">
          <Button
            variant="secondary"
            onClick={goNewChat}
            className="flex-1 justify-center gap-2 rounded-md border border-primary/20 bg-primary font-medium text-primary-foreground shadow-sm transition-colors hover:opacity-90"
          >
            <MessageSquarePlus className="h-4 w-4" />
            New Chat
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                id="sidebar-new-chat-trigger"
                variant="secondary"
                size="icon"
                aria-label="New chat options"
                className="group rounded-md border border-primary/20 bg-primary text-primary-foreground shadow-sm transition-colors hover:opacity-90"
              >
                <ChevronDown className="h-4 w-4 transition-transform duration-300 group-data-[state=open]:rotate-180" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              sideOffset={6}
              className="w-56 border-border bg-popover text-foreground shadow-2xl duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
            >
              <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Create new
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-border" />
              <DropdownMenuItem
                onClick={goNewChat}
                className="gap-2.5 text-[13px] transition-colors focus:bg-accent focus:text-foreground"
              >
                <MessageSquarePlus className="h-4 w-4 text-muted-foreground" />
                New Chat
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => setView("skills")}
                className="gap-2.5 text-[13px] transition-colors focus:bg-accent focus:text-foreground"
              >
                <Blocks className="h-4 w-4 text-muted-foreground" />
                New Chat from Skill
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-1">
        {/* Primary nav */}
        <nav className="space-y-0.5">
          {PRIMARY_NAV.map(({ icon: Icon, label, view: navView }) => (
            <button
              key={label}
              onClick={() => setView(navView)}
              className={cn(
                "group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors duration-200 hover:bg-sidebar-accent",
                view === navView && "bg-sidebar-accent",
              )}
            >
              <Icon
                className={cn(
                  "h-[18px] w-[18px] text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground",
                  view === navView && "text-sidebar-foreground",
                )}
              />
              {label}
            </button>
          ))}
        </nav>

        {/* Glassy search — spaced below nav, near favorites */}
        <div className="mt-6 px-0.5">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#5C534A]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats…"
              className="w-full rounded-full border border-[#B8B0A6]/85 bg-[#E6E1DB]/60 py-2.5 pl-9 pr-3 text-sm text-sidebar-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] outline-none backdrop-blur-md transition-all placeholder:text-muted-foreground focus:border-[#9A9288] focus:bg-[#DFDAD3]/75 focus:ring-2 focus:ring-[#B8B0A6]/35"
            />
          </div>
        </div>

        {/* Favorites */}
        <div className="mt-4">
          <button
            onClick={() => setFavoritesOpen((v) => !v)}
            className="group flex w-full items-center justify-between rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70 transition-all duration-300 hover:text-sidebar-foreground"
          >
            <span>Favorites</span>
            <ChevronRight
              className={cn("h-3.5 w-3.5 transition-transform duration-300", favoritesOpen && "rotate-90")}
            />
          </button>
          <div
            className={cn(
              "grid transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
              favoritesOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
            )}
          >
            <div className="overflow-hidden">
              {favorites.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">
                  Tap the circle to star a chat.
                </p>
              ) : (
                <div className="space-y-0.5 pt-1">
                  {favorites.map((c) => (
                    <ChatRow
                      key={c.id}
                      id={c.id}
                      title={c.title}
                      active={activeId === c.id}
                      favorite
                      onSelect={() => goSelect(c.id)}
                      onToggleFavorite={() => toggleFavorite(c.id)}
                      onDelete={() => deleteConversation(c.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Recent Chats */}
        <div className="mt-4">
          <button
            onClick={() => setRecentOpen((v) => !v)}
            className="group flex w-full items-center justify-between rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70 transition-all duration-300 hover:text-sidebar-foreground"
          >
            <span>Recent Chats</span>
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 transition-transform duration-300",
                recentOpen ? "rotate-0" : "-rotate-90",
              )}
            />
          </button>
          <div
            className={cn(
              "grid transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
              recentOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
            )}
          >
            <div className="overflow-hidden">
              <div className="space-y-0.5 pt-1">
                {visibleRecent.length === 0 && (
                  <p className="px-3 py-2 text-xs text-muted-foreground">No chats found.</p>
                )}
                {visibleRecent.map((c) => (
                  <ChatRow
                    key={c.id}
                    id={c.id}
                    title={c.title}
                    active={activeId === c.id}
                    favorite={!!c.favorite}
                    onSelect={() => goSelect(c.id)}
                    onToggleFavorite={() => toggleFavorite(c.id)}
                    onDelete={() => deleteConversation(c.id)}
                  />
                ))}
                {hasMore && (
                  <button
                    onClick={() => setShowAllRecent((v) => !v)}
                    className="group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-all duration-300 hover:translate-x-0.5 hover:bg-sidebar-accent hover:text-sidebar-foreground active:scale-[0.98]"
                  >
                    <MoreHorizontal className="h-4 w-4 transition-colors duration-300 group-hover:text-sidebar-foreground" />
                    {showAllRecent ? "Less" : "More"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom profile */}
      <div className="border-t border-sidebar-border p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              id="sidebar-user-menu-trigger"
              className="group flex w-full min-w-0 items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-all duration-300 hover:-translate-y-px hover:bg-sidebar-accent active:scale-[0.99]"
            >
              {profile?.picture ? (
                <img
                  src={profile.picture}
                  alt=""
                  referrerPolicy="no-referrer"
                  className="h-7 w-7 shrink-0 rounded-full border border-border object-cover"
                />
              ) : (
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-secondary text-[11px] font-semibold text-sidebar-foreground">
                  {initials}
                </span>
              )}
              <span className="truncate text-sm font-medium text-sidebar-foreground">{displayName}</span>
              <ChevronsUpDown className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            side="top"
            className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-[240px]"
          >
            <DropdownMenuLabel className="flex items-center gap-2.5">
              {profile?.picture ? (
                <img
                  src={profile.picture}
                  alt=""
                  referrerPolicy="no-referrer"
                  className="h-8 w-8 shrink-0 rounded-full object-cover"
                />
              ) : (
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold">
                  {initials}
                </span>
              )}
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[13px] font-medium text-foreground">{displayName}</span>
                <span className="truncate text-xs font-normal text-muted-foreground">{displayEmail}</span>
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                setView("settings")
                window.requestAnimationFrame(() => {
                  document.getElementById("profile")?.scrollIntoView({ behavior: "smooth", block: "start" })
                })
              }}
              className="gap-2 text-[13px]"
            >
              <Settings />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              className="gap-2 text-[13px]"
              onClick={() => signOut()}
            >
              <LogOut />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  )
}

function ChatRow({
  title,
  active,
  favorite,
  onSelect,
  onToggleFavorite,
  onDelete,
}: {
  id?: string
  title: string
  active: boolean
  favorite: boolean
  onSelect: () => void
  onToggleFavorite: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={cn(
        "group flex items-center gap-1 rounded-lg px-2 py-1.5 transition-colors duration-200 hover:bg-sidebar-accent",
        active && "bg-sidebar-accent",
      )}
    >
      <button
        onClick={onToggleFavorite}
        aria-label={favorite ? `Unpin ${title}` : `Pin ${title}`}
        title={favorite ? "Unpin" : "Pin to favorites"}
        className="relative flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-white/50"
      >
        {favorite ? (
          <Star className="h-4 w-4 fill-primary text-primary transition-all" />
        ) : active ? (
          <CheckCircle2 className="h-4 w-4 text-navy transition-all" />
        ) : (
          <Circle className="h-4 w-4 text-muted-foreground/70 transition-colors group-hover:text-primary/70" />
        )}
      </button>
      <button onClick={onSelect} className="min-w-0 flex-1 text-left">
        <span
          className={cn(
            "block truncate text-sm text-muted-foreground transition-colors duration-300 group-hover:text-sidebar-foreground",
            active && "font-medium text-sidebar-foreground",
          )}
        >
          {title}
        </span>
      </button>
      <button
        onClick={onDelete}
        aria-label={`Delete ${title}`}
        className="shrink-0 rounded-md p-1 text-muted-foreground opacity-0 transition-all hover:text-destructive group-hover:opacity-100"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}
