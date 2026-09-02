"use client"

import { useEffect, type ReactNode } from 'react'
import { create } from 'zustand'
// Type-only import (erased at build time, so no runtime import cycle with
// agent-runtime, which imports the store's `useChat` value).
import type { EventCategory, EventStatus } from './agent-runtime'
import { actionTitle } from './hr-actions'
import { matchKeywordSkills } from './skill-triggers'
import {
  extractFileRefs,
  extractPathsFromObservation,
  extractPathsFromToolParams,
  FILE_PRODUCING_TOOLS,
  normalizeWorkspacePath,
  uniqueFilePaths,
} from './workspace-files'
import {
  noteChatApproval,
  setChatWorkStatus,
  syncWorkFromChatActivity,
} from './chat-work-bridge'
import { redactPii, redactPiiDeep } from './pii-redact'

export type Reaction = 'up' | 'down' | null

/**
 * A single step in the agent's live reasoning stream, derived from the
 * backend's Action/Observation events. The execution panel (agent-runtime)
 * maps these into its RunEvent shape for rendering. Timestamps are absolute
 * (ms) and converted to run-relative offsets at render time.
 */
export interface ActivityStep {
  id: string
  category: EventCategory
  title: string
  detail?: string
  status: EventStatus
  createdAtMs: number
  endedAtMs?: number
  /** Backend tool_call_id, used to match an Observation back to its Action. */
  toolCallId?: string
  level?: 'info' | 'warn' | 'error' | 'debug'
  /** Raw action data for rendering approval cards if the backend pauses execution. */
  toolName?: string
  rawParams?: Record<string, any>
}

type ParkedActivity = { activity: ActivityStep[]; activityStartedAt: number | null }

function parkActivity(
  activityByChat: Record<string, ParkedActivity>,
  chatId: string | null | undefined,
  activity: ActivityStep[],
  activityStartedAt: number | null,
): Record<string, ParkedActivity> {
  if (!chatId) return activityByChat
  return {
    ...activityByChat,
    [chatId]: { activity, activityStartedAt },
  }
}

function takeParkedActivity(
  activityByChat: Record<string, ParkedActivity>,
  chatId: string | null | undefined,
): ParkedActivity {
  if (!chatId) return { activity: [], activityStartedAt: null }
  return activityByChat[chatId] ?? { activity: [], activityStartedAt: null }
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  createdAt?: number
  reaction?: Reaction
  status: 'sending' | 'sent' | 'receiving' | 'received' | 'error'
  metadata?: {
    files?: string[]
    artifacts?: unknown
    tool_calls?: unknown[]
    approval?: ChatApproval
    /** Persisted so remounts / duplicate cards don't reset to pending buttons. */
    approvalStatus?: 'pending' | 'approved' | 'rejected' | 'error'
  }
}

export interface ChatApproval {
  id: string
  conversationId: string
  toolName: string
  title: string
  params: Record<string, any>
  risk?: string
}

export interface ConversationMeta {
  id: string
  title: string
  favorite?: boolean
}

interface ChatState {
  // Active conversation (UI)
  activeConversation: Message[]
  conversations: ConversationMeta[]
  activeId: string | null

  // Per-chat history and backend binding (persisted to localStorage). The
  // active chat's messages live in `activeConversation`; the others are parked
  // here and swapped in on selection. `backendIdByChat` maps a UI chat to its
  // reused backend conversation id so context survives across messages/reloads.
  messagesByChat: Record<string, Message[]>
  backendIdByChat: Record<string, string>
  /** Last activity feed per chat — restored when switching conversations. */
  activityByChat: Record<string, { activity: ActivityStep[]; activityStartedAt: number | null }>

  // Run state
  isRunning: boolean
  error: string | null

  // Live agent reasoning steps for the current turn (execution panel / feed).
  activity: ActivityStep[]
  activityStartedAt: number | null

  // HITL: backend paused on ConfirmRisky. Composer disables send while set.
  pendingApproval: ChatApproval | null
  approvalResolving: boolean

  // Backend (HRAgents agent server) connection
  backendConversationId: string | null
  socket: WebSocket | null
  backendConnected: boolean
  connectionError: string | null

  // Settings
  model: string
  tone: string
  dataSource: string
  webSearch: boolean

  // UI state
  sidebarOpen: boolean
  sidebarWidth: number
  agent: string
  /** True after localStorage hydrate finishes (or determines there is nothing to load). */
  sessionHydrated: boolean
  /** Intake/skills draft sitting in the composer — not sent until the user hits Send. */
  composerDraft: { text: string; nonce: number } | null

  // Actions
  sendMessage: (content: string, opts?: { files?: string[] }) => Promise<void>
  cancelRun: () => void
  clearConversation: () => void
  approvePendingApproval: () => Promise<void>
  rejectPendingApproval: () => Promise<void>
  setModel: (model: string) => void
  setTone: (tone: string) => void
  setDataSource: (source: string) => void
  toggleWebSearch: () => void
  setSidebarOpen: (open: boolean) => void
  setSidebarWidth: (width: number) => void
  setAgent: (agent: string) => void
  newChat: () => void
  /** Start a blank chat and put `text` in the composer (do not send). */
  openChatWithDraft: (text: string) => void
  clearComposerDraft: () => void
  selectConversation: (id: string) => void
  deleteConversation: (id: string) => void
  toggleFavorite: (id: string) => void
  reactToMessage: (messageId: string, reaction: 'up' | 'down') => void
  /** Open a shared snapshot as a local conversation and select it. */
  openSharedChat: (payload: {
    shareId: string
    title: string
    messages: Array<{
      id?: string
      role: 'user' | 'assistant' | 'system'
      content: string
      createdAt?: number
      timestamp?: number
      status?: Message['status']
      metadata?: Message['metadata']
    }>
  }) => string
  hydrate: () => void
}

