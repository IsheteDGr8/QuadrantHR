"use client"

import { useEffect, useRef, useState } from "react"
import { ThumbsUp, ThumbsDown, Copy, Check, Download, FileText, ShieldCheck, Send, X, Loader2 } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ChatComposer } from "@/components/chat-composer"
import { AgentActivityFeed } from "@/components/agent-activity-feed"
import { DocumentPreview } from "@/components/document-preview"
import { useChat, formatRelativeTime, type Message } from "@/lib/chat-store"
import { useCanvas } from "@/lib/canvas-store"
import {
  downloadWorkspaceFile,
  extractFileRefs,
  fileExt,
  friendlyFileTitle,
  scrubAssistantContent,
  scrubUserContent,
} from "@/lib/workspace-files"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

function MessageFiles({ content, files, className }: { content: string; files?: string[]; className?: string }) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewFile, setPreviewFile] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)

  const fileMatches = extractFileRefs(content, files)
  if (fileMatches.length === 0) return null

  const openPreview = (f: string) => {
    setPreviewFile(f)
    setPreviewOpen(true)
  }

  const handleDownload = async (e: React.MouseEvent, filePath: string) => {
    e.stopPropagation()
    e.preventDefault()
    setDownloading(filePath)
    try {
      await downloadWorkspaceFile(filePath)
    } catch {
      window.location.href = `/api/workspace/files?path=${encodeURIComponent(filePath)}&download=1`
    } finally {
      setDownloading(null)
    }
  }

  return (
    <>
      <div className={cn("mt-3 flex flex-wrap gap-2", className)}>
        {fileMatches.map((filePath) => {
          const title = friendlyFileTitle(filePath)
          const ext = fileExt(filePath).replace(".", "").toUpperCase() || "FILE"
          const busy = downloading === filePath
          return (
            <div
              key={filePath}
              className="group inline-flex max-w-full items-center gap-1 rounded-xl border border-border/80 bg-gradient-to-br from-secondary/70 to-secondary/30 p-1.5 pr-2 text-left text-xs text-foreground shadow-sm transition-all hover:border-foreground/20 hover:shadow-md"
            >
              <button
                type="button"
                onClick={() => openPreview(filePath)}
                className="inline-flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-1.5 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-stone-900 text-[#f5e6d3] shadow-sm">
                  <FileText className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-[13px] leading-tight">{title}</span>
                  <span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {ext} · Click to open
                  </span>
                </span>
              </button>
              <button
                type="button"
                onClick={(e) => handleDownload(e, filePath)}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-background/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                title="Download"
                aria-label={`Download ${title}`}
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              </button>
            </div>
          )
        })}
      </div>

      <DocumentPreview
        filePath={previewFile}
        open={previewOpen}
        onOpenChange={(open) => {
          setPreviewOpen(open)
          if (!open) setPreviewFile(null)
        }}
        initialMode="popup"
      />
    </>
  )
}

