import fs from 'node:fs'
import path from 'node:path'

import type { CanvasBlock, CanvasStatePayload } from '@/lib/canvas-types'

type TraceStatus = 'success' | 'failure' | 'info'

interface TraceDetails {
  turnId?: string | null
  success?: boolean
  count?: number
  status?: string | null
  error?: string
  [key: string]: unknown
}

interface ConversationRecord {
  conversationId: string
  turnId: string | null
  events: any[]
  eventKeys: Set<string>
  terminalKeys: Set<string>
  processing: boolean
  processedTerminalKey: string | null
  pendingTerminalKey: string | null
  pendingTerminalTimer: ReturnType<typeof setTimeout> | null
  state: CanvasStatePayload
  pose: Record<string, unknown>
}

export interface EvaluatorResult {
  workflow_detected: boolean
  canvas_worthy: boolean
  workflow_type: string | null
  reason: string
}

const TERMINAL_STATUSES = new Set(['finished', 'error', 'stuck', 'paused', 'interrupted', 'stopped'])
// Also run the canvas pipeline when the agent pauses for human approval — that
// is exactly when chat says "review the draft in the Canvas."
const PIPELINE_STATUSES = new Set([
  ...TERMINAL_STATUSES,
  'waiting_for_confirmation',
])

// Next.js / Turbopack can evaluate this module more than once (separate route
// bundles). A plain module-level Map then means webhook POSTs write to one
// instance while /api/canvas/state reads another — Canvas stays empty forever.
// Persist on globalThis + a small on-disk cache so every handler sees the same
// ready state.
const globalForCanvas = globalThis as typeof globalThis & {
  __closedaiCanvasRecords?: Map<string, ConversationRecord>
}
const records: Map<string, ConversationRecord> =
  globalForCanvas.__closedaiCanvasRecords ?? new Map<string, ConversationRecord>()
globalForCanvas.__closedaiCanvasRecords = records

const CANVAS_STATE_DIR = path.join(process.cwd(), '.next', 'cache', 'canvas-state')

function ensureCanvasStateDir() {
  try {
    fs.mkdirSync(CANVAS_STATE_DIR, { recursive: true })
  } catch {
    /* ignore */
  }
}

function canvasStatePath(conversationId: string): string {
  return path.join(CANVAS_STATE_DIR, `${normalizeConversationId(conversationId)}.json`)
}

function persistCanvasState(state: CanvasStatePayload) {
  try {
    ensureCanvasStateDir()
    fs.writeFileSync(canvasStatePath(state.conversationId), JSON.stringify(state), 'utf8')
  } catch (error) {
    console.warn('[canvas-trace]', JSON.stringify({
      conversationId: state.conversationId,
      stage: 'persist canvas state',
      status: 'failure',
      error: error instanceof Error ? error.message : String(error),
    }))
  }
}

function loadPersistedCanvasState(conversationId: string): CanvasStatePayload | null {
  try {
    const file = canvasStatePath(conversationId)
    if (!fs.existsSync(file)) return null
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8')) as CanvasStatePayload
    if (!parsed || typeof parsed !== 'object') return null
    if (!Array.isArray(parsed.blocks)) parsed.blocks = []
    return parsed
  } catch {
    return null
  }
}

function nowIso(): string {
  return new Date().toISOString()
}

function cleanId(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed || null
}

function normalizeConversationId(value: string): string {
  return value.replace(/-/g, '').toLowerCase()
}

function trace(conversationId: string, stage: string, status: TraceStatus, details: TraceDetails = {}) {
  const safeDetails = { ...details }
  delete safeDetails.prompt
  delete safeDetails.content
  delete safeDetails.llm_message
  console.info('[canvas-trace]', JSON.stringify({
    conversationId,
    turnId: details.turnId ?? null,
    stage,
    timestamp: nowIso(),
    status,
    ...safeDetails,
  }))
}

function emptyState(conversationId: string): CanvasStatePayload {
  return {
    conversationId,
    turnId: null,
    status: 'empty',
    blocks: [],
    updatedAt: nowIso(),
  }
}

function getRecord(conversationId: string): ConversationRecord {
  conversationId = normalizeConversationId(conversationId)
  let record = records.get(conversationId)
  if (!record) {
    record = {
      conversationId,
      turnId: null,
      events: [],
      eventKeys: new Set(),
      terminalKeys: new Set(),
      processing: false,
      processedTerminalKey: null,
      pendingTerminalKey: null,
      pendingTerminalTimer: null,
      state: emptyState(conversationId),
      pose: {},
    }
    records.set(conversationId, record)
  }
  return record
}

function eventKey(evt: any, index: number): string {
  const kind = cleanId(evt?.kind) || 'event'
  return cleanId(evt?.id) || cleanId(evt?.event_id) || (cleanId(evt?.tool_call_id) ? `${kind}:${evt.tool_call_id}` : null) || `${kind}:${index}:${JSON.stringify(evt).slice(0, 300)}`
}

function eventText(evt: any): string {
  const pieces = [
    evt?.kind,
    evt?.tool_name,
    evt?.action?.name,
    evt?.action?.tool_name,
    evt?.observation?.content,
    evt?.observation?.result,
    evt?.observation?.text,
    evt?.status,
    evt?.execution_status,
  ]
  return pieces.filter((p) => typeof p === 'string').join(' ').toLowerCase()
}

function semanticEventText(evt: any): string {
  return [
    eventText(evt),
    evt?.tool_name,
    stringifyForSearch(evt?.action),
    stringifyForSearch(evt?.observation),
  ]
    .filter(Boolean)
    .join(' ')
    .replace(/_/g, ' ')
    .toLowerCase()
}

function readExecutionStatus(evt: any): string | null {
  // Real ConversationStateUpdateEvent shape from the backend is
  // { kind, key: "execution_status", value: "waiting_for_confirmation" | "finished" | ... }
  // — NOT a top-level execution_status field. Match chat-store.ts.
  const keyed = evt?.value
  if (evt?.key === 'execution_status') {
    const status = typeof keyed === 'string' ? keyed : keyed?.execution_status
    return typeof status === 'string' ? status.toLowerCase() : null
  }
  if (keyed && typeof keyed === 'object' && typeof keyed.execution_status === 'string') {
    return String(keyed.execution_status).toLowerCase()
  }
  const raw =
    evt?.execution_status ||
    evt?.status ||
    evt?.state?.execution_status ||
    evt?.conversation?.execution_status ||
    evt?.data?.execution_status
  if (typeof raw !== 'string') return null
  return raw.toLowerCase()
}

function isFinalAgentMessage(evt: any): boolean {
  return evt?.kind === 'MessageEvent' && evt?.source === 'agent'
}

function terminalKey(evt: any, record: ConversationRecord): string | null {
  const status = readExecutionStatus(evt)
  if (!status || !PIPELINE_STATUSES.has(status)) return null
  const turnId = cleanId(evt?.turn_id) || cleanId(evt?.turnId) || cleanId(evt?.head_id) || cleanId(evt?.leaf_event_id) || cleanId(evt?.id) || `events:${record.events.length}`
  record.turnId = turnId
  return `${turnId}:${status}`
}

function summarizePose(record: ConversationRecord): Record<string, unknown> {
  return {
    ...record.pose,
    subject: inferSubject(record.events),
  }
}

function inferSubject(events: any[]): string | null {
  const joined = JSON.stringify(events).slice(0, 10000)
  const match = joined.match(/\b([A-Z][a-z]+ [A-Z][a-z]+)\b/)
  return match?.[1] || null
}

function toolNames(events: any[]): string[] {
  return Array.from(new Set(events.map((evt) => cleanId(evt?.tool_name)).filter(Boolean) as string[]))
}