const MODELS = [
  { label: 'GPT-5.2', value: 'gpt-5.2' },
  { label: 'GPT-4o', value: 'gpt-4o' },
  { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet' },
  { label: 'Claude 3 Opus', value: 'claude-3-opus' },
]

const TONES = [
  'Default',
  'Professional',
  'Friendly',
  'Technical',
  'Creative',
  'Analytical',
]

const DATA_SOURCES = [
  'Internal Knowledge',
  'Web Search',
  'Both',
]

// Browser-reachable base for the backend event WebSocket. The REST calls that
// carry secrets (creating the conversation with the Azure LLM config) go
// through the Next.js server route instead, so no credentials touch the client.
const WS_BASE =
  process.env.NEXT_PUBLIC_HRAGENT_WS_URL?.replace(/\/$/, '') || 'ws://127.0.0.1:8001'

// Optional token for the browser's event WebSocket, used only when the backend
// is started with SESSION_API_KEY. Sent as a first-message auth frame. NOTE:
// because it is a NEXT_PUBLIC_ value it is visible to the browser; treat this
// as a network-scoped (VPN/internal) control, not a real secret. A short-lived
// minted token / WS proxy is tracked for the hardening phase. Empty = the
// backend is open (local testing default) and no auth frame is sent.
const WS_TOKEN = process.env.NEXT_PUBLIC_HRAGENT_WS_TOKEN || ''

const CONNECT_TIMEOUT_MS = 20000

// Whether the agent produced any visible text during the current turn. Used to
// decide if we need the final-response fallback when the run finishes. The UI
// only runs one turn at a time, so a module-scoped flag is sufficient.
let sawAgentTextThisTurn = false

// Id of the assistant message currently being built from streaming token
// deltas, if any. Null when we are not mid-stream. Reset each turn.
let streamingMessageId: string | null = null

// Live text-generation step in the activity feed. When the agent answers with
// plain text (no tool call to render), the feed would otherwise stay empty for
// the whole turn; we keep one "responding…" step that is born on the first
// streamed token and closes when the run reaches a terminal state.
let respondingStepId: string | null = null
let respondTextBuffer = ''
let respondLastPaintedAt = 0

// De-dupe WS frames within a conversation (safety-net behavior). Cleared when
// the backend conversation id changes, not on every user send.
let seenEventIds = new Set<string>()
let seenEventIdsForConversation: string | null = null

// Workspace files produced this turn (write_workspace_file, office_fill_*, …).
// Attached to the assistant message as metadata.files so chips render even
// when the model wording is vague.
let turnGeneratedFiles = new Set<string>()

/** The assistant text bubble created for the current user turn (not approval cards). */
let turnAssistantMessageId: string | null = null

/** Tool call id we already surfaced an approval card for (prevents duplicate cards). */
let approvalShownForToolCallId: string | null = null

/** Last ActionEvent this turn — status updates can arrive before the action frame. */
let lastActionForApproval: {
  toolName: string
  toolCallId?: string
  params: Record<string, unknown>
} | null = null
let confirmationStatusSeen = false

function rememberTurnFiles(paths: string[]) {
  for (const p of paths) {
    if (p) turnGeneratedFiles.add(p)
  }
}

function consumeTurnFiles(): string[] | undefined {
  if (turnGeneratedFiles.size === 0) return undefined
  const files = Array.from(turnGeneratedFiles)
  return files
}

function mergeFilesOntoMessage(messageId: string, set: Setter) {
  const files = consumeTurnFiles()
  if (!files?.length) return
  set((state) => ({
    activeConversation: state.activeConversation.map((m) => {
      if (m.id !== messageId) return m
      const existing = m.metadata?.files || []
      const merged = uniqueFilePaths([...existing, ...files, ...extractFileRefs(m.content)])
      return {
        ...m,
        metadata: { ...m.metadata, files: merged },
      }
    }),
  }))
}

// A turn is terminal when the backend stops producing for it. Besides the
// explicit failures, a user-initiated interrupt lands here too: the backend
// reports `paused` (and may later resume on the next message). Without these,
// the activity feed's running steps and the streamed bubble would never be
// finalized after a Stop, leaving the sidebar stuck on "running".
const TERMINAL_STATUSES = new Set(['finished', 'error', 'stuck', 'paused', 'interrupted', 'stopped'])
// Statuses that represent a user-cancelled turn rather than a failure: closing
// steps as errors would mislead the activity feed.
const USER_CANCEL_STATUSES = new Set(['paused', 'interrupted', 'stopped'])

// hr-mcp tools that read structured data (Azure SQL later) vs. policy RAG.
const DATA_TOOLS = new Set(['employee_lookup', 'pto_balance', 'org_chart', 'benefits_lookup'])

const TOOL_LABELS: Record<string, string> = {
  employee_lookup: 'Looking up employee record',
  pto_balance: 'Checking PTO balance',
  org_chart: 'Fetching org chart',
  benefits_lookup: 'Looking up benefits',
  list_emails: 'Reading Gmail inbox',
  list_slack_channels: 'Listing Slack channels',
  send_email: 'Sending email',
  send_slack_message: 'Sending Slack message',
  send_teams_message: 'Sending Teams message',
  invoke_skill: 'Executing HR skill',
}

const MCP_TOOL_LABELS: Record<string, string> = {
  query_cosmos: 'Querying Cosmos DB',
  list_collections: 'Listing Cosmos DB containers',
  describe_container: 'Describing Cosmos DB container',
  find_implied_links: 'Finding Cosmos DB relationships',
  get_sample_documents: 'Sampling Cosmos DB documents',
  count_documents: 'Counting Cosmos DB documents',
  get_partition_key_info: 'Reading Cosmos DB partition key',
  get_indexing_policy: 'Reading Cosmos DB indexing policy',
  list_distinct_values: 'Listing Cosmos DB field values',
  query: 'Searching Azure AI Search',
  list_indexes: 'Listing Azure AI Search indexes',
  get_index: 'Reading Azure AI Search index',
  list_formats: 'Listing supported document formats',
  get_document_info: 'Reading document metadata',
  office_read: 'Reading document contents',
  office_validate: 'Validating document integrity',
  office_diff_documents: 'Comparing documents',
  office_check_consistency: 'Checking document consistency',
  office_export_pdf: 'Exporting document to PDF',
  office_list_pdf_fields: 'Listing PDF form fields',
  office_fill_pdf_form: 'Filling PDF form fields',
  office_analyze_pdf_layout: 'Analyzing PDF layout',
  office_overlay_pdf_text: 'Overlaying text on PDF',
  office_template_detect: 'Detecting DOCX template fields',
  office_template_fill: 'Filling DOCX template',
  office_template_batch: 'Batch-filling DOCX templates',
}

// Map a backend tool name to the execution panel's visual category so the
// reasoning stepper shows a sensible icon (DB lookup vs. knowledge search).
function categoryForTool(name: string): EventCategory {
  if (name === 'policy_search') return 'memory'
  if (name === 'invoke_skill') return 'skill'
  if (DATA_TOOLS.has(name)) return 'database'
  if (name === 'think') return 'step'
  return 'tool'
}

function truncate(text: string, max = 140): string {
  const t = text.replace(/\s+/g, ' ').trim()
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

// Extract a tool call's real arguments from the ActionEvent `action` payload.
// MCP tools nest args under `data`; client tools carry them top-level. Either
// way, drop the SDK meta fields (kind / summary / security_risk).
function extractActionParams(action: any): Record<string, any> {
  if (!action || typeof action !== 'object') return {}
  const base =
    action.data && typeof action.data === 'object' && !Array.isArray(action.data)
      ? action.data
      : action
  const out: Record<string, any> = {}
  for (const [k, v] of Object.entries(base)) {
    if (k === 'kind' || k === 'summary' || k === 'security_risk') continue
    out[k] = v
  }
  return out
}

// Compact "key: value, key: value" summary of a tool call's arguments for the
// step's detail line.
function argsSummary(action: any): string | undefined {
  const entries = Object.entries(extractActionParams(action))
  if (entries.length === 0) return undefined
  const parts = entries.map(
    ([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`,
  )
  return truncate(parts.join(', '), 120)
}

function observationText(observation: any): string {
  const content = observation?.content
  if (!Array.isArray(content)) return ''
  return content
    .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
    .map((c) => c.text)
    .join(' ')
    .trim()
}

function readActivatedSkills(evt: any): string[] {
  const raw = evt?.activated_skills
  if (!Array.isArray(raw)) return []
  return raw
    .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
    .map((s) => s.trim())
}

function skillNameFromAction(evt: any): string | undefined {
  const name = extractActionParams(evt?.action).name
  return typeof name === 'string' && name.trim() ? name.trim() : undefined
}

function observationSkillName(observation: any): string | undefined {
  const name = observation?.skill_name
  return typeof name === 'string' && name.trim() ? name.trim() : undefined
}

function formatSkillTitle(name: string, mode: 'activated' | 'invoking'): string {
  const label = truncate(name, 80)
  return mode === 'activated' ? `Activated skill: ${label}` : `Invoking skill: ${label}`
}

function skillNamesInActivity(activity: ActivityStep[]): Set<string> {
  const names = new Set<string>()
  for (const step of activity) {
    if (step.category !== 'skill') continue
    const fromParams = step.rawParams?.name
    if (typeof fromParams === 'string' && fromParams.trim()) {
      names.add(fromParams.trim())
      continue
    }
    const m =
      /^Activated skill: (.+)$/.exec(step.title) || /^Invoking skill: (.+)$/.exec(step.title)
    if (m?.[1]) names.add(m[1].trim())
  }
  return names
}

function pushActivatedSkillSteps(set: Setter, skillNames: string[], existing?: ActivityStep[]) {
  if (skillNames.length === 0) return
  const already = skillNamesInActivity(existing ?? [])
  const toAdd = skillNames.filter((n) => !already.has(n))
  if (toAdd.length === 0) return
  const now = Date.now()
  set((state) => {
    const present = skillNamesInActivity(state.activity)
    const steps: ActivityStep[] = []
    for (const name of toAdd) {
      if (present.has(name)) continue
      present.add(name)
      steps.push({
        id: newId('skill'),
        category: 'skill',
        title: formatSkillTitle(name, 'activated'),
        detail: 'Matched keyword trigger in your message',
        status: 'success',
        createdAtMs: now,
        endedAtMs: now,
        toolName: 'skill_trigger',
        rawParams: { name },
      })
    }
    return steps.length > 0 ? { activity: [...state.activity, ...steps] } : {}
  })
}

function pushInvokeSkillActionStep(set: Setter, evt: any, existing?: ActivityStep[]) {
  const params = extractActionParams(evt?.action)
  const name =
    (typeof params.name === 'string' ? params.name.trim() : '') || skillNameFromAction(evt) || ''
  if (!name) return
  const already = skillNamesInActivity(existing ?? [])
  if (already.has(name)) return
  const toolCallId = typeof evt?.tool_call_id === 'string' ? evt.tool_call_id : undefined
  pushActivity(set, {
    id: newId('act'),
    category: 'skill',
    title: formatSkillTitle(name, 'invoking'),
    detail: detailForAction('invoke_skill', evt, params),
    status: 'running',
    createdAtMs: Date.now(),
    toolCallId,
    toolName: 'invoke_skill',
    rawParams: params,
  })
}

function detailForAction(
  toolName: string,
  evt: any,
  params: Record<string, any>,
): string | undefined {
  if (toolName === 'invoke_skill') {
    const name =
      typeof params.name === 'string' ? params.name.trim() : skillNameFromAction(evt)
    return name ? `Loading skill: ${truncate(name, 80)}` : argsSummary(evt.action)
  }
  return argsSummary(evt.action)
}

function titleForAction(evt: any): string {
  const toolName: string = evt?.tool_name || 'tool'
  if (toolName === 'think') {
    const thought = evt?.action?.thought
    if (typeof thought === 'string' && thought.trim()) return truncate(thought)
    return 'Thinking'
  }
  if (toolName === 'invoke_skill') {
    const name = skillNameFromAction(evt)
    if (name) return formatSkillTitle(name, 'invoking')
  }
  const summary = typeof evt?.summary === 'string' ? evt.summary.trim() : ''
  if (summary) return truncate(summary)
  return TOOL_LABELS[toolName] || MCP_TOOL_LABELS[toolName] || `Calling ${toolName}`
}

function newId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

// Chat title from the first user message: first line, trimmed to a sane length.
function titleFromText(text: string): string {
  const firstLine = text.split('\n')[0].trim()
  if (firstLine.length <= 48) return firstLine || 'New Chat'
  return `${firstLine.slice(0, 45).trimEnd()}…`
}

function textFromLlmMessage(llmMessage: any): string {
  if (!llmMessage) return ''
  const content = llmMessage.content
  if (typeof content === 'string') return content.trim()
  if (Array.isArray(content)) {
    return content
      .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
      .map((c) => c.text)
      .join('\n')
      .trim()
  }
  return ''
}

function readExecutionStatus(evt: any): string | undefined {
  const value = evt?.value
  if (evt?.key === 'execution_status') {
    return typeof value === 'string' ? value : value?.execution_status
  }
  if (value && typeof value === 'object') return value.execution_status
  return undefined
}

export const useChat = create<ChatState>((set, get) => ({
  // Initial state
  activeConversation: [],
  conversations: [],
  activeId: null,
  messagesByChat: {},
  backendIdByChat: {},
  activityByChat: {},
  isRunning: false,
  error: null,

  activity: [],
  activityStartedAt: null,

  pendingApproval: null,
  approvalResolving: false,

  backendConversationId: null,
  socket: null,
  backendConnected: false,
  connectionError: null,

  model: MODELS[0].label,
  tone: 'Default',
  dataSource: 'Internal Knowledge',
  webSearch: false,
  sidebarOpen: true,
  sidebarWidth: 320,
  agent: 'Vera',
  sessionHydrated: false,
  composerDraft: null,

  sendMessage: async (content: string, opts?: { files?: string[] }) => {
    const files = uniqueFilePaths(
      (opts?.files || [])
        .map((p) => normalizeWorkspacePath(p) || p.trim())
        .filter(Boolean),
    )
    const base = content.trim()
    const attachmentNote =
      files.length > 0
        ? `\n\nAttached files:\n${files.map((p) => `- ${p}`).join('\n')}`
        : ''
    // Keep an existing note if the caller already appended one; otherwise add ours.
    const outgoing =
      (base && /Attached files:/i.test(base)
        ? base
        : `${base}${attachmentNote}`.trim()) ||
      (files.length ? `Attached files:\n${files.map((p) => `- ${p}`).join('\n')}` : '')
    if (!outgoing) return
    // One turn at a time: never queue a new prompt while the previous agent run
    // is still in flight. The composer shows a Stop button while running, so
    // the user can interrupt instead. Guarding here (not just in the UI) makes
    // the rule hold for every caller and is the single source of truth.
    if (get().isRunning) return

    // Prefer explicit paths; fall back to parsing any note already in content.
    const messageFiles = files.length ? files : extractFileRefs(outgoing)

    const now = new Date()
    const userMessage: Message = {
      id: newId('user'),
      role: 'user',
      content: outgoing,
      timestamp: now,
      createdAt: now.getTime(),
      reaction: null,
      status: 'sent',
      metadata: messageFiles.length ? { files: messageFiles } : undefined,
    }

    set((state) => {
      // Ensure a chat exists (messages sent from the landing screen have no
      // active chat yet) and give it a title from the first user message.
      let activeId = state.activeId
      let conversations = state.conversations
      if (!activeId) {
        activeId = `chat-${Date.now()}`
        conversations = [{ id: activeId, title: titleFromText(base || outgoing) }, ...conversations]
      } else if (state.activeConversation.every((m) => m.role !== 'user')) {
        conversations = conversations.map((c) =>
          c.id === activeId && c.title === 'New Chat'
            ? { ...c, title: titleFromText(base || outgoing) }
            : c,
        )
      }
      return {
        activeId,
        conversations,
        activeConversation: [...state.activeConversation, userMessage],
        isRunning: true,
        error: null,
        // Start a fresh reasoning stream for this turn.
        activity: [],
        activityStartedAt: now.getTime(),
      }
    })

    // Work Queue only for substantial runs (skills/MCP/tools) — not "Hi there".
    // Promotion happens from Action/Observation/approval/finish via syncWorkFromChatActivity.

    sawAgentTextThisTurn = false
    streamingMessageId = null
    turnAssistantMessageId = null
    approvalShownForToolCallId = null
    lastActionForApproval = null
    confirmationStatusSeen = false
    turnGeneratedFiles = new Set()
    resetRespondingStep()
    // Immediate skill-activity feedback (safety-net); backend MessageEvent may lag.
    pushActivatedSkillSteps(set, matchKeywordSkills(outgoing))

    try {
      const socket = await ensureSocket(get, set)
      socket.send(
        JSON.stringify({
          role: 'user',
          content: [{ type: 'text', text: outgoing }],
        }),
      )
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Failed to reach HR Agent'
      // New Chat / switch mid-connect — don't dump an error into the new blank chat.
      if (detail.includes('Chat changed before')) {
        set({ isRunning: false, error: null })
        return
      }
      appendSystem(set, `Error: ${detail}`)
      set({ isRunning: false, error: detail, connectionError: detail })
    }
  },

  cancelRun: () => {
    const { backendConversationId } = get()
    set({ isRunning: false, pendingApproval: null, approvalResolving: false })
    if (backendConversationId) {
      // Best-effort interrupt of the running backend conversation.
      fetch('/api/chat', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversationId: backendConversationId }),
      }).catch(() => {})
    }
  },

  clearConversation: () => {
    streamingMessageId = null
    resetRespondingStep()
    set({
      activeConversation: [],
      error: null,
      activity: [],
      activityStartedAt: null,
      pendingApproval: null,
      approvalResolving: false,
    })
  },

  approvePendingApproval: async () => {
    const pending = get().pendingApproval
    if (!pending) return
    set({ pendingApproval: null, approvalResolving: true })
    resumeAwaitingApprovalSteps(set, 'Approved — executing…')
    stampApprovalMessages(set, 'approved')
    try {
      const res = await fetch('/api/chat/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversationId: pending.conversationId,
          accept: true,
        }),
      })
      if (!res.ok) throw new Error('Failed to approve action')
      set({ approvalResolving: false, isRunning: true })
      const chatId = get().activeId
      if (chatId) mirrorWorkQueue(get, 'running')
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Approval failed'
      appendSystem(set, `Error: ${detail}`)
      closeAwaitingApprovalSteps(set, 'error', detail)
      set({ approvalResolving: false, pendingApproval: pending })
    }
  },

  rejectPendingApproval: async () => {
    const pending = get().pendingApproval
    if (!pending) return
    set({ pendingApproval: null, approvalResolving: true })
    closeAwaitingApprovalSteps(set, 'warn', 'Rejected — nothing was sent')
    stampApprovalMessages(set, 'rejected')
    try {
      const res = await fetch('/api/chat/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversationId: pending.conversationId,
          accept: false,
          reason: 'User rejected the action.',
        }),
      })
      if (!res.ok) throw new Error('Failed to reject action')
      set({ approvalResolving: false })
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Rejection failed'
      appendSystem(set, `Error: ${detail}`)
      set({ approvalResolving: false, pendingApproval: pending })
    }
  },

  setModel: (model: string) => set({ model }),
  setTone: (tone: string) => set({ tone }),
  setDataSource: (dataSource: string) => set({ dataSource }),
  toggleWebSearch: () => set((state) => ({ webSearch: !state.webSearch })),
  setSidebarOpen: (sidebarOpen: boolean) => set({ sidebarOpen }),
  setSidebarWidth: (sidebarWidth: number) => set({ sidebarWidth }),
  setAgent: (agent: string) => set({ agent }),

  reactToMessage: (messageId: string, reaction: 'up' | 'down') => {
    set((state) => ({
      activeConversation: state.activeConversation.map((message) =>
        message.id === messageId
          ? { ...message, reaction: message.reaction === reaction ? null : reaction }
          : message,
      ),
    }))
  },

  newChat: () => {
    const { activeId, activeConversation, conversations, messagesByChat } = get()

    const isEmptyNewChat = (id: string, liveMessages?: Message[]) => {
      const meta = conversations.find((c) => c.id === id)
      if (meta?.title !== 'New Chat') return false
      if (liveMessages) return liveMessages.length === 0
      return (messagesByChat[id]?.length ?? 0) === 0
    }

    // Already on a blank New Chat — no-op (avoid connection reset / landing flicker).
    if (activeId && isEmptyNewChat(activeId, activeConversation)) {
      return
    }

    // Prefer reusing an existing blank New Chat over creating another.
    const existingEmpty = conversations.find(
      (c) => c.id !== activeId && isEmptyNewChat(c.id),
    )

    const existing = get().socket
    if (existing) {
      try {
        existing.onopen = null
        existing.onmessage = null
        existing.onclose = null
        existing.onerror = null
        existing.close()
      } catch {
        /* ignore */
      }
    }
    streamingMessageId = null
    turnAssistantMessageId = null
    approvalShownForToolCallId = null
    lastActionForApproval = null
    confirmationStatusSeen = false
    resetRespondingStep()

    if (existingEmpty) {
      set((state) => {
        const nextMessages = { ...state.messagesByChat }
        if (activeId) nextMessages[activeId] = activeConversation
        const activityByChat = parkActivity(
          state.activityByChat,
          activeId,
          state.activity,
          state.activityStartedAt,
        )
        return {
          socket: null,
          backendConnected: false,
          backendConversationId: null,
          messagesByChat: nextMessages,
          activityByChat,
          activeId: existingEmpty.id,
          activeConversation: nextMessages[existingEmpty.id] ?? [],
          error: null,
          isRunning: false,
          activity: [],
          activityStartedAt: null,
          pendingApproval: null,
          approvalResolving: false,
        }
      })
      return
    }

    const id = `chat-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    set((state) => {
      const nextMessages = { ...state.messagesByChat }
      if (activeId) nextMessages[activeId] = activeConversation
      const activityByChat = parkActivity(
        state.activityByChat,
        activeId,
        state.activity,
        state.activityStartedAt,
      )
      return {
        socket: null,
        backendConnected: false,
        backendConversationId: null,
        messagesByChat: nextMessages,
        activityByChat,
        activeConversation: [],
        activeId: id,
        conversations: [
          { id, title: 'New Chat' },
          ...state.conversations.filter(
            (c) =>
              !(
                c.title === 'New Chat' &&
                (nextMessages[c.id]?.length === 0 || !nextMessages[c.id])
              ),
          ),
        ],
        error: null,
        isRunning: false,
        activity: [],
        activityStartedAt: null,
        pendingApproval: null,
        approvalResolving: false,
      }
    })
  },

  openChatWithDraft: (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    get().newChat()
    const draft = { text: trimmed, nonce: Date.now() }
    try {
      sessionStorage.setItem('hr-copilot:composer-draft', JSON.stringify(draft))
    } catch {
      /* ignore */
    }
    set({
      composerDraft: draft,
      isRunning: false,
      error: null,
      pendingApproval: null,
      approvalResolving: false,
    })
  },

  clearComposerDraft: () => set({ composerDraft: null }),

  selectConversation: (id: string) => {
    const { activeId, activeConversation } = get()
    if (id === activeId) return
    // Close the old socket without blanking backendConversationId first —
    // SideCanvas needs the restored id immediately to poll canvas state.
    const existing = get().socket
    if (existing) {
      try {
        existing.onopen = null
        existing.onmessage = null
        existing.onclose = null
        existing.onerror = null
        existing.close()
      } catch {
        /* ignore */
      }
    }
    streamingMessageId = null
    resetRespondingStep()
    set((state) => {
      const messagesByChat = { ...state.messagesByChat }
      if (activeId) messagesByChat[activeId] = activeConversation
      const activityByChat = parkActivity(
        state.activityByChat,
        activeId,
        state.activity,
        state.activityStartedAt,
      )
      const restored = takeParkedActivity(activityByChat, id)
      return {
        socket: null,
        backendConnected: false,
        messagesByChat,
        activityByChat,
        activeId: id,
        // Restore this chat's history; the backend conversation is rebound
        // lazily (reconnected) on the next message.
        activeConversation: messagesByChat[id] ?? [],
        backendConversationId: state.backendIdByChat[id] ?? null,
        error: null,
        isRunning: false,
        activity: restored.activity,
        activityStartedAt: restored.activityStartedAt,
        pendingApproval: null,
        approvalResolving: false,
      }
    })
  },

  deleteConversation: (id: string) => {
    const conversations = get().conversations.filter((c) => c.id !== id)
    const isActive = get().activeId === id
    const nextActiveId = isActive ? (conversations[0]?.id ?? null) : get().activeId
    if (isActive) {
      resetConnection(get, set)
      streamingMessageId = null
      resetRespondingStep()
    }
    set((state) => {
      const messagesByChat = { ...state.messagesByChat }
      delete messagesByChat[id]
      const backendIdByChat = { ...state.backendIdByChat }
      delete backendIdByChat[id]
      const activityByChat = { ...state.activityByChat }
      delete activityByChat[id]
      const restored = takeParkedActivity(activityByChat, nextActiveId)
      return {
        conversations,
        messagesByChat,
        backendIdByChat,
        activityByChat,
        activeId: nextActiveId,
        ...(isActive
          ? {
              activeConversation: nextActiveId ? (messagesByChat[nextActiveId] ?? []) : [],
              backendConversationId: nextActiveId
                ? (backendIdByChat[nextActiveId] ?? null)
                : null,
              error: null,
              isRunning: false,
              activity: restored.activity,
              activityStartedAt: restored.activityStartedAt,
            }
          : {}),
      }
    })
  },

  toggleFavorite: (id: string) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, favorite: !c.favorite } : c,
      ),
    }))
  },

  openSharedChat: (payload) => {
    const id = `shared-${payload.shareId}`
    const now = Date.now()
    const messages: Message[] = (payload.messages || []).map((m, i) => ({
      id: m.id || `shared-msg-${i}`,
      role: m.role,
      content: m.content || '',
      timestamp: new Date(m.timestamp ?? m.createdAt ?? now),
      createdAt: m.createdAt ?? m.timestamp ?? now,
      reaction: null,
      status: (m.status as Message['status']) || 'received',
      metadata: m.metadata,
    }))
    const title = (payload.title || 'Shared chat').trim() || 'Shared chat'

    resetConnection(get, set)
    streamingMessageId = null
    turnAssistantMessageId = null
    resetRespondingStep()

    set((state) => {
      const messagesByChat = { ...state.messagesByChat }
      if (state.activeId) messagesByChat[state.activeId] = state.activeConversation
      messagesByChat[id] = messages
      const activityByChat = parkActivity(
        state.activityByChat,
        state.activeId,
        state.activity,
        state.activityStartedAt,
      )

      const exists = state.conversations.some((c) => c.id === id)
      const conversations = exists
        ? state.conversations.map((c) => (c.id === id ? { ...c, title } : c))
        : [{ id, title }, ...state.conversations]

      return {
        conversations,
        messagesByChat,
        activityByChat,
        activeId: id,
        activeConversation: messages,
        backendConversationId: null,
        error: null,
        isRunning: false,
        activity: [],
        activityStartedAt: null,
      }
    })
    return id
  },

  hydrate: () => hydrateFromStorage(set),
}))

