import { NextRequest, NextResponse } from 'next/server'

const HRAGENT_API_URL = (process.env.HRAGENT_API_URL || 'http://127.0.0.1:8001').replace(/\/$/, '')
const SESSION_API_KEY = process.env.HRAGENT_SESSION_API_KEY || ''

function backendHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (SESSION_API_KEY) headers['X-Session-API-Key'] = SESSION_API_KEY
  return headers
}

/**
 * Re-apply HITL on an already-created conversation. Old chats persisted
 * NeverConfirm / no analyzer, so Settings and New Chat alone never recovered them.
 */
export async function POST(request: NextRequest) {
  let body: { conversationId?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
  }

  const conversationId = body.conversationId
  if (!conversationId) {
    return NextResponse.json({ error: 'conversationId is required' }, { status: 400 })
  }

  const headers = backendHeaders({ 'Content-Type': 'application/json' })
  const policyRes = await fetch(
    `${HRAGENT_API_URL}/api/conversations/${conversationId}/confirmation_policy`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        policy: { kind: 'ConfirmRisky', confirm_unknown: false },
      }),
    },
  )
  if (!policyRes.ok) {
    const detail = await policyRes.json().catch(() => null)
    return NextResponse.json(
      { error: detail?.detail || 'Failed to set confirmation policy' },
      { status: policyRes.status || 502 },
    )
  }

  await fetch(`${HRAGENT_API_URL}/api/conversations/${conversationId}/security_analyzer`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      security_analyzer: { kind: 'LLMSecurityAnalyzer' },
    }),
  }).catch(() => {
    /* analyzer is best-effort; forced-HIGH tools still pause without it */
  })

  return NextResponse.json({ success: true })
}