export function shouldEvaluateCanvas(pose: Record<string, unknown>, events: any[]) {
  const names = toolNames(events)
  const actionEvents = events.filter((evt) => evt?.kind === 'ActionEvent')
  const observationEvents = events.filter((evt) => evt?.kind === 'ObservationEvent')
  const agentText = events.filter((evt) => isFinalAgentMessage(evt)).map(extractAgentMessageText).join(' ')
  const text = `${JSON.stringify(pose)} ${names.join(' ')} ${events.map(semanticEventText).join(' ')} ${agentText}`
    .replace(/_/g, ' ')
    .toLowerCase()
  const structuredOutcome = observationEvents.some((evt) => {
    const tool = cleanId(evt?.tool_name) || ''
    if (PLUMBING_TOOL_RE.test(tool)) return false
    return hasSubstantialStructuredPayload(observationPayload(evt))
  })
  const longFormOutcome = observationEvents.some((evt) => observationTextLength(evt) >= 280)
  const explicitCanvasLanguage = /\b(show|display|visualize|compare|review|summarize|table|report|draft|form|dashboard|profile|record|workspace|canvas|creative|side canvas|onboard|approval)\b/.test(text)
  const agentMessageEvents = events.filter((evt) => isFinalAgentMessage(evt))
  const substantialAgentMessage = agentMessageEvents.some((evt) => extractAgentMessageText(evt).length >= 200)
  const approvalOrCommDraft = names.some((name) =>
    /^(send_email|send_slack_message|send_teams_message|upsert_document|replace_document|office_fill_|write_workspace_file)/.test(name),
  )
  const waitingForConfirmation = events.some((evt) => readExecutionStatus(evt) === 'waiting_for_confirmation')
  const batchOrMultiStep = /\bbatch\b|\bmultiple\b|\bworkflow\b|\bdependent\b|\bseveral\b/.test(text) || actionEvents.length >= 3
  const multipleSystems = new Set(names.map((name) => name.split('_')[0])).size > 1 && actionEvents.length > 1
  return {
    candidate:
      structuredOutcome ||
      longFormOutcome ||
      explicitCanvasLanguage ||
      batchOrMultiStep ||
      multipleSystems ||
      substantialAgentMessage ||
      approvalOrCommDraft ||
      waitingForConfirmation,
    reason: {
      structuredOutcome,
      longFormOutcome,
      explicitCanvasLanguage,
      batchOrMultiStep,
      multipleSystems,
      substantialAgentMessage,
      approvalOrCommDraft,
      waitingForConfirmation,
      actionCount: actionEvents.length,
      toolCount: names.length,
    },
  }
}

export function parseEvaluatorResult(raw: unknown): EvaluatorResult {
  const data = typeof raw === 'string' ? parseJsonObject(raw) : raw
  if (!data || typeof data !== 'object') throw new Error('Evaluator returned no JSON object')
  const obj = data as Record<string, unknown>
  return {
    workflow_detected: obj.workflow_detected === true,
    canvas_worthy: obj.canvas_worthy === true,
    workflow_type: typeof obj.workflow_type === 'string' ? obj.workflow_type : null,
    reason: typeof obj.reason === 'string' ? obj.reason.slice(0, 500) : '',
  }
}

export function validateCanvasBlocks(raw: unknown, supportedTypes = loadSupportedBlockTypes()): CanvasBlock[] {
  const data = typeof raw === 'string' ? parseJsonObject(raw) : raw
  const list = Array.isArray(data) ? data : Array.isArray((data as any)?.blocks) ? (data as any).blocks : data ? [data] : []
  const blocks: CanvasBlock[] = []
  for (const item of list) {
    if (!item || typeof item !== 'object') continue
    const block = item as Record<string, unknown>
    if (typeof block.type !== 'string') continue
    if (!supportedTypes.has(block.type)) continue
    if (typeof block.props !== 'object' || block.props === null || Array.isArray(block.props)) continue
    blocks.push({
      type: block.type,
      version: typeof block.version === 'string' || typeof block.version === 'number' ? block.version : 1,
      props: block.props as Record<string, unknown>,
    })
  }
  const sanitized = sanitizeCanvasBlocks(blocks)
  if (sanitized.length === 0) throw new Error('Generator returned no supported Canvas blocks')
  return sanitized
}

const CHAT_DUMP_TYPES = new Set(['freeform-card', 'chat-thread', 'task-card'])
const APPROVAL_TYPES = new Set(['approval-card', 'approval-compact', 'approval'])
const TABLE_TYPES = new Set(['table', 'data-table'])
const PLUMBING_TOOL_RE =
  /^(activate_integration|invoke_skill|think|cache_prompt|execute_bash|browser_|finish|think_tool)/i

function isPlumbingTable(block: CanvasBlock): boolean {
  if (!TABLE_TYPES.has(block.type)) return false
  const title = String(block.props.title || '')
  if (PLUMBING_TOOL_RE.test(title)) return true
  const columns = Array.isArray(block.props.columns)
    ? (block.props.columns as unknown[]).map((c) => String(c).toLowerCase())
    : []
  const colset = new Set(columns)
  if (colset.has('cache_prompt')) return true
  if (colset.has('type') && colset.has('text') && columns.length <= 4) return true
  return false
}

function isChatDumpCard(block: CanvasBlock): boolean {
  if (CHAT_DUMP_TYPES.has(block.type)) return true
  if (block.type !== 'summary-card') return false
  const body = typeof block.props.body === 'string' ? block.props.body : ''
  return body.length > 400
}

function isUnavailablePlaceholder(block: CanvasBlock): boolean {
  const blob = JSON.stringify(block.props || {}).toLowerCase()
  return /details unavailable|unavailable in canvas|mark(?:ed)? unavailable/.test(blob)
}

function sanitizeCanvasBlocks(blocks: CanvasBlock[]): CanvasBlock[] {
  return blocks
    .filter((block) => !APPROVAL_TYPES.has(block.type))
    .filter((block) => !isChatDumpCard(block))
    .filter((block) => !isPlumbingTable(block))
    .filter((block) => !isUnavailablePlaceholder(block))
    .map((block) => {
      const props = { ...block.props }
      delete props.actions
      delete props.buttons
      delete props.primaryAction
      delete props.secondaryAction
      delete props.approveAction
      delete props.rejectAction
      return scrubCanvasBlockPaths({ ...block, props })
    })
    .filter(Boolean) as CanvasBlock[]
}

const PATH_COLUMN_RE = /^(path|file\s*path|location|uri|url|storage|blob|container)$/i

