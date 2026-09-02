"use client"

import { type HrActionKind, HR_ACTION_KIND } from "@/lib/hr-actions"
import { cn } from "@/lib/utils"

export type ChatApproval = {
  conversationId: string
  toolName: string
  title: string
  params: Record<string, any>
}

function shortText(text: unknown, maxChars: number): string {
  const s = typeof text === "string" ? text : ""
  const normalized = s.replace(/\s+/g, " ").trim()
  if (!normalized) return ""
  if (normalized.length <= maxChars) return normalized
  return normalized.slice(0, maxChars - 1) + "…"
}

export function ChatApprovalCard({
  approval,
  onApprove,
  onReject,
}: {
  approval: ChatApproval
  onApprove: () => void
  onReject: () => void
}) {
  const kind = (HR_ACTION_KIND as Record<string, HrActionKind>)[approval.toolName] as
    | HrActionKind
    | undefined
  const p = approval.params ?? {}

  const primaryText =
    kind === "email"
      ? "Approve sending this email?"
      : kind === "slack"
        ? "Approve sending this Slack message?"
        : kind === "teams"
          ? "Approve sending this Teams message?"
          : "Continue?"

  const continueLabel =
    kind === "email"
      ? "Continue — send email"
      : kind === "slack"
        ? "Continue — send Slack message"
        : kind === "teams"
          ? "Continue — send Teams message"
          : "Continue"

  const bodySnippet = shortText(
    kind === "email"
      ? p.body ?? p.message ?? p.text
      : p.message ?? p.body ?? p.text,
    180,
  )

  const toValue = kind === "email" && p.to ? String(p.to) : undefined
  const subjectValue = kind === "email" && p.subject ? String(p.subject) : undefined
  const recipientValue =
    kind === "slack"
      ? p.channel
        ? String(p.channel)
        : undefined
      : kind === "teams"
        ? p.recipient
          ? String(p.recipient)
          : undefined
        : undefined

  return (
    <div className={cn("w-full rounded-xl border border-border bg-card/95 p-3")}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-foreground">{primaryText}</p>
          <p className="text-[11.5px] text-muted-foreground truncate">{approval.title}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onReject}
            className="flex items-center justify-center rounded-lg border border-border bg-card px-3 py-2 text-[13px] font-medium text-foreground transition-colors hover:bg-secondary/50"
          >
            Reject
          </button>
          <button
            onClick={onApprove}
            className="flex items-center justify-center rounded-lg border border-primary/20 bg-primary px-3 py-2 text-[13px] font-semibold text-primary-foreground transition-all hover:bg-primary/90"
          >
            {continueLabel}
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-col gap-2">
        {kind === "email" && (
          <>
            {toValue && (
              <div className="flex flex-col gap-0.5">
                <span className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
                  To
                </span>
                <span className="text-[13px] text-foreground">{toValue}</span>
              </div>
            )}
            {subjectValue && (
              <div className="flex flex-col gap-0.5">
                <span className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
                  Subject
                </span>
                <span className="text-[13px] text-foreground">{subjectValue}</span>
              </div>
            )}
          </>
        )}

        {recipientValue && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
              Recipient
            </span>
            <span className="text-[13px] text-foreground">{recipientValue}</span>
          </div>
        )}

        {bodySnippet && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
              Draft preview
            </span>
            <div className="rounded-lg border border-border bg-secondary/60 p-3 text-[13px] leading-relaxed text-foreground whitespace-pre-wrap">
              {bodySnippet}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

