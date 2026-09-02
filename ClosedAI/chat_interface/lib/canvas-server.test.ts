import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseEvaluatorResult,
  readCanvasState,
  recordCanvasEvents,
  shouldEvaluateCanvas,
  validateCanvasBlocks,
} from './canvas-server'

function action(tool_name: string, tool_call_id: string, args: Record<string, unknown> = {}) {
  return { kind: 'ActionEvent', tool_name, tool_call_id, action: { name: tool_name, args } }
}

function observation(tool_name: string, tool_call_id: string, content: unknown = undefined, is_error = false) {
  return { kind: 'ObservationEvent', tool_name, tool_call_id, observation: { is_error, content } }
}

function terminal(id: string) {
  return { kind: 'MessageEvent', source: 'agent', id, llm_message: { role: 'assistant', content: 'Done.' } }
}

function waitForPipeline() {
  return new Promise((resolve) => setTimeout(resolve, 450))
}

test('pre-filter skips simple prose with no execution evidence', () => {
  const result = shouldEvaluateCanvas({ intent: 'conversation' }, [])
  assert.equal(result.candidate, false)
})

test('pre-filter sends arbitrary structured outcomes to evaluator', () => {
  const result = shouldEvaluateCanvas(
    { intent: 'show compiled result bundle' },
    [
      action('compile_result_bundle', '1'),
      observation('compile_result_bundle', '1', {
        title: 'Quarterly planning bundle',
        owner: 'Operations',
        rows: [
          { item: 'Budget', status: 'ready', value: '$120k' },
          { item: 'Hiring plan', status: 'needs review', value: '4 roles' },
        ],
      }),
    ],
  )
  assert.equal(result.candidate, true)
  assert.equal(result.reason.structuredOutcome, true)
})

test('pre-filter can consider generic multi-step work without assigning a Canvas type', () => {
  const result = shouldEvaluateCanvas(
    { intent: 'review dependent workflow results' },
    [
      action('collect_inputs', '1'),
      observation('collect_inputs', '1', { ok: true }),
      action('prepare_drafts', '2'),
      observation('prepare_drafts', '2', { count: 2 }),
      action('summarize_status', '3'),
      observation('summarize_status', '3', { pending: 1 }),
    ],
  )
  assert.equal(result.candidate, true)
  assert.equal(result.reason.batchOrMultiStep, true)
})

test('evaluator parsing rejects malformed responses safely', () => {
  assert.throws(() => parseEvaluatorResult('not json'), /No JSON found/)
  assert.throws(() => parseEvaluatorResult(null), /no JSON object/i)
})

test('evaluator parsing normalizes missing optional fields', () => {
  const result = parseEvaluatorResult('{"workflow_detected":true,"canvas_worthy":true}')
  assert.deepEqual(result, {
    workflow_detected: true,
    canvas_worthy: true,
    workflow_type: null,
    reason: '',
  })
})

test('generator validation accepts only supported generic block payloads', () => {
  const blocks = validateCanvasBlocks({
    blocks: [
      { type: 'summary-card', version: 1, props: { title: 'Result', body: 'Ready for review.' } },
      { type: 'made-up-block', version: 1, props: {} },
    ],
  }, new Set(['summary-card']))
  assert.equal(blocks.length, 1)
  assert.equal(blocks[0].type, 'summary-card')
})

test('generator validation rejects empty or unsupported output', () => {
  assert.throws(() => validateCanvasBlocks({ blocks: [] }), /no supported/i)
  assert.throws(() => validateCanvasBlocks({ type: 'unknown', version: 1, props: {} }, new Set(['table'])), /no supported/i)
})

test('generator validation removes approval controls from Canvas blocks', () => {
  const blocks = validateCanvasBlocks({
    blocks: [
      { type: 'approval-card', version: 1, props: { title: 'Send email' } },
      { type: 'email-preview', version: 1, props: { subject: 'Welcome', actions: ['send', 'discard'] } },
    ],
  }, new Set(['approval-card', 'email-preview']))
  assert.equal(blocks.length, 1)
  assert.equal(blocks[0].type, 'email-preview')
  assert.equal('actions' in blocks[0].props, false)
})

test('generator validation drops freeform chat-dump blocks', () => {
  assert.throws(
    () => validateCanvasBlocks({
      blocks: [{ type: 'freeform-card', version: 1, props: { title: 'Draft', body: 'Full write-up — chat stays short. '.repeat(20) } }],
    }, new Set(['freeform-card', 'summary-card'])),
    /no supported/i,
  )
})

test('new turn does not reuse prior scalar lookup evidence', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `turn-scope-${Date.now()}`
    await recordCanvasEvents(conversationId, [
      action('lookup_scalar_value', '1'),
      observation('lookup_scalar_value', '1', { remaining: 12 }),
      terminal('lookup-turn'),
    ])
    await waitForPipeline()
    assert.equal(readCanvasState(conversationId).status, 'skipped')

    await recordCanvasEvents(conversationId, [
      action('compile_result_bundle', '1', { title: 'Planning packet' }),
      observation('compile_result_bundle', '1', {
        title: 'Planning packet',
        sections: [
          { label: 'Budget', status: 'ready' },
          { label: 'Risks', status: 'review' },
        ],
        draft: {
          subject: 'Planning update',
          body: 'Here is the structured planning update for review.',
        },
      }),
      terminal('structured-turn'),
    ])
    await waitForPipeline()

    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'skipped')
    assert.deepEqual(state.blocks, [])
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