function ChatApprovalCard({ message }: { message: Message }) {
  const approval = message.metadata?.approval
  const approvePendingApproval = useChat((s) => s.approvePendingApproval)
  const rejectPendingApproval = useChat((s) => s.rejectPendingApproval)
  const persisted = (message.metadata?.approvalStatus || "pending") as
    | "pending"
    | "approved"
    | "rejected"
    | "error"
  const [localStatus, setLocalStatus] = useState(persisted)
  const [busy, setBusy] = useState(false)
  const status = persisted !== "pending" ? persisted : localStatus
  if (!approval) return null

  const submit = async (accept: boolean) => {
    setBusy(true)
    try {
      if (accept) await approvePendingApproval()
      else await rejectPendingApproval()
      const stamped = useChat
        .getState()
        .activeConversation.find((m) => m.id === message.id)?.metadata?.approvalStatus
      setLocalStatus(stamped === "approved" || stamped === "rejected" ? stamped : "error")
    } catch {
      setLocalStatus("error")
    } finally {
      setBusy(false)
    }
  }

  const rows =
    approval.toolName === "send_email"
      ? [
          ["To", approval.params.to],
          ["Cc", approval.params.cc],
          ["Subject", approval.params.subject],
        ]
      : approval.toolName === "send_slack_message"
        ? [["Channel", approval.params.channel]]
        : [["Recipient", approval.params.recipient]]

  return (
    <div className="mt-3 w-full max-w-[520px] rounded-xl border border-amber-500/25 bg-amber-500/[0.055] p-3.5">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-amber-500/25 bg-secondary/60">
          <ShieldCheck className="h-4 w-4 text-amber-300" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-[13px] font-semibold text-foreground">Approval required</p>
            {approval.risk && (
              <span className="rounded-full border border-amber-500/25 bg-secondary/60 px-2 py-0.5 text-[10px] font-medium text-amber-200">
                {approval.risk}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[12px] text-foreground">{approval.title}</p>
          <div className="mt-3 space-y-1.5">
            {rows.map(([label, value]) =>
              value ? (
                <div key={label} className="grid grid-cols-[64px_1fr] gap-2 text-[11.5px]">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="break-words text-foreground">{String(value)}</span>
                </div>
              ) : null,
            )}
          </div>
          <p className="mt-3 text-[11.5px] text-muted-foreground">
            Full draft/status is available in the Canvas. Approval happens here in chat.
          </p>
        </div>
      </div>

      {status === "pending" ? (
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => submit(false)}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-secondary/60 px-3 py-2 text-[12px] font-medium text-foreground transition-colors hover:bg-secondary/50 disabled:opacity-50"
          >
            <X className="h-3.5 w-3.5" />
            Reject
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => submit(true)}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-secondary/70 px-3 py-2 text-[12px] font-semibold text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />
            Approve &amp; Send
          </button>
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-border bg-secondary/60 px-3 py-2 text-[12px] text-foreground">
          <Check className="h-3.5 w-3.5" />
          {status === "approved" ? "Approved. Execution can continue." : status === "rejected" ? "Rejected. Nothing was sent." : "Could not submit approval."}
        </div>
      )}
    </div>
  )
}

function MessageActions({ message }: { message: Message }) {
  const { reactToMessage } = useChat()
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard may be unavailable; ignore
    }
  }

  return (
    <div className="mt-1 flex items-center gap-3 text-muted-foreground">
      <button
        aria-label="Good response"
        aria-pressed={message.reaction === "up"}
        onClick={() => reactToMessage(message.id, "up")}
        className={cn("transition-colors hover:text-foreground", message.reaction === "up" && "text-foreground")}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        aria-label="Bad response"
        aria-pressed={message.reaction === "down"}
        onClick={() => reactToMessage(message.id, "down")}
        className={cn("transition-colors hover:text-foreground", message.reaction === "down" && "text-foreground")}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
      <button
        aria-label="Copy message"
        onClick={handleCopy}
        className="transition-colors hover:text-foreground"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-foreground" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  )
}

function isLongformAssistant(text: string): boolean {
  const t = text.trim()
  if (t.length > 700) return true
  const headings = (t.match(/^#{1,3}\s/gm) || []).length
  const numbered = (t.match(/^\s*\d+\.\s/gm) || []).length
  return headings >= 2 || numbered >= 5
}

function excerptMarkdown(text: string, max = 420): string {
  const trimmed = text.trim()
  if (trimmed.length <= max) return trimmed
  const cut = trimmed.slice(0, max)
  const lastBreak = Math.max(cut.lastIndexOf("\n"), cut.lastIndexOf(". "))
  return `${(lastBreak > 120 ? cut.slice(0, lastBreak + 1) : cut).trim()}\n\n…`
}

function AssistantMarkdown({ content }: { content: string }) {
  const setCanvasOpen = useCanvas((s) => s.setOpen)
  const [expanded, setExpanded] = useState(false)
  const text = scrubAssistantContent(content)
  const long = isLongformAssistant(text)
  const shown = long && !expanded ? excerptMarkdown(text) : text
  return (
    <>
      <ReactMarkdown remarkPlugins={MARKDOWN_PLUGINS} components={MARKDOWN_COMPONENTS}>
        {shown}
      </ReactMarkdown>
      {long && !expanded ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setCanvasOpen(true)}
            className="rounded-lg border border-border bg-secondary/70 px-2.5 py-1 text-[12px] font-medium text-foreground hover:bg-secondary"
          >
            Open full plan in Canvas
          </button>
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="rounded-lg px-2.5 py-1 text-[12px] text-muted-foreground hover:text-foreground"
          >
            Show in chat
          </button>
        </div>
      ) : null}
    </>
  )
}