function scrubVisiblePathString(value: unknown): unknown {
  if (typeof value !== 'string') return value
  let s = value
  // Replace outputs/foo.md → foo.md everywhere in visible copy
  s = s.replace(/\b(?:outputs|uploads|workspace)[/\\]+([^\s`"')]+)/gi, '$1')
  s = s.replace(/\bAzure\s+Blob(?:\s+Storage)?\b/gi, 'files')
  s = s.replace(/\bblob storage\b/gi, 'files')
  return s
}

function resolveAttachmentPath(props: Record<string, unknown>): string | undefined {
  const candidates = [props.path, props.file_path, props.filepath, props.filename, props.name, props.title]
  for (const c of candidates) {
    if (typeof c === 'string' && /\.(pdf|docx|xlsx|pptx|txt|csv|md)$/i.test(c)) {
      // Prefer keeping outputs/ prefix for API resolution when present
      const trimmed = c.trim().replace(/\\/g, '/')
      if (trimmed.includes('outputs/') || trimmed.includes('uploads/')) {
        const m = trimmed.match(/((?:outputs|uploads)\/[^\s]+)/i)
        return m ? m[1].replace(/[.,!?'"]+$/, '') : trimmed
      }
      return trimmed.split(/[/\\]/).pop() || trimmed
    }
  }
  return undefined
}

function scrubCanvasBlockPaths(block: CanvasBlock): CanvasBlock | null {
  const type = block.type
  const props = { ...block.props }

  // Attachment / document blocks: keep real path for download; show basename only.
  if (type === 'attachment' || type === 'file-attachment' || type === 'document-preview') {
    const path = resolveAttachmentPath(props)
    if (path) props.path = path
    const base = path ? path.split(/[/\\]/).pop() : undefined
    if (base) {
      props.filename = base
      if (typeof props.title === 'string' && /outputs|uploads|\//i.test(props.title)) {
        props.title = base
      }
    }
    // Never show raw path as a visible secondary field
    delete props.file_path
    delete props.filepath
    delete props.location
    return { ...block, props }
  }

  // data-table / table: drop PATH columns and scrub cell strings
  if (type === 'data-table' || type === 'table') {
    const columns = Array.isArray(props.columns) ? (props.columns as unknown[]) : null
    const rows = Array.isArray(props.rows) ? (props.rows as unknown[]) : null

    if (columns && rows) {
      const keepIdx: number[] = []
      const newCols: string[] = []
      columns.forEach((col, i) => {
        const label = String(col ?? '')
        if (PATH_COLUMN_RE.test(label.trim())) return
        keepIdx.push(i)
        newCols.push(String(scrubVisiblePathString(label)))
      })
      props.columns = newCols
      props.rows = rows.map((row) => {
        if (!Array.isArray(row)) {
          if (row && typeof row === 'object') {
            const obj = { ...(row as Record<string, unknown>) }
            for (const key of Object.keys(obj)) {
              if (PATH_COLUMN_RE.test(key)) delete obj[key]
              else obj[key] = scrubVisiblePathString(obj[key])
            }
            return obj
          }
          return scrubVisiblePathString(row)
        }
        return keepIdx.map((i) => scrubVisiblePathString(row[i]))
      })

      // If this was purely an "artifacts with paths" table, convert leftover
      // filename cells into attachment blocks instead of an empty table.
      if (newCols.length === 0) {
        return null
      }
    } else if (rows) {
      props.rows = rows.map((row) => {
        if (row && typeof row === 'object' && !Array.isArray(row)) {
          const obj = { ...(row as Record<string, unknown>) }
          for (const key of Object.keys(obj)) {
            if (PATH_COLUMN_RE.test(key)) delete obj[key]
            else obj[key] = scrubVisiblePathString(obj[key])
          }
          return obj
        }
        if (Array.isArray(row)) return row.map(scrubVisiblePathString)
        return scrubVisiblePathString(row)
      })
    }

    if (typeof props.title === 'string') props.title = scrubVisiblePathString(props.title) as string
    if (typeof props.subtitle === 'string') props.subtitle = scrubVisiblePathString(props.subtitle) as string
    if (typeof props.body === 'string') props.body = scrubVisiblePathString(props.body) as string
    return { ...block, props }
  }

  // Generic string prop scrub for summary cards etc.
  for (const [k, v] of Object.entries(props)) {
    if (typeof v === 'string') props[k] = scrubVisiblePathString(v) as string
  }
  return { ...block, props }
}

function parseJsonObject(raw: string): unknown {
  const trimmed = raw.trim().replace(/^```(?:json|ui-block)?\s*/i, '').replace(/```$/i, '').trim()
  try {
    return JSON.parse(trimmed)
  } catch {
    const match = trimmed.match(/(\{[\s\S]*\}|\[[\s\S]*\])/)
    if (!match) throw new Error('No JSON found')
    return JSON.parse(match[1])
  }
}

function loadBlockCatalog(): string {
  const catalogPath = path.join(process.cwd(), '..', 'agent-ui-blocks-extracted', 'agent-ui-blocks', 'references', 'block-catalog.md')
  return fs.readFileSync(catalogPath, 'utf8')
}

function loadSupportedBlockTypes(): Set<string> {
  try {
    const catalog = loadBlockCatalog()
    return new Set(Array.from(catalog.matchAll(/"type":\s*"([^"]+)"/g)).map((m) => m[1]))
  } catch {
    return new Set([
      'summary-card',
      'stat-grid',
      'stat-strip',
      'icon-list',
      'checklist',
      'stepper',
      'table',
      'data-table',
      'email-preview',
      'attachment',
      'key-value',
      'key-value-list',
      'employee-card-detailed',
      'employee-card-compact',
      'employee-card-contact',
    ])
  }
}

async function callConfiguredLlm(system: string, user: string): Promise<string | null> {
  const provider = (process.env.LLM_PROVIDER || process.env.CANVAS_LLM_PROVIDER || '').toLowerCase()
  const timeoutMs = Number(process.env.CANVAS_LLM_TIMEOUT_MS || 15000)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    if (provider === 'openai' && process.env.OPENAI_API_KEY) {
      const baseUrl = (process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, '')
      const res = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
        body: JSON.stringify({
          model: process.env.CANVAS_OPENAI_MODEL || process.env.OPENAI_MODEL || 'gpt-4o-mini',
          temperature: 0,
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
        }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`OpenAI ${res.status}`)
      const data = await res.json()
      return data?.choices?.[0]?.message?.content || null
    }
    if (provider === 'groq' && process.env.GROQ_API_KEY) {
      const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.GROQ_API_KEY}` },
        body: JSON.stringify({
          model: process.env.CANVAS_GROQ_MODEL || process.env.GROQ_MODEL || 'llama-3.1-8b-instant',
          temperature: 0,
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
        }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`Groq ${res.status}`)
      const data = await res.json()
      return data?.choices?.[0]?.message?.content || null
    }
    if (provider === 'ollama') {
      const baseUrl = (process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434').replace(/\/$/, '')
      const res = await fetch(`${baseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: process.env.CANVAS_OLLAMA_MODEL || process.env.OLLAMA_MODEL || 'llama3.1',
          stream: false,
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
        }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`Ollama ${res.status}`)
      const data = await res.json()
      return data?.message?.content || null
    }
  } finally {
    clearTimeout(timer)
  }
  return null
}

const COSMOS_META_KEYS = new Set(['_rid', '_self', '_etag', '_attachments', '_ts'])

function stringField(obj: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = obj[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  }
  return ''
}

function personName(obj: Record<string, unknown>): string {
  const direct = stringField(obj, 'name', 'fullName', 'full_name', 'displayName')
  if (direct) return direct
  return [obj.firstName || obj.first_name, obj.lastName || obj.last_name]
    .filter((part) => typeof part === 'string' && part.trim())
    .join(' ')
    .trim()
}

function looksLikePerson(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const obj = value as Record<string, unknown>
  const name = personName(obj)
  if (!name) return false
  const identity = stringField(
    obj,
    'employeeId',
    'employee_id',
    'workEmail',
    'email',
    'jobTitle',
    'title',
    'departmentName',
    'department',
    'managerName',
    'manager',
    'hireDate',
    'start_date',
  )
  return Boolean(identity || obj.recordType === 'employees')
}

function isNotFoundPayload(payload: unknown): boolean {
  if (!payload) return false
  if (typeof payload === 'object' && !Array.isArray(payload) && (payload as any).found === false) return true
  if (typeof payload === 'string') {
    return /no (employee|results?) (matched|found)|not found/i.test(payload)
  }
  return false
}

function parseFormattedQueryResults(text: string): { documents: Record<string, unknown>[] } | null {
  if (!text || !/^(Results:|Document \d+:)/m.test(text)) return null
  const documents: Record<string, unknown>[] = []
  let current: Record<string, unknown> | null = null
  for (const line of text.split('\n')) {
    if (/^Document \d+:\s*$/.test(line.trim())) {
      if (current && Object.keys(current).length > 0) documents.push(current)
      current = {}
      continue
    }
    const match = line.match(/^\s{2}([A-Za-z0-9_]+):\s*(.*)$/)
    if (!match || !current) continue
    const key = match[1]
    if (COSMOS_META_KEYS.has(key) || key.startsWith('_')) continue
    current[key] = parseMaybeJson(match[2])
  }
  if (current && Object.keys(current).length > 0) documents.push(current)
  return documents.length > 0 ? { documents } : null
}

function coerceObservationText(text: string): unknown {
  const parsed = parseMaybeJson(text)
  if (parsed !== text) return parsed
  const formatted = parseFormattedQueryResults(text)
  return formatted || text
}

function unwrapObservationValue(observation: any): unknown {
  if (!observation) return null
  const content = observation.content
  if (Array.isArray(content) && content.length > 0 && content.every(isMcpContentPart)) {
    const text = content
      .map((part: any) => (typeof part.text === 'string' ? part.text : ''))
      .join('\n')
      .trim()
    return text ? coerceObservationText(text) : null
  }
  const raw = observation.result ?? content ?? observation.data ?? observation.text
  if (raw == null) return null
  if (typeof raw === 'string') return coerceObservationText(raw)
  return parseMaybeJson(raw)
}

function extractPersonRecords(payload: unknown): Record<string, unknown>[] {
  if (!payload || isNotFoundPayload(payload)) return []
  if (Array.isArray(payload)) {
    return payload.flatMap((item) => extractPersonRecords(item))
  }
  if (typeof payload !== 'object') return []
  const obj = payload as Record<string, unknown>
  if (looksLikePerson(obj.employee)) return [obj.employee as Record<string, unknown>]
  if (looksLikePerson(obj)) return [obj]
  const nestedKeys = ['documents', 'items', 'results', 'rows', 'employees', 'records']
  for (const key of nestedKeys) {
    if (Array.isArray(obj[key])) {
      const people = (obj[key] as unknown[]).filter(looksLikePerson) as Record<string, unknown>[]
      if (people.length > 0) return people
    }
  }
  return []
}

function displayValue(value: unknown): string {
  if (value == null || value === '') return ''
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function personDetailPairs(person: Record<string, unknown>): { key: string; value: string }[] {
  const pairs: { key: string; value: string }[] = []
  const push = (key: string, ...fields: string[]) => {
    const value = stringField(person, ...fields)
    if (value) pairs.push({ key, value })
  }
  push('Employee ID', 'employeeId', 'employee_id', 'id')
  push('Title', 'title', 'jobTitle', 'role')
  push('Department', 'department', 'departmentName', 'team')
  push('Email', 'email', 'workEmail')
  push('Manager', 'manager', 'managerName')
  push('Location', 'location', 'workLocationName')
  push('Start date', 'start_date', 'hireDate')
  push('Type', 'employment_type', 'employmentType')
  push('Status', 'status', 'employmentStatus')
  const salary = person.salary
  if (typeof salary === 'number') {
    const currency = stringField(person, 'currency') || 'USD'
    pairs.push({ key: 'Salary', value: `${currency} ${salary.toLocaleString()}` })
  } else if (salary && typeof salary === 'object') {
    const amount = displayValue((salary as any).amount ?? (salary as any).base ?? salary)
    if (amount && amount !== '{}' ) pairs.push({ key: 'Salary', value: amount })
  }
  return pairs.filter((pair, index, all) => all.findIndex((item) => item.key === pair.key) === index)
}

function blocksFromPerson(person: Record<string, unknown>): CanvasBlock[] {
  const name = personName(person)
  if (!name) return []
  const role = stringField(person, 'title', 'jobTitle', 'role')
  const team = stringField(person, 'department', 'departmentName', 'team')
  const email = stringField(person, 'email', 'workEmail')
  const status = stringField(person, 'status', 'employmentStatus') || 'active'
  const start = stringField(person, 'start_date', 'hireDate')
  const pairs = personDetailPairs(person)
  const cardFields = new Set(['Title', 'Department', 'Email', 'Status', 'Employee ID', 'Manager', 'Location'])
  const extraPairs = pairs.filter((pair) => {
    if (cardFields.has(pair.key)) return false
    if (start && pair.key === 'Start date') return false
    return true
  })
  const blocks: CanvasBlock[] = [
    {
      type: extraPairs.length <= 1 && !email && !role ? 'employee-card-compact' : 'employee-card-detailed',
      version: 1,
      props: {
        name,
        role: role || undefined,
        team: team || undefined,
        status,
        email: email || undefined,
        tenure: start ? `Started ${start}` : undefined,
        manager: stringField(person, 'manager', 'managerName') || undefined,
        location: stringField(person, 'location', 'workLocationName') || undefined,
        employeeId: stringField(person, 'employeeId', 'employee_id', 'id') || undefined,
      },
    },
  ]
  if (extraPairs.length > 0) {
    blocks.push({
      type: 'key-value',
      version: 1,
      props: {
        title: `${name} — details`,
        pairs: extraPairs,
      },
    })
  }
  return blocks
}

function blocksFromStructuredPayload(payload: unknown, tool: string): CanvasBlock[] {
  if (!payload || isNotFoundPayload(payload)) return []
  const blocks: CanvasBlock[] = []
  const moduleName =
    payload && typeof payload === 'object' && !Array.isArray(payload)
      ? String((payload as any)._canvas?.module || '')
      : ''

  const people = extractPersonRecords(payload)
  if (people.length > 0 && people.length <= 3) {
    for (const person of people) blocks.push(...blocksFromPerson(person))
  }

  if (moduleName === 'pto' && payload && typeof payload === 'object') {
    const pto = (payload as any).pto
    if (pto && typeof pto === 'object') {
      const pairs = Object.entries(pto as Record<string, unknown>)
        .map(([key, value]) => ({ key: key.replace(/_/g, ' '), value: displayValue(value) }))
        .filter((pair) => pair.value)
      if (pairs.length) {
        blocks.push({ type: 'key-value', version: 1, props: { title: 'PTO balance', pairs } })
      }
    }
  } else if (moduleName === 'benefits' && payload && typeof payload === 'object') {
    const benefits = (payload as any).benefits
    if (benefits && typeof benefits === 'object' && !Array.isArray(benefits)) {
      const pairs = Object.entries(benefits as Record<string, unknown>)
        .map(([key, value]) => ({ key, value: displayValue(value) }))
        .filter((pair) => pair.value)
      if (pairs.length) {
        blocks.push({ type: 'key-value', version: 1, props: { title: 'Benefits', pairs } })
      }
    }
  } else if (moduleName === 'org_chart' && payload && typeof payload === 'object') {
    const obj = payload as any
    const pairs = [
      { key: 'Manager', value: displayValue(obj.manager) },
      { key: 'Peers', value: Array.isArray(obj.peers) ? String(obj.peers.length) : '' },
      { key: 'Reports', value: Array.isArray(obj.reports) ? String(obj.reports.length) : '' },
    ].filter((pair) => pair.value)
    if (pairs.length) {
      blocks.push({ type: 'key-value', version: 1, props: { title: 'Org chart', pairs } })
    }
  }

  if (people.length === 0 || people.length > 3) {
    const objectRows = tabularRowsFromPayload(payload)
    if (objectRows && objectRows.length > 0) {
      const columns = Array.from(
        objectRows.reduce((set, row) => {
          Object.keys(row).forEach((k) => set.add(k))
          return set
        }, new Set<string>()),
      ).slice(0, 8)
      if (columns.length > 0) {
        blocks.push({
          type: 'table',
          version: 1,
          props: {
            title: tableTitleForTool(tool),
            columns,
            rows: objectRows.slice(0, 40).map((row) => columns.map((c) => row[c] ?? '')),
          },
        })
      }
    }
  }

  return blocks
}

function hasExtractableWorkProduct(events: any[]): boolean {
  if (hasApprovalOrCommDraft(events)) return true
  for (const evt of events) {
    if (evt?.kind !== 'ObservationEvent') continue
    const tool = cleanId(evt?.tool_name) || ''
    if (PLUMBING_TOOL_RE.test(tool)) continue
    const payload = observationPayload(evt)
    if (isNotFoundPayload(payload)) continue
    if (extractPersonRecords(payload).length > 0) return true
    if (tabularRowsFromPayload(payload)) return true
    if (hasSubstantialStructuredPayload(payload)) return true
    if (typeof payload === 'string' && /(?:outputs|uploads)\/[^\s)]+\.(?:pdf|docx|xlsx|pptx|txt|csv|md)/i.test(payload)) {
      return true
    }
  }
  return false
}

function hasApprovalOrCommDraft(events: any[]): boolean {
  return (
    events.some((evt) => {
      const name = cleanId(evt?.tool_name) || ''
      return /^(send_email|send_slack_message|send_teams_message|upsert_document|replace_document|office_fill_|write_workspace_file)/.test(name)
    }) || events.some((evt) => readExecutionStatus(evt) === 'waiting_for_confirmation')
  )
}

function deterministicEvaluation(events: any[]): EvaluatorResult {
  const hasDraft = hasApprovalOrCommDraft(events)
  const numberedPlan = events.some(
    (evt) => isFinalAgentMessage(evt) && extractNumberedSteps(extractAgentMessageText(evt)).length >= 3,
  )
  const realTable = events.some((evt) => {
    if (evt?.kind !== 'ObservationEvent') return false
    const tool = cleanId(evt?.tool_name) || ''
    if (PLUMBING_TOOL_RE.test(tool)) return false
    return tabularRowsFromPayload(observationPayload(evt)) !== null
  })
  const hasPerson = events.some((evt) => {
    if (evt?.kind !== 'ObservationEvent') return false
    const tool = cleanId(evt?.tool_name) || ''
    if (PLUMBING_TOOL_RE.test(tool)) return false
    return extractPersonRecords(observationPayload(evt)).length > 0
  })
  const hasFile = events.some((evt) => {
    const blob = `${summarizeObservation(evt?.observation) || ''} ${extractAgentMessageText(evt)}`
    return /(?:outputs|uploads)\/[^\s)]+\.(?:pdf|docx|xlsx|pptx|txt|csv|md)/i.test(blob)
  })
  const agentText = events.filter((evt) => isFinalAgentMessage(evt)).map(extractAgentMessageText).join('\n')
  const stats = extractStatsFromText(agentText)
  const findings = extractFindingItems(agentText)
  const canvas_worthy =
    hasDraft || numberedPlan || realTable || hasPerson || hasFile || stats.length >= 1 || findings.length >= 2
  return {
    workflow_detected: canvas_worthy,
    canvas_worthy,
    workflow_type: hasDraft
      ? 'approval_draft'
      : hasPerson
        ? 'profile'
        : numberedPlan
          ? 'plan'
          : hasFile
            ? 'report'
            : realTable
              ? 'results'
              : stats.length
                ? 'metrics'
                : canvas_worthy
                  ? 'review'
                  : null,
    reason: canvas_worthy
      ? 'Deterministic: Canvas holds the work product (metrics, files, tables, drafts, next steps) — not a chat copy.'
      : 'No separate work product for Canvas.',
  }
}

async function evaluateWithFallback(
  conversationId: string,
  turnId: string | null,
  pose: Record<string, unknown>,
  events: any[],
): Promise<EvaluatorResult> {
  const deterministic = deterministicEvaluation(events)
  if (deterministic.canvas_worthy) {
    trace(conversationId, 'evaluator result', 'success', {
      turnId,
      fallback: true,
      skippedLlm: true,
      ...deterministic,
    })
    return deterministic
  }
  const dataObservations = events.filter((evt) => {
    if (evt?.kind !== 'ObservationEvent') return false
    const tool = cleanId(evt?.tool_name) || ''
    return !PLUMBING_TOOL_RE.test(tool)
  })
  // Tools ran but produced no canvasable work product (e.g. employee not found).
  // Do not let the LLM invent a hollow "Draft / Review / Details unavailable" shell.
  if (dataObservations.length > 0 && !hasExtractableWorkProduct(events)) {
    trace(conversationId, 'evaluator result', 'success', {
      turnId,
      fallback: true,
      skippedLlm: true,
      noWorkProduct: true,
      ...deterministic,
    })
    return deterministic
  }
  const system = [
    'Return only JSON with workflow_detected, canvas_worthy, workflow_type, and reason.',
    'Decide whether the user request plus result events produced a meaningful outcome/content surface.',
    'Plans, checklists, drafts, tables, reports, and long structured answers ARE canvas_worthy.',
    'Canvas is not for execution/audit reports, chat transcripts, tool calls, or generic activity logs.',
    'Small/simple scalar answers should usually stay in chat.',
  ].join(' ')
  const user = JSON.stringify({ pose, execution_events: events.map(redactEventForModel) })
  try {
    trace(conversationId, 'evaluator invoked', 'info', { turnId, count: events.length })
    const raw = await callConfiguredLlm(system, user)
    if (raw) {
      const parsed = parseEvaluatorResult(raw)
      if (parsed.canvas_worthy) {
        trace(conversationId, 'evaluator result', 'success', { turnId, ...parsed })
        return parsed
      }
    }
  } catch (error) {
    trace(conversationId, 'evaluator result', 'failure', {
      turnId,
      error: error instanceof Error ? error.message : String(error),
    })
  }
  trace(conversationId, 'evaluator result', 'success', { turnId, fallback: true, ...deterministic })
  return deterministic
}

async function generateWithFallback(conversationId: string, turnId: string | null, pose: Record<string, unknown>, events: any[], evaluation: EvaluatorResult): Promise<CanvasBlock[]> {
  const fallbackBlocks = buildDeterministicCanvasBlocks(events, evaluation)
  if (fallbackBlocks.length > 0) {
    trace(conversationId, 'generator result', 'success', { turnId, fallback: true, count: fallbackBlocks.length })
    return fallbackBlocks
  }
  const catalog = loadBlockCatalog()
  const system = [
    'Return only JSON. Generate supported Canvas block objects shaped {type,version,props}.',
    'Canvas is a generic outcome/content surface, not a fixed workflow UI and not an execution report.',
    'Dynamically decide the useful presentation for this specific task result using the available block catalog.',
    'Think like a product-minded work-product curator before choosing blocks.',
    'First identify: (1) what the user was trying to accomplish, (2) what the agent actually produced or retrieved, (3) which observed artifacts/results the user needs to inspect or use, and (4) which parts belong only in chat.',
    'The Canvas must represent the meaningful result/work product of the user task: the thing the user needs to inspect, compare, review, edit, reference, or use.',
    'Do not design around hard-coded task types. Examples like onboarding or employee lookup are only quality references, not special cases.',
    'Do not reproduce the chat transcript or execution timeline.',
    'Do not show tool names, MCP operations, database queries, container inspection, integration activation, internal reasoning, execution timings, or implementation details unless they are themselves meaningful user-facing artifacts.',
    'Use execution events only as evidence for determining which real artifacts, results, statuses, and outcomes exist.',
    'Infer the appropriate Canvas structure from the user request, final conversation context, observed result data, and available block catalog.',
    'Possible useful outputs include profiles, tables, comparisons, reports, metric strips, workflow state, forms, dashboards, read-only drafts, checklists, search results, and attachments. This list is illustrative, not exhaustive.',
    'NEVER emit freeform-card, chat-thread, or a summary-card that pastes the assistant chat message. Canvas is a separate work product, not a 1:1 copy of chat.',
    'NEVER turn tool/MCP content arrays (type/text/cache_prompt) or activate_integration / invoke_skill results into a data-table.',
    'Prefer stat-grid for headline numbers, attachment for generated files, data-table only for real record rows (employees, reqs, tickets), stepper/checklist for next steps, email-preview for drafts.',
    'Use multiple blocks when the result has meaningfully different sections. Put the most important overview first, then the primary artifact, then supporting details.',
    'Do not make every event into a block. Collapse low-level details into the user-facing outcome.',
    'Reference examples for selection quality, not implementation: if a task prepares onboarding content, Canvas might show the person/context, assigned benefits or setup facts, read-only email drafts, and next-step status. If a task retrieves a person record, Canvas might show identity/role plus structured fields. If a task compares requests, Canvas might show a short summary plus a sortable-looking table. If a task creates a report, Canvas might show key findings, sections, charts/tables when data exists, and source/status notes.',
    'These examples are not task rules. For any new task, derive the Canvas from the actual observed result and choose the closest supported generic blocks.',
    'Small/simple answers can remain chat-only; if generating blocks, include only content that adds value as a side workspace.',
    'Do not invent missing information or artifacts. If a useful section lacks observed data, omit that section entirely. Never emit placeholder copy such as "unavailable", "details unavailable", "pending", or "N/A" in place of real fields.',
    'When observations contain a person or HR record, Canvas MUST render identity plus every observed field (title, department, email, manager, location, start date, employment type, employee id, etc.) using employee-card-detailed and key-value / key-value-list. Never show a name-only subject card.',
    'Approval buttons belong in chat, never in Canvas. Canvas may show read-only drafts and approval status.',
    'For generated files (Markdown, PDF, CSV, DOCX): ALWAYS emit attachment (or file-attachment) blocks with props {filename, path, size?}. path may be the workspace-relative path for the UI to download — NEVER display outputs/, uploads/, Azure, Blob, Cosmos, MCP, or folder paths as visible labels, table columns, or body text. Visible filename only.',
    'Do NOT create a data-table whose columns are Artifact / Path / Notes for files — use attachment blocks instead.',
    'The Canvas should answer: "What does the user need to see to understand and work with the result?"',
  ].join(' ')
  const user = JSON.stringify({
    pose,
    execution_events: events.map(redactEventForModel),
    conversation_messages: events.filter((evt) => evt?.kind === 'MessageEvent').map(redactEventForModel),
    evaluator_result: evaluation,
    block_catalog: catalog.slice(0, 50000),
  })
  try {
    trace(conversationId, 'generator invoked', 'info', { turnId, workflowType: evaluation.workflow_type })
    const raw = await callConfiguredLlm(system, user)
    if (raw) {
      const blocks = validateCanvasBlocks(raw)
      trace(conversationId, 'generator result', 'success', { turnId, count: blocks.length })
      return blocks
    }
  } catch (error) {
    trace(conversationId, 'generator result', 'failure', { turnId, error: error instanceof Error ? error.message : String(error) })
  }
  trace(conversationId, 'generator result', 'failure', { turnId, fallback: true, error: 'No Canvas blocks available.' })
  return []
}

function extractAgentMessageText(evt: any): string {
  const fromLlm = textFromContent(evt?.llm_message?.content ?? evt?.llm_message)
  if (fromLlm) return fromLlm
  return textFromContent(evt?.content ?? evt?.message ?? evt?.text)
}

function textFromContent(content: unknown): string {
  if (typeof content === 'string') return content.trim()
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === 'string') return part
        if (part && typeof part === 'object') {
          const text = (part as any).text || (part as any).content
          return typeof text === 'string' ? text : ''
        }
        return ''
      })
      .join('\n')
      .trim()
  }
  if (content && typeof content === 'object') {
    const nested = (content as any).text || (content as any).content
    if (typeof nested === 'string') return nested.trim()
    if (Array.isArray(nested)) return textFromContent(nested)
  }
  return ''
}

function extractNumberedSteps(text: string): { label: string; sub?: string }[] {
  const steps: { label: string; sub?: string }[] = []
  const re = /^\s*\d+\.\s+(.*)$/gm
  let match: RegExpExecArray | null
  while ((match = re.exec(text)) !== null) {
    const label = (match[1] || '')
      .replace(/^\*\*(.+?)\*\*\s*/, '$1 — ')
      .replace(/\*\*/g, '')
      .trim()
    if (label) steps.push({ label: label.replace(/\s+/g, ' ').slice(0, 180) })
  }
  return steps
}

function buildDeterministicCanvasBlocks(events: any[], evaluation: EvaluatorResult): CanvasBlock[] {
  const blocks: CanvasBlock[] = []
  const seenFiles = new Set<string>()

  for (const evt of events) {
    if (evt?.kind !== 'ActionEvent') continue
    const tool = cleanId(evt?.tool_name) || ''
    const args = evt?.action?.args || evt?.action?.arguments || evt?.action || {}
    if (tool === 'send_email' && typeof args === 'object') {
      blocks.push({
        type: 'email-preview',
        version: 1,
        props: {
          title: 'Email draft',
          to: args.to || '',
          cc: args.cc || '',
          subject: args.subject || '',
          body: args.body || '',
          status: 'pending_approval',
        },
      })
    } else if ((tool === 'send_slack_message' || tool === 'send_teams_message') && typeof args === 'object') {
      blocks.push({
        type: 'key-value',
        version: 1,
        props: {
          title: tool === 'send_slack_message' ? 'Slack draft' : 'Teams draft',
          pairs: [
            { key: 'To', value: String(args.channel || args.recipient || '') },
            { key: 'Message', value: String(args.message || args.body || '').slice(0, 800) },
          ],
        },
      })
    } else if (
      tool === 'write_workspace_file' ||
      tool.startsWith('office_fill_') ||
      tool === 'office_template_fill' ||
      tool === 'office_overlay_pdf_text'
    ) {
      const rawPath =
        (typeof args === 'object' &&
          (args.path || args.output_path || args.file_path || args.filename)) ||
        null
      if (typeof rawPath === 'string') {
        const filePath = rawPath.replace(/\\/g, '/').trim()
        const filename = filePath.split('/').pop() || filePath
        if (filename && !seenFiles.has(filename)) {
          seenFiles.add(filename)
          blocks.push({
            type: 'attachment',
            version: 1,
            props: {
              filename,
              path: filePath,
            },
          })
        }
      }
    }
  }

  for (const evt of events) {
    if (evt?.kind !== 'ObservationEvent') continue
    const summary = summarizeObservation(evt?.observation) || ''
    const matches = summary.matchAll(
      /(?:outputs|uploads)\/[a-zA-Z0-9_\-./]+\.(?:pdf|docx|xlsx|pptx|txt|csv|md)/gi,
    )
    for (const m of matches) {
      const filePath = m[0]
      const filename = filePath.split('/').pop() || filePath
      if (seenFiles.has(filename)) continue
      seenFiles.add(filename)
      blocks.push({
        type: 'attachment',
        version: 1,
        props: { filename, path: filePath },
      })
    }
  }

  const agentTexts = events.filter((evt) => isFinalAgentMessage(evt)).map(extractAgentMessageText)
  const lastAgent = agentTexts[agentTexts.length - 1] || ''

  if (lastAgent) {
    const pathMatches = lastAgent.matchAll(
      /(?:outputs|uploads)\/[a-zA-Z0-9_\-./]+\.(?:pdf|docx|xlsx|pptx|txt|csv|md)/gi,
    )
    for (const m of pathMatches) {
      const filePath = m[0]
      const filename = filePath.split('/').pop() || filePath
      if (seenFiles.has(filename)) continue
      seenFiles.add(filename)
      blocks.push({
        type: 'attachment',
        version: 1,
        props: { filename, path: filePath },
      })
    }
    // Bare filenames mentioned as attached documents
    const bare = lastAgent.matchAll(
      /(?:attached|attachment)[^.!\n]{0,80}?([A-Za-z0-9][A-Za-z0-9 _\-.]{2,80}\.(?:pdf|docx|xlsx|pptx|txt|csv|md))/gi,
    )
    for (const m of bare) {
      const filename = m[1].trim()
      if (seenFiles.has(filename)) continue
      seenFiles.add(filename)
      blocks.push({
        type: 'attachment',
        version: 1,
        props: { filename, path: filename },
      })
    }
  }

  const stats = extractStatsFromText(lastAgent)
  if (stats.length > 0) {
    blocks.unshift({
      type: 'stat-grid',
      version: 1,
      props: {
        title: evaluation.workflow_type === 'report' ? 'Audit snapshot' : 'Key figures',
        stats,
      },
    })
  }

  const seenPeople = new Set<string>()
  for (const evt of events) {
    if (evt?.kind !== 'ObservationEvent') continue
    const tool = cleanId(evt?.tool_name) || ''
    if (PLUMBING_TOOL_RE.test(tool)) continue
    const structured = blocksFromStructuredPayload(observationPayload(evt), tool)
    for (const block of structured) {
      if (block.type.startsWith('employee-card')) {
        const name = String(block.props.name || '').toLowerCase()
        if (name && seenPeople.has(name)) continue
        if (name) seenPeople.add(name)
      }
      blocks.push(block)
    }
  }

  if (lastAgent) {
    const steps = extractNumberedSteps(lastAgent)
    const findings = extractFindingItems(lastAgent).filter((item) => {
      if (steps.length < 3) return true
      return !steps.some((step) => item.label.startsWith(step.label.slice(0, 24)))
    })
    if (findings.length >= 2) {
      blocks.push({
        type: 'icon-list',
        version: 1,
        props: {
          title: 'Findings',
          items: findings.slice(0, 8),
        },
      })
    }
    if (steps.length >= 3) {
      blocks.push({
        type: 'stepper',
        version: 1,
        props: {
          title: 'Recommended next steps',
          steps: steps.slice(0, 12).map((step, i) => ({
            ...step,
            status: i === 0 ? 'active' : 'pending',
          })),
        },
      })
    }
  }

  return sanitizeCanvasBlocks(blocks)
}

function tableTitleForTool(tool: string): string {
  if (/query_cosmos|employee/i.test(tool)) return 'Records'
  if (/list_email/i.test(tool)) return 'Inbox'
  if (/list_slack|channel/i.test(tool)) return 'Channels'
  if (/requisition|recruit/i.test(tool)) return 'Open roles'
  return 'Results'
}

function extractStatsFromText(text: string): { value: string; label: string }[] {
  if (!text) return []
  const seen = new Set<string>()
  const stats: { value: string; label: string }[] = []
  const patterns: Array<[RegExp, string]> = [
    [/(\d[\d,]*)\s+(?:total\s+)?employee records/i, 'Employee records'],
    [/(\d[\d,]*)\s+employees\b/i, 'Employees'],
    [/headcount[:\s]+(\d[\d,]*)/i, 'Headcount'],
    [/(\d[\d,]*)\s+open requisitions/i, 'Open requisitions'],
    [/(\d[\d,]*)\s+open roles/i, 'Open roles'],
    [/~?(\d+)\s+days?\s+open/i, 'Days open'],
  ]
  for (const [re, label] of patterns) {
    const match = text.match(re)
    if (!match) continue
    const value = match[1]
    if (seen.has(label) || value === '2026') continue
    seen.add(label)
    stats.push({ value, label })
  }
  return stats.slice(0, 4)
}

function extractFindingItems(text: string): { label: string; icon: string }[] {
  const items: { label: string; icon: string }[] = []
  for (const line of text.split('\n')) {
    const match = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/)
    if (!match) continue
    const label = match[1].replace(/\*\*/g, '').replace(/\s+/g, ' ').trim()
    if (label.length < 16) continue
    if (/^next action|^i(?:'ve| have) attached|^open the linked/i.test(label)) continue
    items.push({
      label: label.slice(0, 220),
      icon: /gap|missing|risk|cannot|can’t|can't|exception|compliance/i.test(label) ? 'warning' : 'info',
    })
  }
  return items.slice(0, 8)
}

function isMcpContentPart(value: unknown): boolean {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const obj = value as Record<string, unknown>
  return typeof obj.type === 'string' && (typeof obj.text === 'string' || 'cache_prompt' in obj)
}

function tabularRowsFromPayload(payload: unknown): Record<string, unknown>[] | null {
  if (!payload) return null
  let rows: unknown[] | null = null
  if (Array.isArray(payload)) rows = payload
  else if (typeof payload === 'object') {
    const obj = payload as Record<string, unknown>
    for (const key of ['documents', 'items', 'results', 'rows', 'employees', 'records', 'channels']) {
      if (Array.isArray(obj[key])) {
        rows = obj[key] as unknown[]
        break
      }
    }
  }
  if (!rows || rows.length === 0) return null
  if (!rows.every((row) => row && typeof row === 'object' && !Array.isArray(row))) return null
  const objects = rows as Record<string, unknown>[]
  if (objects.every(isMcpContentPart)) return null
  const keys = new Set(objects.flatMap((row) => Object.keys(row)))
  if (keys.has('cache_prompt') && keys.has('type')) return null
  if (keys.has('type') && keys.has('text') && keys.size <= 4) return null
  const cleaned = objects.slice(0, 40).map((row) =>
    Object.fromEntries(
      Object.entries(row)
        .filter(([k]) => !k.startsWith('_') && !PATH_COLUMN_RE.test(k) && k !== 'cache_prompt')
        .slice(0, 8)
        .map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : v]),
    ),
  )
  if (cleaned.length === 0 || Object.keys(cleaned[0]).length === 0) return null
  return cleaned
}

function redactEventForModel(evt: any) {
  const payload = observationPayload(evt)
  let observationPayloadForModel: unknown = payload
  if (typeof payload === 'string' && payload.length > 12000) {
    observationPayloadForModel = payload.slice(0, 12000)
  }
  return {
    kind: evt?.kind,
    source: evt?.source,
    tool_name: evt?.tool_name,
    tool_call_id: evt?.tool_call_id,
    status: readExecutionStatus(evt),
    is_error: !!evt?.observation?.is_error,
    action: evt?.action ? { name: evt.action.name, args: evt.action.args || evt.action.arguments } : undefined,
    observation_payload: observationPayloadForModel,
    observation_summary: summarizeObservation(evt?.observation),
    message_text: isFinalAgentMessage(evt) ? extractAgentMessageText(evt).slice(0, 2000) : undefined,
  }
}

function summarizeObservation(observation: any): string | undefined {
  if (!observation) return undefined
  const unwrapped = unwrapObservationValue(observation)
  const text = typeof unwrapped === 'string' ? unwrapped : JSON.stringify(unwrapped ?? observation)
  const scrubbed = text.replace(/api[_-]?key|token|secret|password/gi, '[redacted]')
  // Keep emails/names/titles — Canvas is the HR work surface, not a public page.
  return scrubbed.slice(0, 8000)
}

function parseMaybeJson(value: unknown): unknown {
  if (typeof value !== 'string') return value
  const trimmed = value.trim()
  if (!trimmed || !/^[\[{]/.test(trimmed)) return value
  try {
    return JSON.parse(trimmed)
  } catch {
    return value
  }
}

function observationPayload(evt: any): any {
  return unwrapObservationValue(evt?.observation)
}

function observationTextLength(evt: any): number {
  const payload = observationPayload(evt)
  if (typeof payload === 'string') return payload.trim().length
  return stringifyForSearch(payload).length
}

function isScalarPayload(value: unknown): boolean {
  if (value == null) return true
  if (['string', 'number', 'boolean'].includes(typeof value)) return true
  if (Array.isArray(value)) return value.length <= 1 && value.every(isScalarPayload)
  if (typeof value !== 'object') return true
  const entries = Object.entries(value as Record<string, unknown>)
  return entries.length <= 2 && entries.every(([, nested]) => isScalarPayload(nested))
}

function hasSubstantialStructuredPayload(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  if (isNotFoundPayload(value)) return false
  if (Array.isArray(value)) {
    if (value.length === 0) return false
    if (value.every(isMcpContentPart)) return false
    return tabularRowsFromPayload(value) !== null
  }
  if (isMcpContentPart(value)) return false
  if (tabularRowsFromPayload(value) !== null) return true
  const entries = Object.entries(value as Record<string, unknown>)
  if (entries.length >= 3) return true
  return entries.some(([, nested]) => hasSubstantialStructuredPayload(nested))
}

function stringifyForSearch(value: unknown): string {
  try {
    return JSON.stringify(value)
  } catch {
    return String(value ?? '')
  }
}

async function runPipeline(record: ConversationRecord, terminal: string) {
  record.pendingTerminalKey = null
  record.pendingTerminalTimer = null
  if (record.processing || record.processedTerminalKey === terminal) {
    trace(record.conversationId, 'terminal deduped', 'info', { turnId: record.turnId, terminal })
    return
  }
  record.processing = true
  record.state = { ...record.state, status: 'evaluating', updatedAt: nowIso() }
  persistCanvasState(record.state)
  try {
    const pose = summarizePose(record)
    trace(record.conversationId, 'pre-filter invoked', 'info', { turnId: record.turnId, count: record.events.length })
    const prefilter = shouldEvaluateCanvas(pose, record.events)
    trace(record.conversationId, 'pre-filter result', 'success', { turnId: record.turnId, candidate: prefilter.candidate, ...prefilter.reason })
    if (!prefilter.candidate) {
      record.processedTerminalKey = terminal
      record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'skipped', blocks: [], updatedAt: nowIso() }
      persistCanvasState(record.state)
      return
    }
    const evaluation = await evaluateWithFallback(record.conversationId, record.turnId, pose, record.events)
    if (!evaluation.canvas_worthy) {
      record.processedTerminalKey = terminal
      record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'skipped', blocks: [], updatedAt: nowIso() }
      persistCanvasState(record.state)
      return
    }
    const blocks = await generateWithFallback(record.conversationId, record.turnId, pose, record.events, evaluation)
    record.processedTerminalKey = terminal
    if (blocks.length === 0) {
      record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'skipped', blocks: [], updatedAt: nowIso() }
      persistCanvasState(record.state)
      trace(record.conversationId, 'canvas state written', 'success', { turnId: record.turnId, count: 0, stateStatus: 'skipped' })
      return
    }
    record.state = { conversationId: record.conversationId, turnId: record.turnId, status: 'ready', blocks, updatedAt: nowIso() }
    persistCanvasState(record.state)
    trace(record.conversationId, 'canvas state written', 'success', { turnId: record.turnId, count: blocks.length })
  } catch (error) {
    record.state = {
      conversationId: record.conversationId,
      turnId: record.turnId,
      status: 'error',
      blocks: [],
      error: error instanceof Error ? error.message : String(error),
      updatedAt: nowIso(),
    }
    persistCanvasState(record.state)
    trace(record.conversationId, 'canvas pipeline failed', 'failure', { turnId: record.turnId, error: record.state.error })
  } finally {
    record.processing = false
  }
}

function schedulePipeline(record: ConversationRecord, terminal: string) {
  if (record.processedTerminalKey === terminal || record.pendingTerminalKey === terminal) return
  if (record.pendingTerminalTimer) clearTimeout(record.pendingTerminalTimer)
  record.pendingTerminalKey = terminal
  record.pendingTerminalTimer = setTimeout(() => {
    void runPipeline(record, terminal)
  }, 300)
}

export async function recordCanvasEvents(conversationId: string, events: any[]) {
  conversationId = normalizeConversationId(conversationId)
  const record = getRecord(conversationId)
  trace(conversationId, 'execution event received', 'info', { count: events.length })
  events.forEach((evt, index) => {
    const key = eventKey(evt, index)
    if (evt?.kind === 'StreamingDeltaEvent') return
    if (
      (evt?.kind === 'ActionEvent' || evt?.kind === 'ObservationEvent' || isFinalAgentMessage(evt)) &&
      record.processedTerminalKey &&
      !record.processing &&
      record.state.status !== 'empty'
    ) {
      const previousCount = record.events.length
      record.state = emptyState(conversationId)
      record.events = []
      record.eventKeys.clear()
      record.terminalKeys.clear()
      record.processedTerminalKey = null
      persistCanvasState(record.state)
      trace(conversationId, 'canvas state cleared for new turn', 'success', { previousCount })
    }
    if (!record.eventKeys.has(key)) {
      record.eventKeys.add(key)
      record.events.push(evt)
    }
    const terminal = terminalKey(evt, record)
    if (terminal && !record.terminalKeys.has(terminal)) {
      record.terminalKeys.add(terminal)
      trace(conversationId, 'terminal conversation event received', 'success', { turnId: record.turnId, status: readExecutionStatus(evt) })
      schedulePipeline(record, terminal)
    }
    if (isFinalAgentMessage(evt)) {
      const messageTerminal = `message:${key}`
      if (!record.terminalKeys.has(messageTerminal)) {
        record.terminalKeys.add(messageTerminal)
        record.turnId = cleanId(evt?.id) || cleanId(evt?.event_id) || messageTerminal
        trace(conversationId, 'final agent message received', 'success', { turnId: record.turnId })
        schedulePipeline(record, messageTerminal)
      }
    }
  })
  trace(conversationId, 'execution events accumulated', 'success', { turnId: record.turnId, count: record.events.length })
}

export async function recordCanvasConversation(conversation: any) {
  const rawConversationId = cleanId(conversation?.id) || cleanId(conversation?.conversation_id)
  const conversationId = rawConversationId ? normalizeConversationId(rawConversationId) : null
  if (!conversationId) return
  const record = getRecord(conversationId)
  record.pose = { ...record.pose, title: conversation?.title, execution_status: conversation?.execution_status }
  trace(conversationId, 'conversation webhook received', 'success', { status: readExecutionStatus(conversation) })
}

export function readCanvasState(conversationId: string): CanvasStatePayload {
  conversationId = normalizeConversationId(conversationId)
  const record = records.get(conversationId)
  trace(conversationId, 'canvas state requested', 'info')
  let state = record?.state
  if (!state || (state.status === 'empty' && state.blocks.length === 0)) {
    const persisted = loadPersistedCanvasState(conversationId)
    if (persisted && (persisted.blocks.length > 0 || persisted.status === 'ready' || persisted.status === 'evaluating')) {
      state = persisted
      if (record) record.state = persisted
    }
  }
  state = state || emptyState(conversationId)
  if (state.blocks.length > 0) {
    try {
      state = { ...state, blocks: sanitizeCanvasBlocks(state.blocks) }
    } catch {
      /* keep as-is if scrub fails */
    }
  }
  trace(conversationId, 'canvas state returned', 'success', { turnId: state.turnId, status: state.status, count: state.blocks.length })
  return state
}
