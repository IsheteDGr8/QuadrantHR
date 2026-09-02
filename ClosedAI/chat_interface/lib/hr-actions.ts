// Shared definitions for the HR "action" client tools (email / Slack / Teams).
//
// These are registered with the backend as `client_tools` (see app/api/chat/
// route.ts): when the agent calls one, the backend emits an ActionEvent over
// the WebSocket and immediately acks — it does NOT perform the action. The
// frontend surfaces an "Approve & Send" card in chat, and the human is the
// enforcement point: nothing is sent until they approve.
//
// This module is framework-neutral (no React / no zustand) so it can be
// imported by both the server route and client components as a single source
// of truth for the tool names, schemas, and presentation metadata.

// Minimal shape of the backend's ClientToolSpec (a JSON-Schema object for
// `parameters`). Kept local so we don't couple to backend types.
export interface ClientToolSpec {
  name: string
  description: string
  parameters: {
    type: 'object'
    properties: Record<string, unknown>
    required?: string[]
  }
  annotations?: {
    readOnlyHint?: boolean
  }
}

export type HrActionKind = 'email' | 'slack' | 'teams'

const HITL_NOTE =
  'This does NOT send immediately: the draft is shown to the HR user for ' +
  'approval in chat and is only delivered after they click "Approve & Send". ' +
  'Provide a complete, ready-to-send draft. After calling this tool, tell the ' +
  'user you have prepared it for review in Canvas and approval in chat — do not claim it ' +
  'has already been sent.'

/** Inbox / workspace reads — executed server-side immediately (no Approve & Send card). */
export const HR_EMAIL_READ_TOOLS: ClientToolSpec[] = [
  {
    name: 'list_emails',
    description:
      'Read recent messages from the linked email inbox via Gmail API. ' +
      'Preferred for inbox triage / summarize-recent-mail (security_risk=LOW). ' +
      'After results, write a Markdown summary file in the workspace when asked. ' +
      'If this fails, activate_integration("gmail") and use Gmail read/search tools.',
    parameters: {
      type: 'object',
      properties: {
        max_results: {
          type: 'number',
          description: 'How many recent messages to fetch (1–25). Default 10.',
        },
        query: {
          type: 'string',
          description:
            'Gmail search query. Default "in:inbox". Examples: "in:inbox newer_than:7d", "is:unread".',
        },
      },
      required: [],
    },
    annotations: { readOnlyHint: true },
  },
  {
    name: 'list_slack_channels',
    description:
      'List Slack channels visible to the linked Slack workspace (security_risk=LOW). ' +
      'Call this before send_slack_message. After this returns, immediately call ' +
      'send_slack_message if the user already named a channel — do not stop to ask. ' +
      'If this fails, still call send_slack_message with the user-named channel.',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum channels to return (default 200).',
        },
      },
      required: [],
    },
    annotations: { readOnlyHint: true },
  },
]

export const HR_ACTION_TOOLS: ClientToolSpec[] = [
  {
    name: 'send_email',
    description: `Prepare an email to send on the HR user's behalf. ${HITL_NOTE}`,
    parameters: {
      type: 'object',
      properties: {
        to: { type: 'string', description: 'Primary recipient email address.' },
        cc: { type: 'string', description: 'Optional CC recipients (comma-separated).' },
        subject: { type: 'string', description: 'Email subject line.' },
        body: { type: 'string', description: 'Full email body, ready to send.' },
        attachments: {
          type: 'array',
          items: { type: 'string' },
          description:
            'Workspace-relative paths to attach (e.g. outputs/i9_form_Joseph_Johnson_final_pending_signatures.pdf or i9_form.pdf). Required when emailing a generated form or document.',
        },
      },
      required: ['to', 'subject', 'body'],
    },
  },
  {
    name: 'send_slack_message',
    description:
      `Send a Slack message on the HR user's behalf after approval. ${HITL_NOTE} ` +
      'If the user already named a channel (e.g. #all-hr-agent), use that name. ' +
      'Call list_slack_channels first when possible, then send in the same turn. ' +
      'Do not invent a channel the user did not name.',
    parameters: {
      type: 'object',
      properties: {
        channel: {
          type: 'string',
          description: 'Target Slack channel (e.g. "#people-ops") or user (e.g. "@sarah").',
        },
        message: { type: 'string', description: 'Full message text, ready to send.' },
      },
      required: ['channel', 'message'],
    },
  },
  {
    name: 'send_teams_message',
    description: `Prepare a Microsoft Teams message to send on the HR user's behalf. ${HITL_NOTE}`,
    parameters: {
      type: 'object',
      properties: {
        recipient: {
          type: 'string',
          description: 'Target Teams recipient (person name/email or channel).',
        },
        message: { type: 'string', description: 'Full message text, ready to send.' },
      },
      required: ['recipient', 'message'],
    },
  },
]

/** All client tools registered on new conversations (reads + HITL sends). */
export const HR_CLIENT_TOOLS: ClientToolSpec[] = [
  ...HR_EMAIL_READ_TOOLS,
  ...HR_ACTION_TOOLS,
]

export const HR_ACTION_KIND: Record<string, HrActionKind> = {
  send_email: 'email',
  send_slack_message: 'slack',
  send_teams_message: 'teams',
}

export const HR_ACTION_TOOL_NAMES: ReadonlySet<string> = new Set(
  HR_ACTION_TOOLS.map((t) => t.name),
)

export function isHrActionTool(name: string): boolean {
  return HR_ACTION_TOOL_NAMES.has(name)
}

const KIND_LABEL: Record<HrActionKind, string> = {
  email: 'Email',
  slack: 'Slack message',
  teams: 'Teams message',
}

function recipientOf(toolName: string, params: Record<string, any>): string {
  switch (HR_ACTION_KIND[toolName]) {
    case 'email':
      return params.to || 'recipient'
    case 'slack':
      return params.channel || 'channel'
    case 'teams':
      return params.recipient || 'recipient'
    default:
      return 'recipient'
  }
}

/** Canvas artifact title, e.g. "Email to sarah.chen@example.com". */
export function actionTitle(toolName: string, params: Record<string, any>): string {
  const kind = HR_ACTION_KIND[toolName]
  const label = kind ? KIND_LABEL[kind] : 'Action'
  return `${label} to ${recipientOf(toolName, params)}`
}

/** Reasoning-stepper title, e.g. "Prepared email for approval". */
export function actionStepTitle(toolName: string, params: Record<string, any>): string {
  const kind = HR_ACTION_KIND[toolName]
  const label = kind ? KIND_LABEL[kind].toLowerCase() : 'action'
  void params
  return `Prepared ${label} for approval`
}