export const MARKDOWN_PLUGINS = [remarkGfm]
export const MARKDOWN_COMPONENTS: import("react-markdown").Components = {
  p: ({ node, ...props }) => {
    const hasCodeChild = (node?.children ?? []).some(
      (child: any) => child.type === "element" && child.tagName === "code",
    )
    const Tag = hasCodeChild ? "div" : "p"
    return <Tag className="mb-3 last:mb-0" {...props} />
  },
  ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-3 last:mb-0 space-y-1.5" {...props} />,
  ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-3 last:mb-0 space-y-1.5" {...props} />,
  li: ({ node, ...props }) => <li className="marker:text-muted-foreground" {...props} />,
  a: ({ node, ...props }) => (
    <a className="text-blue-400 hover:text-blue-300 hover:underline underline-offset-4 transition-colors" {...props} />
  ),
  strong: ({ node, ...props }) => <strong className="font-semibold text-foreground" {...props} />,
  code: ({ node, inline, className, children, ...props }: any) =>
    inline ? (
      <code className="bg-muted text-foreground rounded-md px-1.5 py-0.5 font-mono text-[12px] border border-border" {...props}>
        {children}
      </code>
    ) : (
      <div className="group relative my-4 rounded-xl border border-border bg-muted shadow-sm overflow-hidden">
        <div className="flex items-center justify-between bg-neutral-900/50 px-4 py-2 border-b border-border">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Code</span>
        </div>
        <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed">
          <code className="font-mono text-foreground" {...props}>
            {children}
          </code>
        </pre>
      </div>
    ),
}

export function ChatConversation({
  prefill,
}: {
  prefill?: { text: string; nonce: number }
}) {
  const { activeConversation, reactToMessage } = useChat()
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [activeConversation.length])

  if (!activeConversation) return null

  return (
    <div className="relative z-10 flex flex-1 flex-col overflow-hidden">
      {/* Live activity feed — pinned above the conversation while the agent works */}
      <AgentActivityFeed />

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[680px] flex-col gap-6 px-6 py-8">
          <div className="text-center text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Today</div>

          {activeConversation.map((message) => {
            const createdAt = message.createdAt ?? message.timestamp?.getTime?.() ?? Date.now()
            if (message.role === "user") {
              const displayText = scrubUserContent(message.content)
              return (
              <div key={message.id} className="msg-in flex flex-col items-end gap-1.5">
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="font-semibold text-foreground">Me</span>
                  <span className="text-muted-foreground">{formatRelativeTime(createdAt)}</span>
                </div>
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-white/60 bg-gradient-to-br from-[#FFF7F1]/95 via-[#FFE8D9]/82 to-[#FFF3EA]/90 px-3.5 py-2.5 text-[14px] leading-relaxed text-foreground shadow-[0_4px_22px_rgba(255,140,100,0.14)] backdrop-blur-md text-pretty">
                  {displayText ? <div className="whitespace-pre-wrap">{displayText}</div> : null}
                  <MessageFiles
                    content={message.content}
                    files={message.metadata?.files}
                    className={displayText ? undefined : "mt-0"}
                  />
                </div>
              </div>
              )
            }
            return (
              <div key={message.id} className="msg-in flex flex-col items-start gap-1.5">
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="font-semibold text-foreground">Vera</span>
                  <span className="text-muted-foreground">{formatRelativeTime(createdAt)}</span>
                </div>
                <div className="max-w-[90%] text-[14px] leading-relaxed text-foreground text-pretty">
                  <AssistantMarkdown content={message.content} />
                  <ChatApprovalCard message={message} />
                  <MessageFiles content={message.content} files={message.metadata?.files} />
                </div>
                <MessageActions message={message} />
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="px-6 pb-4">
        <ChatComposer prefill={prefill} />
        <p className="mt-3 text-center text-[11px] text-muted-foreground">
          Luminar is still training models. Please help us improve the results.
        </p>
      </div>
    </div>
  )
}
