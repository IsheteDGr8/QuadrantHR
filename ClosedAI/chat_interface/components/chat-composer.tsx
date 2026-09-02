"use client"

import { useEffect, useRef, useState } from "react"
import {
  Plus,
  Database,
  ChevronDown,
  Sparkles,
  Mic,
  SendHorizontal,
  Command,
  Paperclip,
  ImageIcon,
  Globe,
  Check,
  X,
  Square,
} from "lucide-react"
import { OptionMenu } from "@/components/option-menu"
import { VoiceRecorder } from "@/components/voice-recorder"
import { useChat, MODELS, TONES, DATA_SOURCES } from "@/lib/chat-store"
import { useAgentRuntime } from "@/lib/agent-runtime"
import { cn } from "@/lib/utils"

interface ChatComposerProps {
  /** When this changes, the composer input is replaced with `text` and focused. */
  prefill?: { text: string; nonce: number }
}

export function ChatComposer({ prefill }: ChatComposerProps) {
  const {
    sendMessage,
    model,
    setModel,
    tone,
    setTone,
    dataSource,
    setDataSource,
    webSearch,
    toggleWebSearch,
    isRunning,
    pendingApproval,
    approvalResolving,
    composerDraft,
    clearComposerDraft,
  } = useChat()
  const { startRun, stopRun } = useAgentRuntime()
  const [input, setInput] = useState("")
  const [attachOpen, setAttachOpen] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [attachments, setAttachments] = useState<Array<{ name: string; path: string }>>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const approvalPending = !!pendingApproval || approvalResolving

  useEffect(() => {
    if (!attachOpen) return
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setAttachOpen(false)
    }
    document.addEventListener("mousedown", onClick)
    return () => document.removeEventListener("mousedown", onClick)
  }, [attachOpen])

  // Store-backed draft from intake (Open with Copilot / Route / Group).
  // sessionStorage backup survives React Strict Mode remounts.
  useEffect(() => {
    let draft = composerDraft
    if (!draft) {
      try {
        const raw = sessionStorage.getItem("hr-copilot:composer-draft")
        if (raw) draft = JSON.parse(raw) as { text: string; nonce: number }
      } catch {
        /* ignore */
      }
    }
    if (!draft?.text) return
    setInput(draft.text)
    requestAnimationFrame(() => {
      const el = textareaRef.current
      if (!el) return
      el.focus()
      el.setSelectionRange(draft!.text.length, draft!.text.length)
      el.style.height = "auto"
      el.style.height = Math.min(el.scrollHeight, 280) + "px"
    })
    if (composerDraft) clearComposerDraft()
  }, [composerDraft, clearComposerDraft])

  // Landing-page quick actions.
  useEffect(() => {
    if (!prefill) return
    setInput(prefill.text)
    const el = textareaRef.current
    if (el) {
      el.focus()
      const end = prefill.text.length
      el.setSelectionRange(end, end)
    }
  }, [prefill])

  // Auto-grow the textarea.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 280) + "px"
  }, [input])

  const handleSend = () => {
    if (isRunning || approvalPending) return
    const text = input.trim()
    if (!text && attachments.length === 0) return
    const files = attachments.map((a) => a.path)
    try {
      sessionStorage.removeItem("hr-copilot:composer-draft")
    } catch {
      /* ignore */
    }
    startRun(text || `Attached ${files.length} file${files.length === 1 ? "" : "s"}`)
    sendMessage(text, { files })
    setInput("")
    setAttachments([])
  }

  const handleStop = () => {
    stopRun()
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (approvalPending) return
    if (e.nativeEvent.isComposing || e.keyCode === 229) return
    if ((e.key === "Enter" && !e.shiftKey) || (e.key === "/" && (e.metaKey || e.ctrlKey))) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="relative">
      {isRecording && (
        <div className="mx-auto max-w-[680px]">
          <VoiceRecorder
            onCancel={() => setIsRecording(false)}
            onConfirm={(t) => {
              setInput((prev) => (prev ? prev + " " + t : t))
              setIsRecording(false)
              textareaRef.current?.focus()
            }}
          />
        </div>
      )}

      {/* Attachment menu */}
      {attachOpen && (
        <div
          ref={menuRef}
          className="dream-fade absolute bottom-full left-1/2 z-20 mb-2 w-60 -translate-x-[calc(50%+230px)] rounded-xl border border-border bg-popover p-1.5 shadow-2xl"
        >
          <button
            onClick={() => {
              fileInputRef.current?.click()
              setAttachOpen(false)
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] text-foreground transition-colors hover:bg-secondary/50"
          >
            <Paperclip className="h-4 w-4 text-muted-foreground" />
            Add photos and files
          </button>
          <button
            onClick={() => {
              setInput((p) => (p ? p : "Create an image of "))
              setAttachOpen(false)
              textareaRef.current?.focus()
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] text-foreground transition-colors hover:bg-secondary/50"
          >
            <ImageIcon className="h-4 w-4 text-muted-foreground" />
            Create Images
          </button>
          <button
            onClick={() => {
              toggleWebSearch()
              setAttachOpen(false)
            }}
            className="flex w-full items-center justify-between gap-2.5 rounded-lg px-3 py-2 text-[13px] text-foreground transition-colors hover:bg-secondary/50"
          >
            <span className="flex items-center gap-2.5">
              <Globe className="h-4 w-4 text-muted-foreground" />
              Web search
            </span>
            {webSearch && <Check className="h-3.5 w-3.5 text-foreground" />}
          </button>
        </div>
      )}

      <div className="input-3d mx-auto max-w-[680px] rounded-xl border border-border bg-card p-3">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={async (e) => {
            const selected = Array.from(e.target.files ?? [])
            if (!selected.length) return
            const uploaded: Array<{ name: string; path: string }> = []
            for (const file of selected) {
              const form = new FormData()
              form.append("file", file)
              form.append("subdir", "uploads")
              try {
                const res = await fetch("/api/workspace/upload", { method: "POST", body: form })
                if (!res.ok) continue
                const data = await res.json()
                if (data.path) uploaded.push({ name: file.name, path: data.path })
              } catch {
                /* skip failed upload */
              }
            }
            if (uploaded.length) {
              setAttachments((prev) => [...prev, ...uploaded])
            }
            e.target.value = ""
          }}
        />

        {/* Top row */}
        <div className="flex items-center justify-between">
          <button
            aria-label="Add attachment"
            onClick={() => {
              if (approvalPending) return
              setAttachOpen((v) => !v)
            }}
            disabled={approvalPending}
            className={cn(
              "text-muted-foreground transition-colors hover:text-foreground",
              attachOpen && "text-foreground",
              approvalPending && "opacity-40 cursor-not-allowed hover:text-muted-foreground",
            )}
          >
            <Plus className="h-5 w-5" />
          </button>

          <OptionMenu
            label="Data source"
            options={DATA_SOURCES}
            value={dataSource}
            onChange={setDataSource}
            align="end"
            trigger={
              <button className="flex items-center gap-1.5 rounded-md border border-border bg-secondary/40 px-2.5 py-1 text-[12px] font-medium text-foreground transition-colors hover:bg-secondary/60">
                <Database className="h-3.5 w-3.5" />
                {dataSource}
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            }
          />
        </div>

        {/* Attachment chips */}
        {(attachments.length > 0 || webSearch) && (
          <div className="mt-2 flex flex-wrap gap-2">
            {webSearch && (
              <span className="flex items-center gap-1.5 rounded-md border border-border bg-secondary/50 px-2 py-1 text-[11px] text-foreground">
                <Globe className="h-3 w-3" />
                Web search on
                <button aria-label="Turn off web search" onClick={toggleWebSearch}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
            {attachments.map((file, i) => (
              <span
                key={i}
                className="flex items-center gap-1.5 rounded-md border border-border bg-secondary/40 px-2 py-1 text-[11px] text-foreground"
              >
                <Paperclip className="h-3 w-3" />
                {file.name}
                <button
                  aria-label={`Remove ${file.name}`}
                  onClick={() => setAttachments((prev) => prev.filter((_, idx) => idx !== i))}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={approvalPending}
          className={cn(
            "mt-2 max-h-[200px] w-full resize-none bg-transparent text-[14px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground",
            approvalPending && "opacity-50 cursor-not-allowed",
          )}
          placeholder="Message Vera..."
        />

        {/* Bottom row */}
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <OptionMenu
              label="Model"
              options={MODELS.map((m) => m.label)}
              value={model}
              onChange={setModel}
              side="top"
              trigger={
                <button className="flex items-center gap-1.5 rounded-md border border-border bg-secondary/40 px-2.5 py-1 text-[12px] font-medium text-foreground transition-colors hover:bg-secondary/60">
                  <Sparkles className="h-3.5 w-3.5 text-muted-foreground" />
                  {model}
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              }
            />
            <OptionMenu
              label="Tone"
              options={TONES}
              value={tone}
              onChange={setTone}
              side="top"
              trigger={
                <button className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[12px] font-medium text-foreground transition-colors hover:text-foreground">
                  <span className="flex h-3.5 w-3.5 items-center justify-center rounded-sm border border-neutral-500 text-[9px]">
                    T
                  </span>
                  {tone === "Default" ? "Tone" : tone}
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              }
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              aria-label="Voice input"
              onClick={() => setIsRecording(true)}
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              <Mic className="h-4 w-4" />
            </button>
            {isRunning ? (
              <button
                onClick={handleStop}
                aria-label="Stop generation"
                title="Stop the current run"
                className="btn-3d flex items-center gap-2 rounded-md border border-destructive/20 bg-destructive px-3 py-1.5 text-[13px] font-medium text-destructive-foreground shadow-sm transition-all hover:bg-destructive/90"
              >
                <Square className="h-3.5 w-3.5" />
                Stop
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={(!input.trim() && attachments.length === 0) || approvalPending}
                className="btn-3d btn-glow flex items-center gap-2 rounded-md border border-primary/20 bg-primary px-3 py-1.5 text-[13px] font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary/90 disabled:opacity-40"
              >
                <SendHorizontal className="h-3.5 w-3.5" />
                Send
                <span className="flex items-center gap-0.5 text-primary-foreground/70">
                  <Command className="h-3 w-3" />
                  <span className="text-[12px]">/</span>
                </span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