test('simple scalar lookup still stays out of Canvas', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `scalar-${Date.now()}`
    await recordCanvasEvents(conversationId, [
      action('lookup_scalar_value', '1', { key: 'remaining_days' }),
      observation('lookup_scalar_value', '1', { remaining_days: 12 }),
      terminal('scalar-turn'),
    ])
    await waitForPipeline()

    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'skipped')
    assert.deepEqual(state.blocks, [])
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

test('long agent plan lands in Canvas without an extra evaluator veto', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `plan-${Date.now()}`
    const plan = [
      'Treat this as a restricted ER case and progress it today.',
      '',
      '### Recommended next steps',
      '',
      '1. **Assign restricted ownership** and lock down access.',
      '2. **Triage for immediate safety** and legal risk.',
      '3. **Open the report** in the restricted view only.',
      '4. **Decide the initial handling path**.',
      '5. **Send same-day acknowledgement**.',
    ].join('\n')
    await recordCanvasEvents(conversationId, [
      {
        kind: 'MessageEvent',
        source: 'agent',
        llm_message: { role: 'assistant', content: plan },
      },
    ])
    await waitForPipeline()
    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'ready')
    assert.ok(state.blocks.length >= 1)
    assert.ok(state.blocks.some((b) => b.type === 'stepper'))
    assert.equal(state.blocks.some((b) => b.type === 'freeform-card'), false)
    const summary = state.blocks.find((b) => b.type === 'summary-card')
    if (summary) {
      assert.ok(String(summary.props.body || '').length <= 400)
    }
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

test('canvas keeps work product separate from chat and skips MCP plumbing tables', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `audit-${Date.now()}`
    const writeup = [
      'Workforce audit complete — 202 total employee records and 15 open requisitions currently showing (all opened 2026-07-01, ~49 days open).',
      'I also found compliance evidence gaps: we can’t reliably prove security training completion.',
      'I’ve attached outputs/workforce_audit_summary.md with the full findings.',
    ].join(' ')
    await recordCanvasEvents(conversationId, [
      action('activate_integration', '1', { name: 'hr' }),
      observation('activate_integration', '1', [
        { type: 'text', text: "Integration 'hr' is active. Available tools: benefits_lookup.", cache_prompt: false },
      ]),
      action('write_workspace_file', '2', {
        path: 'outputs/workforce_audit_summary.md',
        contents: '# Workforce audit',
      }),
      observation('write_workspace_file', '2', { ok: true, path: 'outputs/workforce_audit_summary.md' }),
      {
        kind: 'MessageEvent',
        source: 'agent',
        llm_message: { role: 'assistant', content: writeup },
      },
    ])
    await waitForPipeline()
    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'ready')
    assert.equal(state.blocks.some((b) => b.type === 'freeform-card'), false)
    assert.equal(
      state.blocks.some((b) => {
        if (b.type !== 'table' && b.type !== 'data-table') return false
        const title = String(b.props.title || '')
        const cols = Array.isArray(b.props.columns) ? b.props.columns.map(String) : []
        return /activate_integration/i.test(title) || cols.includes('cache_prompt') || cols.includes('type')
      }),
      false,
    )
    assert.ok(state.blocks.some((b) => b.type === 'attachment'))
    const stats = state.blocks.find((b) => b.type === 'stat-grid')
    assert.ok(stats)
    const values = JSON.stringify(stats?.props.stats || [])
    assert.match(values, /202/)
    assert.match(values, /15/)
    assert.equal(state.blocks.some((b) => b.type === 'summary-card'), false)
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

function mcpObservation(tool_name: string, tool_call_id: string, payload: unknown) {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload)
  return observation(tool_name, tool_call_id, [{ type: 'text', text }])
}

test('pre-filter unwraps MCP text envelopes for structured employee records', () => {
  const result = shouldEvaluateCanvas(
    { intent: 'start onboarding for Yuvraj Abrol' },
    [
      action('employee_lookup', '1', { name: 'Yuvraj Abrol' }),
      mcpObservation('employee_lookup', '1', {
        found: true,
        employee: {
          id: 'emp-2044',
          name: 'Yuvraj Abrol',
          title: 'Software Engineer',
          department: 'Engineering',
          email: 'yuvraj.abrol@closedai.com',
          manager: 'Priya Nair',
          location: 'Seattle',
          start_date: '2026-09-08',
          employment_type: 'full-time',
        },
        _canvas: { module: 'employee_profile', title: 'Yuvraj Abrol — Profile' },
      }),
    ],
  )
  assert.equal(result.candidate, true)
  assert.equal(result.reason.structuredOutcome, true)
})