type Getter = typeof useChat.getState
type Setter = (partial: Partial<ChatState> | ((state: ChatState) => Partial<ChatState>)) => void

function upsertAssistant(set: Setter, text: string) {
  const trimmed = text.trim()
  if (!trimmed) return
  const messages = useChat.getState().activeConversation

  // Prefer updating the bubble created for THIS turn (streaming or prior MessageEvent).
  const turnMsg = turnAssistantMessageId
    ? messages.find((m) => m.id === turnAssistantMessageId)
    : null
  if (turnMsg) {
    set((state) => ({
      activeConversation: state.activeConversation.map((m) =>
        m.id === turnMsg.id
          ? { ...m, content: text, status: 'received' as Message['status'] }
          : m,
      ),
    }))
    mergeFilesOntoMessage(turnMsg.id, set)
    sawAgentTextThisTurn = true
    return
  }

  const last = messages.at(-1)
  if (last?.role === 'assistant' && last.status === 'receiving') {
    streamingMessageId = last.id
    turnAssistantMessageId = last.id
    finalizeStreaming(set, text)
    return
  }

  // One text reply per user turn: if we already rendered an assistant bubble
  // after the latest user message, update it instead of appending a duplicate
  // (MessageEvent + streamed replay often differ slightly in wording).
  const lastUserIdx = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return i
    }
    return -1
  })()
  const priorInTurn = messages
    .slice(lastUserIdx + 1)
    .filter((m) => m.role === 'assistant' && !m.metadata?.approval)
  const existingInTurn = priorInTurn.at(-1)
  if (existingInTurn) {
    turnAssistantMessageId = existingInTurn.id
    set((state) => ({
      activeConversation: state.activeConversation.map((m) =>
        m.id === existingInTurn.id
          ? { ...m, content: text, status: 'received' as Message['status'] }
          : m,
      ),
    }))
    mergeFilesOntoMessage(existingInTurn.id, set)
    sawAgentTextThisTurn = true
    return
  }

  // Never overwrite an approval card — those are separate UI messages.
  if (last?.metadata?.approval) {
    appendAssistant(set, text)
    return
  }

  // Exact duplicate already in history — don't spawn a new bubble (old replies
  // sometimes get re-delivered via final-response fallback / WS replay).
  const existingSame = messages.find(
    (m) => m.role === 'assistant' && !m.metadata?.approval && m.content.trim() === trimmed,
  )
  if (existingSame) {
    if (turnAssistantMessageId === existingSame.id || !turnAssistantMessageId) {
      if (!turnAssistantMessageId) turnAssistantMessageId = existingSame.id
      mergeFilesOntoMessage(existingSame.id, set)
    }
    sawAgentTextThisTurn = true
    return
  }

  appendAssistant(set, text)
}