test('employee lookup observation fills Canvas with real profile fields', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `onboard-profile-${Date.now()}`
    await recordCanvasEvents(conversationId, [
      action('employee_lookup', '1', { name: 'Yuvraj Abrol' }),
      mcpObservation('employee_lookup', '1', {
        found: true,
        employee: {
          id: 'emp-2044',
          name: 'Yuvraj Abrol',
          title: 'Software Engineer',
          department: 'Engineering',
          email: 'yuvraj.abrol@closedai.com',
          manager: 'Priya Nair',
          location: 'Seattle',
          start_date: '2026-09-08',
          employment_type: 'full-time',
          status: 'active',
        },
        _canvas: { module: 'employee_profile', title: 'Yuvraj Abrol — Profile' },
      }),
      terminal('onboard-turn'),
    ])
    await waitForPipeline()
    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'ready')
    const card = state.blocks.find((b) => b.type === 'employee-card-detailed')
    assert.ok(card, 'expected employee-card-detailed')
    assert.equal(card?.props.name, 'Yuvraj Abrol')
    assert.equal(card?.props.role, 'Software Engineer')
    assert.equal(card?.props.team, 'Engineering')
    assert.equal(card?.props.email, 'yuvraj.abrol@closedai.com')
    assert.equal(card?.props.manager, 'Priya Nair')
    assert.equal(card?.props.location, 'Seattle')
    const blob = JSON.stringify(state.blocks).toLowerCase()
    assert.equal(/details unavailable|unavailable in canvas/.test(blob), false)
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

test('cosmos formatted document text becomes a person card, not an empty subject shell', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `cosmos-profile-${Date.now()}`
    const formatted = [
      'Results:',
      '--------------------------------------------------',
      '',
      'Document 1:',
      '  employeeId: emp-2044',
      '  name: Yuvraj Abrol',
      '  jobTitle: Software Engineer',
      '  departmentName: Engineering',
      '  workEmail: yuvraj.abrol@closedai.com',
      '  managerName: Priya Nair',
      '  workLocationName: Seattle',
      '  hireDate: 2026-09-08',
      '  employmentType: full-time',
      '  _rid: abc',
    ].join('\n')
    await recordCanvasEvents(conversationId, [
      action('query_cosmos', '1', { query: "SELECT * FROM c WHERE CONTAINS(c.name, 'Yuvraj', true)" }),
      mcpObservation('query_cosmos', '1', formatted),
      terminal('cosmos-turn'),
    ])
    await waitForPipeline()
    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'ready')
    const card = state.blocks.find((b) => b.type === 'employee-card-detailed')
    assert.ok(card, 'expected employee-card-detailed from cosmos text')
    assert.equal(card?.props.name, 'Yuvraj Abrol')
    assert.equal(card?.props.email, 'yuvraj.abrol@closedai.com')
    assert.equal(card?.props.role, 'Software Engineer')
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

test('failed employee lookup does not open a hollow Canvas', async () => {
  const provider = process.env.LLM_PROVIDER
  const canvasProvider = process.env.CANVAS_LLM_PROVIDER
  process.env.LLM_PROVIDER = ''
  process.env.CANVAS_LLM_PROVIDER = ''

  try {
    const conversationId = `onboard-missing-${Date.now()}`
    await recordCanvasEvents(conversationId, [
      {
        kind: 'MessageEvent',
        source: 'user',
        llm_message: { role: 'user', content: 'Start the new-hire onboarding workflow for Yuvraj Abrol' },
      },
      action('employee_lookup', '1', { name: 'Yuvraj Abrol' }),
      mcpObservation('employee_lookup', '1', {
        found: false,
        query: 'Yuvraj Abrol',
        message: "No employee matched 'Yuvraj Abrol'.",
      }),
      {
        kind: 'MessageEvent',
        source: 'agent',
        id: 'missing-turn',
        llm_message: { role: 'assistant', content: 'I could not find Yuvraj Abrol in the employee directory.' },
      },
    ])
    await waitForPipeline()
    const state = readCanvasState(conversationId)
    assert.equal(state.status, 'skipped')
    assert.deepEqual(state.blocks, [])
  } finally {
    if (provider === undefined) delete process.env.LLM_PROVIDER
    else process.env.LLM_PROVIDER = provider
    if (canvasProvider === undefined) delete process.env.CANVAS_LLM_PROVIDER
    else process.env.CANVAS_LLM_PROVIDER = canvasProvider
  }
})

test('generator validation drops unavailable placeholder copy', () => {
  const blocks = validateCanvasBlocks({
    blocks: [
      { type: 'key-value', version: 1, props: { title: 'Subject', pairs: [{ key: 'Name', value: 'Yuvraj Abrol' }] } },
      { type: 'summary-card', version: 1, props: { title: 'Profile', body: 'Details unavailable in Canvas' } },
    ],
  }, new Set(['key-value', 'summary-card']))
  assert.equal(blocks.length, 1)
  assert.equal(blocks[0].type, 'key-value')
})