function appendAssistant(set: Setter, text: string) {
  const trimmed = redactPii(text).trim()
  if (!trimmed) return

  // Guard against stale final-response / replay injecting a prior turn's answer.
  const messages = useChat.getState().activeConversation
  if (
    messages.some(
      (m) => m.role === 'assistant' && !m.metadata?.approval && m.content.trim() === trimmed,
    )
  ) {
    sawAgentTextThisTurn = true
    return
  }

  const now = new Date()
  const fromTools = consumeTurnFiles() || []
  const fromText = extractFileRefs(text)
  const files = uniqueFilePaths([...fromTools, ...fromText])
  const id = newId('assistant')
  turnAssistantMessageId = id
  sawAgentTextThisTurn = true
  const message: Message = {
    id,
    role: 'assistant',
    content: trimmed,
    timestamp: now,
    createdAt: now.getTime(),
    reaction: null,
    status: 'received',
    metadata: files.length ? { files } : undefined,
  }
  set((state) => ({ activeConversation: [...state.activeConversation, message] }))
}

function appendApprovalRequest(set: Setter, approval: Omit<ChatApproval, 'id'>, toolCallId?: string) {
  // One approval card per pause. Duplicate waiting_for_confirmation events
  // (and re-entry after running) previously spawned multiple cards.
  if (toolCallId && approvalShownForToolCallId === toolCallId) return
  if (getPendingApprovalOpen(useChat.getState().activeConversation)) return
  if (useChat.getState().pendingApproval) return

  if (toolCallId) approvalShownForToolCallId = toolCallId

  const now = new Date()
  const id = newId('approval')
  const full: ChatApproval = {
    ...approval,
    id,
    title: redactPii(approval.title),
    params: redactPiiDeep(approval.params || {}),
  }
  const message: Message = {
    id,
    role: 'assistant',
    content:
      'I prepared an action that needs your approval before it can continue. Review the draft/details in the Canvas, then approve or reject it here.',
    timestamp: now,
    createdAt: now.getTime(),
    reaction: null,
    status: 'received',
    metadata: {
      approval: full,
    },
  }
  set((state) => ({
    activeConversation: [...state.activeConversation, message],
    pendingApproval: full,
    approvalResolving: false,
    isRunning: false,
  }))
}

function getPendingApprovalOpen(messages: Message[]): boolean {
  // Only the latest approval bubble matters — older ones may lack approvalStatus
  // from before we persisted it.
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (!m.metadata?.approval) continue
    const s = m.metadata.approvalStatus
    if (s === 'approved' || s === 'rejected') return false
    return true
  }
  return false
}

function pushActivity(set: Setter, step: ActivityStep) {
  const safe: ActivityStep = {
    ...step,
    title: redactPii(step.title),
    detail: step.detail != null ? redactPii(step.detail) : step.detail,
    rawParams: step.rawParams ? redactPiiDeep(step.rawParams) : step.rawParams,
  }
  set((state) => ({ activity: [...state.activity, safe] }))
}

// Patch the most recent still-open step matching a tool_call_id (an
// Observation/error responding to an earlier Action). HITL pauses flip the
// step to `warn` ("Awaiting approval"); we must still match those or the
// activity panel never leaves that state after Approve & Send.
function updateActivityByToolCall(
  set: Setter,
  toolCallId: string | undefined,
  patch: Partial<ActivityStep>,
): boolean {
  if (!toolCallId) return false
  let matched = false
  set((state) => {
    let done = false
    const activity = state.activity.map((s) => {
      const open =
        s.status === 'running' || (s.status === 'warn' && s.endedAtMs == null)
      if (!done && s.toolCallId === toolCallId && open) {
        done = true
        matched = true
        const next = { ...s, ...patch }
        if (typeof next.detail === 'string') next.detail = redactPii(next.detail)
        if (typeof next.title === 'string') next.title = redactPii(next.title)
        return next
      }
      return s
    })
    return done ? { activity } : {}
  })
  return matched
}

function isAwaitingApprovalStep(s: ActivityStep): boolean {
  if (s.status !== 'warn' || s.endedAtMs != null) return false
  return /awaiting approval/i.test(s.detail || '')
}

function resumeAwaitingApprovalSteps(set: Setter, detail: string) {
  const safe = redactPii(detail)
  set((state) => ({
    activity: state.activity.map((s) =>
      isAwaitingApprovalStep(s)
        ? { ...s, status: 'running' as EventStatus, detail: safe, endedAtMs: undefined }
        : s,
    ),
  }))
}

function closeAwaitingApprovalSteps(set: Setter, status: EventStatus, detail: string) {
  const now = Date.now()
  const safe = redactPii(detail)
  set((state) => ({
    activity: state.activity.map((s) =>
      isAwaitingApprovalStep(s)
        ? { ...s, status, endedAtMs: now, detail: safe }
        : s,
    ),
  }))
}

function stampApprovalMessages(
  set: Setter,
  next: 'approved' | 'rejected',
) {
  set((state) => ({
    activeConversation: state.activeConversation.map((m) => {
      if (!m.metadata?.approval) return m
      if (m.metadata.approvalStatus === 'approved' || m.metadata.approvalStatus === 'rejected') {
        return m
      }
      return { ...m, metadata: { ...m.metadata, approvalStatus: next } }
    }),
  }))
}

function markRunningStepsError(set: Setter, detail: string) {
  const now = Date.now()
  const safe = redactPii(detail)
  set((state) => ({
    activity: state.activity.map((s) =>
      s.status === 'running'
        ? { ...s, status: 'error' as EventStatus, endedAtMs: now, detail: safe }
        : s,
    ),
  }))
}

// --- Live text-generation step (activity feed) ------------------------------
// Surfaces the agent's plain-text answer as it streams, so the feed reflects
// what the agent is doing even when it never calls a tool. The step is created
// on the first streamed token and closed by finishTurn / the error handlers.

function ensureRespondingStep(set: Setter) {
  if (respondingStepId) return
  const id = newId('resp')
  respondingStepId = id
  pushActivity(set, {
    id,
    category: 'step',
    title: 'Responding…',
    status: 'running',
    createdAtMs: Date.now(),
  })
}

function paintRespondingStep(set: Setter) {
  if (!respondingStepId) return
  const title = redactPii(truncate(respondTextBuffer, 60) || 'Responding…')
  set((state) => {
    let changed = false
    const activity = state.activity.map((s) => {
      if (!changed && s.id === respondingStepId && s.status === 'running' && s.title !== title) {
        changed = true
        return { ...s, title }
      }
      return s
    })
    return changed ? { activity } : {}
  })
}

// Throttle step-title repaints to a few per second (deltas arrive per token).
function maybePaintRespondingStep(set: Setter) {
  const now = Date.now()
  if (now - respondLastPaintedAt < 120) return
  respondLastPaintedAt = now
  paintRespondingStep(set)
}

function resetRespondingStep() {
  respondingStepId = null
  respondTextBuffer = ''
  respondLastPaintedAt = 0
}

// Append a streamed token chunk to the in-progress assistant bubble, creating
// it on the first delta of the turn.  Deltas arrive per-token from the
// WebSocket and can fire hundreds of times per second.  To avoid exceeding
// React's maximum update depth we batch them and flush at most once per
// animation frame (~16 ms).  The buffer is always flushed synchronously when
// the streaming message is finalized (see finalizeStreaming).
let _pendingDelta = ''
let _deltaRafId: ReturnType<typeof requestAnimationFrame> | null = null
let _deltaPendingSet: Setter | null = null

function _flushDelta() {
  _deltaRafId = null
  const batch = _pendingDelta
  const set = _deltaPendingSet
  if (!batch || !set) return
  _pendingDelta = ''

  // One assistant text bubble per user turn. Never spawn a second bubble from
  // late StreamingDeltaEvents after MessageEvent sealed the first one.
  if (!streamingMessageId && turnAssistantMessageId) {
    const existing = useChat
      .getState()
      .activeConversation.find((m) => m.id === turnAssistantMessageId)
    // Sealed (MessageEvent / finishTurn) — drop straggler tokens.
    if (existing?.status === 'received') return
    streamingMessageId = turnAssistantMessageId
  }

  if (!streamingMessageId) {
    const now = new Date()
    const id = newId('assistant')
    streamingMessageId = id
    turnAssistantMessageId = id
    const message: Message = {
      id,
      role: 'assistant',
      content: batch,
      timestamp: now,
      createdAt: now.getTime(),
      reaction: null,
      status: 'receiving',
    }
    set((state) => ({ activeConversation: [...state.activeConversation, message] }))
    return
  }
  const id = streamingMessageId
  set((state) => ({
    activeConversation: state.activeConversation.map((m) =>
      m.id === id ? { ...m, content: m.content + batch } : m,
    ),
  }))
}

function appendStreamingDelta(set: Setter, delta: string) {
  // After this turn's answer is sealed, ignore late WS deltas so they cannot
  // create a duplicate Vera bubble (common when MessageEvent races StreamingDelta).
  if (
    !streamingMessageId &&
    turnAssistantMessageId &&
    useChat.getState().activeConversation.find((m) => m.id === turnAssistantMessageId)
      ?.status === 'received'
  ) {
    return
  }
  sawAgentTextThisTurn = true
  _pendingDelta += delta
  _deltaPendingSet = set
  if (_deltaRafId == null) {
    // In SSR/Node environments requestAnimationFrame is unavailable; fall back
    // to a 30 ms setTimeout which achieves the same batching effect.
    if (typeof requestAnimationFrame === 'function') {
      _deltaRafId = requestAnimationFrame(_flushDelta)
    } else {
      _deltaRafId = setTimeout(_flushDelta, 30) as unknown as number
    }
  }
}

// Commit the streamed bubble: mark it received and, when the authoritative
// final text is available, replace the accumulated deltas with it.
function finalizeStreaming(set: Setter, finalText?: string) {
  // Flush any buffered tokens before sealing the message.
  if (_deltaRafId != null) {
    if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(_deltaRafId)
    else clearTimeout(_deltaRafId as unknown as ReturnType<typeof setTimeout>)
    _deltaRafId = null
  }
  _deltaPendingSet = set
  _flushDelta()

  const id = streamingMessageId
  if (!id) return
  streamingMessageId = null
  turnAssistantMessageId = turnAssistantMessageId || id
  const authoritative =
    finalText != null && finalText.trim().length > 0 ? redactPii(finalText) : undefined
  set((state) => ({
    activeConversation: state.activeConversation.map((m) =>
      m.id === id
        ? {
            ...m,
            content: authoritative ?? redactPii(m.content),
            status: 'received' as Message['status'],
          }
        : m,
    ),
  }))
  mergeFilesOntoMessage(id, set)
}

function appendSystem(set: Setter, text: string) {
  const now = new Date()
  const message: Message = {
    id: newId('system'),
    role: 'system',
    content: redactPii(text),
    timestamp: now,
    createdAt: now.getTime(),
    reaction: null,
    status: 'error',
  }
  set((state) => ({ activeConversation: [...state.activeConversation, message] }))
}

function resetConnection(get: Getter, set: Setter) {
  const { socket } = get()
  if (socket) {
    try {
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
      socket.close()
    } catch {
      /* ignore */
    }
  }
  set({ socket: null, backendConversationId: null, backendConnected: false })
}

async function ensureSocket(get: Getter, set: Setter): Promise<WebSocket> {
  const existing = get().socket
  if (existing && existing.readyState === WebSocket.OPEN && get().backendConversationId) {
    return existing
  }
  if (existing) {
    try {
      existing.onopen = null
      existing.onmessage = null
      existing.onclose = null
      existing.onerror = null
      existing.close()
    } catch {
      /* ignore */
    }
    set({ socket: null, backendConnected: false })
  }

  const activeId = get().activeId
  const storedBackendId = (activeId && get().backendIdByChat[activeId]) || null

  // 1) Reuse this chat's existing backend conversation if we have one — this
  //    reconnects the WebSocket and keeps the agent's server-side context. If
  //    the backend no longer has it (e.g. it was restarted with a fresh
  //    workspace), fall through and create a new one; the UI history is
  //    preserved locally regardless.
  if (storedBackendId) {
    try {
      return await openBackendSocket(storedBackendId, get, set)
    } catch (error) {
      if (!(error as { notFound?: boolean })?.notFound) throw error
    }
  }

  // 2) Create a backend conversation server-side (LLM config + secrets stay in
  //    the Next.js server process, never in the browser) and bind it to this chat.
  const newConversationId = await createBackendConversation()
  // User may have clicked New Chat while create was in flight — don't bind to the wrong chat.
  if (get().activeId !== activeId) {
    throw new Error('Chat changed before the agent connection was ready')
  }
  if (activeId) {
    set((state) => ({
      backendIdByChat: { ...state.backendIdByChat, [activeId]: newConversationId },
    }))
  }
  return openBackendSocket(newConversationId, get, set)
}

async function createBackendConversation(): Promise<string> {
  let guardrails = {}
  try {
    const { loadGuardrailPrefs } = await import('./guardrail-prefs')
    guardrails = loadGuardrailPrefs()
  } catch {
    /* ignore */
  }
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ guardrails }),
  })
  if (!res.ok) {
    let detail = 'Failed to create HR Agent conversation'
    try {
      const body = await res.json()
      detail = body.error || body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  const { conversationId } = await res.json()
  if (!conversationId) throw new Error('Backend did not return a conversation id')
  return conversationId
}

// Open the event WebSocket for a backend conversation and subscribe. Resolves
// once connected; rejects with `{ notFound: true }` if the backend reports the
// conversation is gone (close code 4004) so the caller can recreate it.
function mirrorEventToCanvas(conversationId: string, evt: any) {
  if (!conversationId || !evt || typeof evt !== 'object') return
  const kind = evt.kind || evt.type
  // Safety-net lesson: do NOT mirror every Action/think frame — that floods
  // /api/canvas/webhook and the LLM canvas pipeline during the turn.
  // Only fan out observations, final agent messages, and confirmation/terminal state.
  if (kind === 'ObservationEvent') {
    /* keep */
  } else if (kind === 'MessageEvent' && evt.source === 'agent') {
    /* keep */
  } else if (kind === 'ActionEvent') {
    const name = String(evt.tool_name || '')
    if (
      !/^(send_email|send_slack_message|send_teams_message|write_workspace_file|upsert_document|replace_document)/.test(
        name,
      ) &&
      !name.startsWith('office_fill') &&
      name !== 'office_template_fill'
    ) {
      return
    }
  } else if (kind === 'ConversationStateUpdateEvent') {
    const status = readExecutionStatus(evt)
    if (
      status !== 'waiting_for_confirmation' &&
      !(status && TERMINAL_STATUSES.has(status))
    ) {
      return
    }
  } else {
    return
  }
  const id = conversationId.replace(/-/g, '').toLowerCase()
  void fetch(`/api/canvas/webhook/events/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify([evt]),
  }).catch(() => {
    /* canvas is best-effort; chat must keep working if it fails */
  })
}

function openBackendSocket(
  conversationId: string,
  get: Getter,
  set: Setter,
): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const activeIdAtOpen = get().activeId
    if (seenEventIdsForConversation !== conversationId) {
      seenEventIds = new Set<string>()
      seenEventIdsForConversation = conversationId
    }
    const ws = new WebSocket(`${WS_BASE}/sockets/events/${conversationId}`)
    let settled = false

    const stillOnSameChat = () => get().activeId === activeIdAtOpen

    if (!stillOnSameChat()) {
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      reject(new Error('Chat changed before the agent connection was ready'))
      return
    }

    // Bind only if we are still on the chat that requested this socket.
    set((state) => {
      if (state.activeId !== activeIdAtOpen) return {}
      return { socket: ws, backendConversationId: conversationId, connectionError: null }
    })
    if (get().activeId !== activeIdAtOpen || get().socket !== ws) {
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      reject(new Error('Chat changed before the agent connection was ready'))
      return
    }

    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      reject(new Error('Timed out connecting to the HR Agent event stream'))
    }, CONNECT_TIMEOUT_MS)

    ws.onmessage = (event) => {
      // Drop events if the user already switched away from this backend conversation.
      if (get().backendConversationId !== conversationId || get().activeId !== activeIdAtOpen) return
      let parsed: any
      try {
        parsed = JSON.parse(event.data)
      } catch {
        return
      }
      // Fan events into the Side Canvas pipeline. Backend→Next webhooks are
      // unreliable for local multi-port setups and were not delivering, so the
      // browser mirrors the same WS stream the chat already consumes.
      mirrorEventToCanvas(conversationId, parsed)
      handleServerEvent(parsed, get, set)
    }

    ws.onopen = () => {
      if (settled) return
      if (!stillOnSameChat()) {
        settled = true
        clearTimeout(timer)
        try {
          ws.close()
        } catch {
          /* ignore */
        }
        reject(new Error('Chat changed before the agent connection was ready'))
        return
      }
      settled = true
      clearTimeout(timer)
      // First-frame auth when the backend requires a session key; ignored when
      // no keys are configured.
      if (WS_TOKEN) {
        try {
          ws.send(JSON.stringify({ type: 'auth', session_api_key: WS_TOKEN }))
        } catch {
          /* ignore */
        }
      }
      set((state) =>
        state.activeId === activeIdAtOpen ? { backendConnected: true } : {},
      )
      void fetch('/api/chat/guardrails', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversationId }),
      }).catch(() => {
        /* HITL is also enforced server-side on resume */
      })
      resolve(ws)
    }

    ws.onclose = (ev) => {
      if (!settled) {
        settled = true
        clearTimeout(timer)
        if (ev.code === 4004) {
          const err = new Error('Backend conversation not found') as Error & {
            notFound: boolean
          }
          err.notFound = true
          reject(err)
        } else {
          reject(new Error('Could not connect to the HR Agent event stream'))
        }
        return
      }
      if (get().socket === ws) set({ backendConnected: false })
    }
  })
}

function handleServerEvent(evt: any, get: Getter, set: Setter) {
  const kind = evt?.kind
  const eventId = typeof evt?.id === 'string' ? evt.id : ''
  const isDuplicate = Boolean(eventId && seenEventIds.has(eventId))
  if (eventId && !isDuplicate) seenEventIds.add(eventId)

  if (isDuplicate) {
    // Even waiting_for_confirmation must not re-run — replaying it spawned
    // duplicate approval cards. Skill hints on user/invoke frames are the only
    // exception that still need a soft re-touch.
    if (kind === 'MessageEvent' && evt.source === 'user') {
      pushActivatedSkillSteps(set, readActivatedSkills(evt), get().activity)
    } else if (kind === 'ActionEvent' && evt.tool_name === 'invoke_skill') {
      pushInvokeSkillActionStep(set, evt, get().activity)
    }
    return
  }

  if (kind === 'MessageEvent') {
    if (evt.source === 'user') {
      pushActivatedSkillSteps(set, readActivatedSkills(evt), get().activity)
    }
    // Only render the agent's messages; the user's own turn is added
    // optimistically when sending, and echoes back as source "user".
    if (evt.source === 'agent') {
      const text = textFromLlmMessage(evt.llm_message)
      if (text) {
        sawAgentTextThisTurn = true
        // If we streamed this answer token-by-token, replace the in-progress
        // bubble with the authoritative text instead of appending a duplicate.
        if (streamingMessageId) finalizeStreaming(set, text)
        else upsertAssistant(set, text)
      }
    }
    return
  }

  // A live token delta for the current answer (only emitted when the backend
  // LLM is configured with stream=true). Builds the assistant bubble
  // incrementally; the trailing MessageEvent finalizes it. Also mirrors the
  // stream onto a live "responding…" activity step so the sidebar reflects the
  // agent's plain-text work in real time, not just its tool calls.
  if (kind === 'StreamingDeltaEvent') {
    if (typeof evt.content === 'string' && evt.content.length > 0) {
      respondTextBuffer = (respondTextBuffer + evt.content).slice(-4000)
      appendStreamingDelta(set, evt.content)
      ensureRespondingStep(set)
      maybePaintRespondingStep(set)
    }
    return
  }

  // The agent decided to call a tool: add a running step to the reasoning feed.
  if (kind === 'ActionEvent') {
    const toolName: string = evt.tool_name || 'tool'
    // The final answer is delivered via MessageEvent; don't clutter the feed
    // with the internal "finish" call.
    if (toolName === 'finish') return

    const params = extractActionParams(evt.action)

    if (toolName === 'invoke_skill') {
      pushInvokeSkillActionStep(set, evt, get().activity)
      mirrorWorkQueue(get, 'running')
      return
    }

    // Capture generated file paths as soon as the agent requests the write/fill.
    if (FILE_PRODUCING_TOOLS.has(toolName)) {
      rememberTurnFiles(extractPathsFromToolParams(params))
    }

    lastActionForApproval = {
      toolName,
      toolCallId: evt.tool_call_id,
      params,
    }

    // Backend SecurityAnalyzer / ConfirmationPolicy decide when approval is
    // required (via waiting_for_confirmation). Just show a running step here.
    pushActivity(set, {
      id: newId('act'),
      category: categoryForTool(toolName),
      title: titleForAction(evt),
      detail: detailForAction(toolName, evt, params),
      status: confirmationStatusSeen ? 'warn' : 'running',
      createdAtMs: Date.now(),
      toolCallId: evt.tool_call_id,
      toolName,
      rawParams: params,
    })
    if (confirmationStatusSeen) {
      const conversationId = get().backendConversationId
      if (conversationId) {
        appendApprovalRequest(
          set,
          {
            conversationId,
            toolName,
            title: actionTitle(toolName, params),
            params,
            risk: String(params?.security_risk || 'HIGH'),
          },
          evt.tool_call_id,
        )
      }
    }
    mirrorWorkQueue(get, confirmationStatusSeen ? 'needs_approval' : 'running')
    return
  }

  // A tool returned: close out the matching step (success or error).
  if (kind === 'ObservationEvent') {
    const isErr = !!evt.observation?.is_error
    const toolName: string = evt.tool_name || ''
    const patch: Partial<ActivityStep> = {
      status: isErr ? 'error' : 'success',
      endedAtMs: Date.now(),
    }
    if (isErr) {
      patch.detail = truncate(observationText(evt.observation)) || 'Tool error'
    } else if (toolName === 'invoke_skill') {
      const skillName = observationSkillName(evt.observation)
      if (skillName) {
        patch.title = formatSkillTitle(skillName, 'invoking')
        patch.detail = 'Loaded skill instructions'
      }
    } else {
      const obs = truncate(observationText(evt.observation))
      if (obs) patch.detail = obs
      if (
        FILE_PRODUCING_TOOLS.has(toolName) ||
        /path|outputs\//i.test(observationText(evt.observation))
      ) {
        const obsPaths = [
          ...extractPathsFromObservation(evt.observation),
          ...extractPathsFromObservation(observationText(evt.observation)),
        ]
        if (obsPaths.length) rememberTurnFiles(obsPaths)
        else {
          const step = get().activity.find((s) => s.toolCallId === evt.tool_call_id)
          if (step?.rawParams) rememberTurnFiles(extractPathsFromToolParams(step.rawParams))
        }
        const last = get().activeConversation.at(-1)
        if (
          last?.role === 'assistant' &&
          turnGeneratedFiles.size > 0 &&
          (last.status === 'receiving' || sawAgentTextThisTurn)
        ) {
          mergeFilesOntoMessage(last.id, set)
        }
      }
    }
    const matched = updateActivityByToolCall(set, evt.tool_call_id, patch)
    if (!matched && !isErr && toolName === 'invoke_skill') {
      const skillName = observationSkillName(evt.observation) || skillNameFromAction(evt)
      if (skillName) {
        const now = Date.now()
        pushActivity(set, {
          id: newId('skill'),
          category: 'skill',
          title: formatSkillTitle(skillName, 'invoking'),
          detail: 'Loaded skill instructions',
          status: 'success',
          createdAtMs: now,
          endedAtMs: now,
          toolCallId: evt.tool_call_id,
          toolName: 'invoke_skill',
          rawParams: { name: skillName },
        })
      }
    }
    mirrorWorkQueue(get, get().pendingApproval ? 'needs_approval' : 'running')
    return
  }

  if (kind === 'UserRejectObservation') {
    updateActivityByToolCall(set, evt.tool_call_id, {
      status: 'warn',
      endedAtMs: Date.now(),
      detail: truncate(evt.rejection_reason || 'Rejected'),
    })
    return
  }

  // Conversation-level failure (not fed back to the LLM). Surface it and stop.
  if (kind === 'ConversationErrorEvent') {
    const detail = evt.detail || evt.code || 'The conversation failed.'
    appendSystem(set, `Conversation error: ${detail}`)
    markRunningStepsError(set, truncate(String(detail)))
    finalizeStreaming(set)
    set({ isRunning: false, pendingApproval: null, approvalResolving: false })
    // Stale backend conversations keep the LLM config from when they were
    // created. After switching providers (e.g. Groq → Ollama), reconnecting to
    // an old id produces auth/provider errors. Drop the binding so the next
    // message creates a fresh conversation with the current provider.
    if (isStaleProviderError(detail)) {
      invalidateBackendBinding(get, set)
      appendSystem(
        set,
        'This chat was still bound to an old LLM provider. Send your message again — it will use the current provider (Ollama).',
      )
    }
    return
  }

  if (kind === 'ConversationStateUpdateEvent') {
    const status = readExecutionStatus(evt)
    if (status === 'waiting_for_confirmation') {
      confirmationStatusSeen = true
      set({ isRunning: false, approvalResolving: false })
      const { activity } = get()
      const pendingStepRunning = activity
        .slice()
        .reverse()
        .find((s) => s.status === 'running' && s.toolName)
      // Safety-net: Action may leave `running` before this status arrives.
      const pendingStepAny = activity
        .slice()
        .reverse()
        .find((s) => s.toolName && s.toolName !== 'invoke_skill' && s.toolName !== 'finish')
      const pendingStep = pendingStepRunning ?? pendingStepAny
      const conversationId = get().backendConversationId
      const fallback = lastActionForApproval
      const toolName = pendingStep?.toolName || fallback?.toolName || 'action'
      const toolCallId = pendingStep?.toolCallId || fallback?.toolCallId
      const params = pendingStep?.rawParams || fallback?.params || {}
      if (conversationId && toolName) {
        if (toolCallId) {
          updateActivityByToolCall(set, toolCallId, {
            status: 'warn',
            detail: 'Awaiting approval in chat',
          })
        }
        const approvalTitle = actionTitle(toolName, params)
        appendApprovalRequest(
          set,
          {
            conversationId,
            toolName,
            title: approvalTitle,
            params,
            risk: String(params?.security_risk || 'HIGH'),
          },
          toolCallId,
        )
        const chatId = get().activeId
        if (chatId) {
          noteChatApproval(chatId, approvalTitle)
          mirrorWorkQueue(get, 'needs_approval', {
            awaitingApproval: true,
            approvalTitle,
            force: true,
          })
        }
      }
    } else if (status === 'running') {
      // Resume after approval — clear the gate, but keep approvalShownForToolCallId
      // so a duplicate waiting event cannot spawn a second card for the same call.
      set({ isRunning: true, pendingApproval: null, approvalResolving: false })
      resumeAwaitingApprovalSteps(set, 'Approved — executing…')
      mirrorWorkQueue(get, 'running')
    } else if (status && TERMINAL_STATUSES.has(status)) {
      finishTurn(status, get, set)
    }
    return
  }

  if (kind === 'AgentErrorEvent') {
    const detail = evt.error || evt.detail || evt.message || 'The agent reported an error.'
    // Reflect the failure on the originating tool step when we can match it.
    if (evt.tool_call_id) {
      updateActivityByToolCall(set, evt.tool_call_id, {
        status: 'error',
        endedAtMs: Date.now(),
        detail: truncate(String(detail)),
      })
    }
    const text = `Agent error: ${detail}`
    const last = get().activeConversation.at(-1)
    if (last?.role === 'system' && last.content === text) return
    appendSystem(set, text)
    return
  }

  if (kind === 'ServerErrorEvent') {
    const detail = evt.detail || evt.code || 'Unknown server error'
    appendSystem(set, `Server error: ${detail}`)
    set({ isRunning: false, pendingApproval: null, approvalResolving: false })
    return
  }
}

function mirrorWorkQueue(
  get: Getter,
  status: WorkStatusLike,
  opts?: { awaitingApproval?: boolean; approvalTitle?: string; force?: boolean },
) {
  const chatId = get().activeId
  if (!chatId) return
  const conv = get().conversations.find((c) => c.id === chatId)
  const lastUser = [...get().activeConversation].reverse().find((m) => m.role === 'user')
  const title = conv?.title && conv.title !== 'New Chat' ? conv.title : titleFromText(lastUser?.content || 'Agent run')
  syncWorkFromChatActivity({
    chatId,
    title,
    summary: (lastUser?.content || title).slice(0, 400),
    activity: get().activity,
    status,
    awaitingApproval: opts?.awaitingApproval,
    approvalTitle: opts?.approvalTitle,
    force: opts?.force,
  })
}

type WorkStatusLike = 'needs_approval' | 'running' | 'queued' | 'blocked' | 'completed'

function finishTurn(status: string, get: Getter, set: Setter) {
  set({ isRunning: false, pendingApproval: null, approvalResolving: false })
  resetRespondingStep()

  const chatId = get().activeId
  let workStatus: WorkStatusLike = 'queued'
  if (status === 'finished') workStatus = 'completed'
  else if (USER_CANCEL_STATUSES.has(status)) workStatus = 'queued'
  else if (status === 'error' || status === 'stuck') workStatus = 'blocked'
  else workStatus = 'queued'

  // Only create/update Work Queue when this turn did substantial tool/skill work
  // (or an item already exists). Greetings like "Hi there" stay out.
  if (chatId) {
    mirrorWorkQueue(get, workStatus)
    // Keep setChatWorkStatus for items already tracked when promote threshold wasn't met mid-turn
    // but item existed — mirrorWorkQueue handles existing; no-op if none.
    if (workStatus === 'completed' || workStatus === 'blocked' || workStatus === 'queued') {
      setChatWorkStatus(chatId, workStatus)
    }
  }

  // Close out any steps still marked running so the feed doesn't spin forever,
  // and commit any partially streamed answer. A user-initiated stop is not a
  // failure: close those steps as "warn" so the feed reads as cancelled, not
  // broken, and don't fetch the final response for it.
  let stepStatus: EventStatus = status === 'finished' ? 'success' : 'error'
  let cancelled = false
  if (USER_CANCEL_STATUSES.has(status)) {
    stepStatus = 'warn'
    cancelled = true
  }
  const now = Date.now()
  set((state) => {
    const activity = state.activity.map((s) =>
      s.status === 'running' ? { ...s, status: stepStatus, endedAtMs: now } : s,
    )
    return {
      activity,
      activityByChat: parkActivity(
        state.activityByChat,
        state.activeId,
        activity,
        state.activityStartedAt,
      ),
    }
  })
  finalizeStreaming(set)

  if (status === 'error' || status === 'stuck') {
    appendSystem(set, `The agent stopped (${status}).`)
    return
  }
  if (cancelled) {
    appendSystem(set, 'The run was stopped.')
    return
  }

  // status === 'finished'. Some agents deliver their final answer via a
  // finish action rather than a plain message event. If nothing rendered this
  // turn, pull the final response as a fallback (give a trailing message event
  // a brief moment to arrive first).
  // Skip when an approval card is open — fetching often returns a prior turn's
  // answer and resurfaces it as a duplicate bubble.
  if (sawAgentTextThisTurn) return
  if (get().pendingApproval || getPendingApprovalOpen(get().activeConversation)) return
  const conversationId = get().backendConversationId
  if (!conversationId) return
  const turnStartedAt = get().activityStartedAt
  setTimeout(async () => {
    if (sawAgentTextThisTurn) return
    if (get().pendingApproval || getPendingApprovalOpen(get().activeConversation)) return
    try {
      const res = await fetch(
        `/api/chat?conversationId=${encodeURIComponent(conversationId)}&final=1`,
      )
      if (!res.ok) return
      const data = await res.json()
      const text = (data.response || '').trim()
      if (!text || sawAgentTextThisTurn) return
      // Reject stale finals that already appear earlier in this chat (previous turn).
      const already = get().activeConversation.some(
        (m) =>
          m.role === 'assistant' &&
          !m.metadata?.approval &&
          m.content.trim() === text &&
          (turnStartedAt == null || (m.createdAt ?? 0) < turnStartedAt),
      )
      if (already) return
      upsertAssistant(set, text)
    } catch {
      /* ignore */
    }
  }, 500)
}

// ---------------------------------------------------------------------------
// Persistence: chat list, per-chat history, backend binding, and last activity
// feed are saved to localStorage so switching chats / reopening the tab restores
// them. Ephemeral runtime state (socket, isRunning) is not persisted.
// ---------------------------------------------------------------------------

const PERSIST_KEY = 'hr-copilot:chats:v3'
const PERSIST_KEY_LEGACY = ['hr-copilot:chats:v2', 'hr-copilot:chats:v1']
/** Bump when HR_SYSTEM_SUFFIX / agent config changes so old backend conversations
 * (which bake the system prompt at create time) are rebound on next message. */
const AGENT_PROMPT_BUILD = '2026-08-20-hr-ux-v3-skills'
const PROMPT_BUILD_KEY = 'hr-copilot:prompt-build'

interface StoredMessage extends Omit<Message, 'timestamp'> {
  timestamp: number
}

interface PersistShape {
  conversations: ConversationMeta[]
  activeId: string | null
  messagesByChat: Record<string, StoredMessage[]>
  backendIdByChat: Record<string, string>
  activityByChat?: Record<string, ParkedActivity>
}

/** True when the error means this backend conversation's baked-in LLM is unusable. */
function isStaleProviderError(detail: unknown): boolean {
  const s = String(detail || '').toLowerCase()
  return (
    s.includes('invalid_api_key') ||
    s.includes('invalid api key') ||
    s.includes('authentication') ||
    s.includes('llmauthenticationerror') ||
    s.includes('resource_exhausted') ||
    s.includes('ollamaexception') ||
    s.includes('apiconnectionerror') ||
    (s.includes('groqexception') && s.includes('api')) ||
    (s.includes('badrequesterror') &&
      (s.includes('api key') || s.includes('api_key') || s.includes('gemini')))
  )
}

/** Drop the active chat's backend conversation binding and close the socket. */
function invalidateBackendBinding(get: Getter, set: Setter) {
  const activeId = get().activeId
  resetConnection(get, set)
  if (!activeId) return
  set((state) => {
    const backendIdByChat = { ...state.backendIdByChat }
    delete backendIdByChat[activeId]
    return { backendIdByChat, backendConversationId: null }
  })
}

function serializeMessages(messages: Message[]): StoredMessage[] {
  return messages.map((m) => ({
    ...m,
    timestamp: m.timestamp instanceof Date ? m.timestamp.getTime() : (m.createdAt ?? Date.now()),
  }))
}

function reviveMessages(messages: StoredMessage[] | undefined): Message[] {
  if (!Array.isArray(messages)) return []
  return messages.map((m) => ({
    ...m,
    timestamp: new Date(typeof m.timestamp === 'number' ? m.timestamp : (m.createdAt ?? Date.now())),
  }))
}

function persistState(state: ChatState) {
  if (typeof window === 'undefined') return
  // Fold the active chat's live messages/activity back into the maps before writing.
  const messagesByChat: Record<string, StoredMessage[]> = {}
  for (const [id, msgs] of Object.entries(state.messagesByChat)) {
    messagesByChat[id] = serializeMessages(msgs)
  }
  if (state.activeId) {
    messagesByChat[state.activeId] = serializeMessages(state.activeConversation)
  }
  const activityByChat = parkActivity(
    state.activityByChat,
    state.activeId,
    state.activity,
    state.activityStartedAt,
  )
  const shape: PersistShape = {
    conversations: state.conversations,
    activeId: state.activeId,
    messagesByChat,
    backendIdByChat: state.backendIdByChat,
    activityByChat,
  }
  try {
    window.localStorage.setItem(PERSIST_KEY, JSON.stringify(shape))
  } catch {
    /* quota / private mode — non-fatal */
  }
}

let hydrated = false

function hydrateFromStorage(set: Setter) {
  if (typeof window === 'undefined' || hydrated) return
  hydrated = true
  let shape: PersistShape | null = null
  let fromLegacy = false
  try {
    const raw = window.localStorage.getItem(PERSIST_KEY)
    if (raw) {
      shape = JSON.parse(raw)
    } else {
      // Migrate older persist keys: keep chat list + messages, but DROP backend
      // conversation ids. Those bake in the LLM provider from creation time;
      // reusing them after a provider switch (Ollama ↔ Gemini ↔ Groq) fails.
      for (const key of PERSIST_KEY_LEGACY) {
        const legacy = window.localStorage.getItem(key)
        if (!legacy) continue
        shape = JSON.parse(legacy)
        fromLegacy = true
        window.localStorage.removeItem(key)
        break
      }
    }
  } catch {
    shape = null
  }
  if (!shape) {
    try {
      window.localStorage.setItem(PROMPT_BUILD_KEY, AGENT_PROMPT_BUILD)
    } catch {
      /* ignore */
    }
    set({ sessionHydrated: true })
    return
  }

  const messagesByChat: Record<string, Message[]> = {}
  for (const [id, msgs] of Object.entries(shape.messagesByChat || {})) {
    messagesByChat[id] = reviveMessages(msgs)
  }
  const activeId = shape.activeId ?? null
  // Fresh provider bindings after migration; keep them for same-session v2 loads.
  let backendIdByChat = fromLegacy ? {} : shape.backendIdByChat || {}
  const activityByChat = fromLegacy ? {} : shape.activityByChat || {}
  const restoredActivity = takeParkedActivity(activityByChat, activeId)

  // System prompt is baked into the backend conversation at create time.
  // When we ship prompt fixes, drop all bindings so the next message gets a
  // fresh conversation with the updated HR_SYSTEM_SUFFIX (UI history stays).
  try {
    const prevBuild = window.localStorage.getItem(PROMPT_BUILD_KEY)
    if (prevBuild !== AGENT_PROMPT_BUILD) {
      backendIdByChat = {}
      window.localStorage.setItem(PROMPT_BUILD_KEY, AGENT_PROMPT_BUILD)
    }
  } catch {
    /* ignore */
  }

  set({
    conversations: shape.conversations || [],
    activeId,
    messagesByChat,
    backendIdByChat,
    activityByChat,
    activeConversation: activeId ? (messagesByChat[activeId] ?? []) : [],
    backendConversationId: activeId ? (backendIdByChat[activeId] ?? null) : null,
    activity: restoredActivity.activity,
    activityStartedAt: restoredActivity.activityStartedAt,
    sessionHydrated: true,
  })
}

// Debounced write on any relevant state change. Runs once per module load.
if (typeof window !== 'undefined') {
  let writeTimer: ReturnType<typeof setTimeout> | undefined
  useChat.subscribe((state) => {
    clearTimeout(writeTimer)
    writeTimer = setTimeout(() => persistState(state), 250)
  })
}

export function ChatProvider({ children }: { children: ReactNode }) {
  // Restore the persisted session once, on the client, after mount to avoid an
  // SSR/CSR hydration mismatch.
  useEffect(() => {
    useChat.getState().hydrate()
  }, [])
  return children
}

export function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.floor(hours / 24)
  return `${days} d ago`
}

export { MODELS, TONES, DATA_SOURCES }
