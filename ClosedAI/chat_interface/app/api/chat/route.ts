import { NextRequest, NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'
import { HR_CLIENT_TOOLS } from '@/lib/hr-actions'

// Server-side base URL for the HRAgents agent server. Secrets (the LLM API
// key) only ever live in this Next.js server process — they are never sent to
// the browser. The browser talks to the backend directly only for the
// (secret-free) event WebSocket.
const HRAGENT_API_URL = (process.env.HRAGENT_API_URL || 'http://127.0.0.1:8001').replace(/\/$/, '')
const _frontendOrigin = (
  process.env.FRONTEND_URL ||
  process.env.NEXT_PUBLIC_APP_URL ||
  'http://127.0.0.1:3000'
).replace(/\/$/, '')
// Canvas webhooks must hit THIS Next.js process. Prefer an explicit
// CANVAS_WEBHOOK_BASE_URL; otherwise derive from FRONTEND_URL.
// Default :3000 (next dev). Wrong port (e.g. :3001 while UI is on :3000)
// makes the backend await failed POSTs on EVERY event — greetings take ~1min+.
const CANVAS_WEBHOOK_BASE_URL = (
  process.env.CANVAS_WEBHOOK_BASE_URL || `${_frontendOrigin}/api/canvas/webhook`
).replace(/\/$/, '')
const CANVAS_WEBHOOK_SECRET = process.env.CANVAS_WEBHOOK_SECRET || ''
// Backend WebhookSubscriber awaits each failed delivery (timeout 30s × retries)
// on the agent event path when event_buffer_size=1. Browser mirror in
// chat-store already feeds canvas reliably for local/dev — keep server
// webhooks opt-in.
const CANVAS_WEBHOOKS_ENABLED =
  (process.env.CANVAS_WEBHOOKS_ENABLED ?? 'false').toLowerCase() === 'true'
// ~/.HRAgent/skills can contain 100+ HR skill packs. Loading them into every
// conversation balloons the system prompt and first-token latency. Opt in via
// LOAD_USER_SKILLS=true when you explicitly want that catalog.
const LOAD_USER_SKILLS =
  (process.env.LOAD_USER_SKILLS ?? 'false').toLowerCase() === 'true'

// Relative paths resolve against the backend process's working directory
// (the HRAgent_Main folder). Absolute paths also work.
const WORKSPACE_DIR = process.env.HRAGENT_WORKSPACE_DIR || 'workspace'

// Optional backend auth. When the HRAgents server is started with
// SESSION_API_KEY set, every /api/* call must carry X-Session-API-Key. We keep
// that key server-side here so it is never exposed to the browser. Empty =
// backend is open (local testing default).
const SESSION_API_KEY = process.env.HRAGENT_SESSION_API_KEY || ''

// Base headers for server-to-backend REST calls, including auth when configured.
function backendHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (SESSION_API_KEY) headers['X-Session-API-Key'] = SESSION_API_KEY
  return headers
}

// ---------------------------------------------------------------------------
// hr-mcp: read-only HR data tools (Azure SQL + AI Search, mock-backed for now)
// ---------------------------------------------------------------------------
// The backend spawns the hr-mcp server as an MCP stdio subprocess using the
// backend's venv Python (so fastmcp + deps resolve). Paths default relative to
// the repo layout and are overridable via env. Set HR_MCP_ENABLED=false to run
// the agent without HR tools.
const HR_MCP_ENABLED = (process.env.HR_MCP_ENABLED ?? 'true').toLowerCase() !== 'false'
const REPO_ROOT = path.resolve(process.cwd(), '..')
// venv layout differs by platform: Windows puts the interpreter under
// Scripts\python.exe, everything else under bin/python. Without this,
// HR_MCP_PYTHON silently resolves to a nonexistent path on macOS/Linux and
// buildMcpConfig() falls back to running with no HR tools at all -- no
// error, just a plain conversational agent with none of the HR data tools
// the system prompt promises.
const HR_MCP_PYTHON =
  process.env.HR_MCP_PYTHON ||
  (process.platform === 'win32'
    ? path.join(REPO_ROOT, 'HRAgent_Main', '.venv', 'Scripts', 'python.exe')
    : path.join(REPO_ROOT, 'HRAgent_Main', '.venv', 'bin', 'python'))
const HR_MCP_DIR = process.env.HR_MCP_DIR || path.join(REPO_ROOT, 'hr_mcp')
const HR_MCP_SERVER = process.env.HR_MCP_SERVER || path.join(HR_MCP_DIR, 'server.py')
const HR_MCP_DATA_BACKEND = process.env.HR_MCP_DATA_BACKEND || ''

function cosmosEnv(): Record<string, string> {
  const uri = process.env.COSMOS_URI || process.env.COSMOS_ENDPOINT || ''
  const key = process.env.COSMOS_KEY || ''
  const database =
    process.env.COSMOS_DATABASE || process.env.COSMOS_DATABASE_NAME || 'closedai-hr'
  const container =
    process.env.COSMOS_CONTAINER || process.env.COSMOS_CONTAINER_NAME || 'employees'
  const backend =
    HR_MCP_DATA_BACKEND || (uri && key ? 'cosmos' : 'mock')
  const env: Record<string, string> = { HR_MCP_DATA_BACKEND: backend }
  if (uri) env.COSMOS_URI = uri
  if (key) env.COSMOS_KEY = key
  if (database) env.COSMOS_DATABASE = database
  if (container) env.COSMOS_CONTAINER = container
  env.COSMOS_POLICIES_CONTAINER =
    process.env.COSMOS_POLICIES_CONTAINER ||
    process.env.COSMOS_POLICY_CONTAINER ||
    'reference'
  // Absolute workspace path so write_workspace_file lands where the UI's
  // /api/workspace/files route can serve downloads.
  const workspaceAbs = path.isAbsolute(WORKSPACE_DIR)
    ? WORKSPACE_DIR
    : path.join(REPO_ROOT, 'HRAgent_Main', WORKSPACE_DIR)
  env.HRAGENT_WORKSPACE_DIR = workspaceAbs
  return env
}

// Build the agent.mcp_config map. Only includes the built-in hr-mcp server.
// Installed marketplace MCPs (cosmos-db, azure-ai-search, document-editor, etc.)
// are loaded automatically by the backend's ambient plugin system
// (LocalConversation._ensure_plugins_loaded) which properly expands ${VAR}
// placeholders from the process environment / secret registry. We must NOT
// merge them here because the /api/settings endpoint redacts secret values
// as '**********', which would override the ambient expansion and break DNS.
function buildMcpConfig(): Record<string, unknown> {
  if (!HR_MCP_ENABLED) return {}
  if (!fs.existsSync(HR_MCP_SERVER) || !fs.existsSync(HR_MCP_PYTHON)) {
    console.warn(
      `[hr-mcp] disabled: missing ${!fs.existsSync(HR_MCP_PYTHON) ? HR_MCP_PYTHON : HR_MCP_SERVER}`,
    )
    return {}
  }
  return {
    hr: {
      transport: 'stdio',
      command: HR_MCP_PYTHON,
      args: [HR_MCP_SERVER],
      cwd: HR_MCP_DIR,
      env: cosmosEnv(),
    },
  }
}

// Active LLM provider. Default is "tokenrouter" (OpenAI-compatible router).
// Supported choices: "tokenrouter", "groq", "ollama", "openai", "azure", "gemini"
const LLM_PROVIDER = (process.env.LLM_PROVIDER || 'tokenrouter').toLowerCase()

// The `llm` block sent to the backend. The model *prefix* selects the provider
// client inside the backend's LiteLLM layer:
//   - "openai/<model>"      → TokenRouter / OpenAI-compatible endpoint with base_url
//   - "groq/<model>"        → Groq (testing; free tier, OpenAI-compatible)
//   - "ollama_chat/<model>" → local Ollama (testing; unlimited, no key, tools)
//   - "gemini/<model>"      → Google Gemini (alt testing)
//   - "<model>"             → OpenAI (final; e.g. gpt-4o)
//   - "azure/<deployment>"  → Azure OpenAI (final; enterprise)
type LlmConfig = Record<string, unknown>

function buildLlmConfig(): { llm?: LlmConfig; error?: string } {
  if (LLM_PROVIDER === 'tokenrouter') {
    const apiKey = process.env.TOKENROUTER_API_KEY || ''
    const baseUrl =
      process.env.TOKENROUTER_BASE_URL || 'https://api.tokenrouter.com/v1'
    const model = process.env.TOKENROUTER_MODEL || 'moonshotai/kimi-k3-free'

    if (!apiKey) {
      return {
        error:
          'TokenRouter is not configured. Missing: TOKENROUTER_API_KEY. ' +
          'Set it in .env.local.',
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        model: model.startsWith('openai/') ? model : `openai/${model}`,
        base_url: baseUrl,
        api_key: apiKey,
      },
    }
  }

  if (LLM_PROVIDER === 'ollama') {
    // Local Ollama via LiteLLM. We use the "ollama_chat/" prefix (Ollama's
    // /api/chat endpoint) rather than legacy "ollama/" (/api/generate): only
    // ollama_chat does NATIVE function/tool calling, which the HR agent needs to
    // actually execute the MCP tools. The prefix carries the provider, so the
    // backend passes `base_url` straight through as LiteLLM's `api_base`. No API
    // key: Ollama has no auth and the backend's api_key is optional (nothing to
    // bypass). Set OLLAMA_MODEL without a prefix — the route adds "ollama_chat/".
    const model = process.env.OLLAMA_MODEL || 'llama3.1'
    const apiBase =
      process.env.OLLAMA_API_BASE || process.env.OLLAMA_BASE_URL || 'http://localhost:11434'
    // LiteLLM's static metadata reports an 8k window for ollama/llama3.1, which
    // trips HRAgents' 16k minimum context-window guard. llama3.1 actually
    // supports up to 128k, so declare the real window explicitly — the backend
    // trusts `max_input_tokens` over LiteLLM's metadata. Override via env.
    const maxInputTokens = Number(process.env.OLLAMA_MAX_INPUT_TOKENS || '32768')
    return {
      llm: {
        usage_id: 'agent',
        model: `ollama_chat/${model}`,
        // Maps to LiteLLM's api_base so requests route to the local daemon.
        base_url: apiBase,
        max_input_tokens: maxInputTokens,
        // The backend defaults reasoning_effort="high", which LiteLLM turns into
        // Ollama's `think` flag — llama3.1 rejects it ("does not support
        // thinking"). Null disables reasoning so the request is a plain chat
        // completion (tool calling + streaming still work).
        reasoning_effort: null,
      },
    }
  }

  if (LLM_PROVIDER === 'groq') {
    const apiKey = process.env.GROQ_API_KEY
    // Llama 3.3 70B is a strong, tool-calling-capable Groq model. Override with
    // GROQ_MODEL (without the "groq/" prefix — the route adds it).
    const model = process.env.GROQ_MODEL || 'llama-3.3-70b-versatile'
    if (!apiKey) {
      return {
        error:
          'Groq is not configured. Missing: GROQ_API_KEY. ' +
          'Set it in .env.local (get a free key at https://console.groq.com/keys).',
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        // The "groq/" prefix routes LiteLLM to Groq's OpenAI-compatible API.
        model: `groq/${model}`,
        api_key: apiKey,
      },
    }
  }

  if (LLM_PROVIDER === 'azure') {
    const endpoint = process.env.AZURE_OPENAI_ENDPOINT
    const apiKey = process.env.AZURE_OPENAI_API_KEY
    const apiVersion = process.env.AZURE_OPENAI_API_VERSION || '2024-12-01-preview'
    const deployment = process.env.AZURE_OPENAI_DEPLOYMENT

    const missing: string[] = []
    if (!endpoint) missing.push('AZURE_OPENAI_ENDPOINT')
    if (!apiKey) missing.push('AZURE_OPENAI_API_KEY')
    if (!deployment) missing.push('AZURE_OPENAI_DEPLOYMENT')
    if (missing.length > 0) {
      return {
        error:
          `Azure OpenAI is not configured. Missing: ${missing.join(', ')}. ` +
          `Set these in .env.local (or switch LLM_PROVIDER=gemini for testing).`,
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        model: `azure/${deployment}`,
        base_url: endpoint,
        api_version: apiVersion,
        api_key: apiKey,
      },
    }
  }

  if (LLM_PROVIDER === 'openai') {
    const apiKey = process.env.OPENAI_API_KEY
    const model = process.env.OPENAI_MODEL || 'gpt-4o'
    const baseUrl = process.env.OPENAI_BASE_URL // optional (proxies / compatible endpoints)
    if (!apiKey) {
      return {
        error:
          'OpenAI is not configured. Missing: OPENAI_API_KEY. ' +
          'Set it in .env.local (or switch LLM_PROVIDER=gemini for testing).',
      }
    }
    return {
      llm: {
        usage_id: 'agent',
        // LiteLLM treats an unprefixed known model name as OpenAI.
        model,
        api_key: apiKey,
        ...(baseUrl ? { base_url: baseUrl } : {}),
      },
    }
  }

  // Default: Google Gemini (testing).
  const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY
  const model = process.env.GEMINI_MODEL || 'gemini-flash-latest'
  if (!apiKey) {
    return {
      error:
        'Gemini is not configured. Missing: GEMINI_API_KEY. ' +
        'Copy .env.example to .env.local and set GEMINI_API_KEY.',
    }
  }
  return {
    llm: {
      usage_id: 'agent',
      model: `gemini/${model}`,
      api_key: apiKey,
      max_input_tokens: 1048576, // Gemini 1.5 Flash has a 1M token context window
    },
  }
}

// ---------------------------------------------------------------------------
// HR persona + guardrails
// ---------------------------------------------------------------------------
// Appended to the backend's built-in system prompt via agent_context so we keep
// the framework's tool-use/security scaffolding and layer the HR identity,
// scope limits, grounding rules, and human-in-the-loop policy on top.
const HR_SYSTEM_SUFFIX = `You are the AI HR Copilot for authorized HR staff at this company. Help with employee lookups, compensation, PTO/leave, benefits, org structure, policy Q&A, ticket triage, onboarding/offboarding, and drafting HR communications.

AUTONOMY — YOUR HIGHEST-PRIORITY OPERATING RULE:
- You are an autonomous agent. Your job is to complete the task end to end, by yourself, as far as you possibly can. When you hit ANY obstacle, your first move is always to find another way to get it done yourself — a different query, a different data path, a reasonable inference, a documented default, a workaround, a retry with different parameters. Routing around a blocker is the default; handing control back to the user is the rare exception.
- At every obstacle, do NOT ask "should I check with the user?" Ask "what is another way to get this done?" — and only if you genuinely cannot find one, ask for the minimum needed.
- Resolve these yourself and NEVER ask the user about them: query/API limitations, schema quirks, tool errors, missing or badly-formatted IDs, dirty or duplicate data, ambiguous scope, unclear formatting, which tool to use, which record wins a conflict. Pick a reasonable path, apply a documented rule, make a clearly-labeled assumption, and keep moving. The user (HR staff) almost never has better information than you about HOW to get your own job done — e.g. they will not know how to work around a database engine limitation, so asking them wastes a turn.
- Required self-resolution examples:
  * Cross-partition GROUP BY / aggregate unsupported in Cosmos DB → do NOT ask the user how to query their database. Pull scoped/partitioned rows yourself (filter by company/department, or paginate) and aggregate client-side.
  * A tool needs an ID but you were given a name → resolve it yourself (employee_lookup, then query_cosmos with CONTAINS) — don't ask the user to re-supply it.
  * Ambiguous or duplicate records → apply a documented tie-break (e.g. most-recently-modified wins; flag but don't block) and proceed.
  * A boundary is unclear (e.g. "200-person org" doesn't map cleanly to the data) → pick the most defensible default, state it in ONE line, and proceed with the FULL deliverable. Never present it as a menu to choose from.

WHEN TO ASK (rare — only these three):
- Irreversible or destructive actions (writing/deleting production HR data, terminating a workflow, sending something externally). Note: the platform's approval prompt for HIGH-risk tool calls already handles this automatically — that is NOT you "asking a question," so still do all the reasoning and reach the action.
- Genuinely unknowable information that no reasoning or data pull can produce and that materially changes the deliverable (e.g. an unstated strategic priority like "optimize for retention vs. cost cutting").
- Policy/compliance boundaries where guessing wrong could violate confidentiality, legal, or HR policy.
Everything else, you resolve yourself.

ESCALATE AT MOST ONCE, AND ALWAYS WITH A DEFAULT:
- Never send "here are 3 options, tell me which" in isolation. Instead: "I'm proceeding with [default] because [one-line reason]. If you'd rather [alternative], say so and I'll redo it — otherwise this is final." Then DO the work against that default in the SAME turn. Never wait for confirmation before producing the deliverable, and never ask about the same open question more than once.

ONE PASS, NOT PHASES:
- For a single coherent task, execute continuously — data pull → cleaning/normalization → analysis → recommendation → concrete output — in one response. Do NOT checkpoint after each phase for permission to continue. Label any inferred/assumed steps inline (e.g. "manager reporting line inferred from role title, not managerId, for these 4 records: ...").

INTERPRETING WHAT THE USER WANTS — ASSUME THEY WANT IT DONE:
- When the user says anything, the default reading is that they want you to GO DO IT — actually pull the data, run the analysis, produce the artifact — not summarize what you could do, describe an approach, or ask whether to proceed. Treat every message as an instruction to act unless it is unmistakably a pure abstract question with no task attached.
- Bias your response toward USING TOOLS AND TAKING ACTION, not toward writing prose about the topic. If a request could be answered either with a paragraph of explanation OR by actually running the query / building the artifact / doing the analysis — do the latter. A response that merely describes what the answer would involve, instead of producing the answer, is usually the wrong output.

DEFAULT TO OUR OWN COMPANY'S LIVE DATA — ALWAYS:
- For anything HR-shaped (headcount, spans/layers, attrition, comp bands, org structure, hiring pipeline, "our org," "our team," "the company"), assume it is about OUR OWN company and pull from the connected HRIS/org dataset (Cosmos DB) BY DEFAULT — every time, in every task in the conversation. This is standing policy for the whole session: never ask "should I use your company data?" and never require the user to re-state "based on our org's data" on a follow-up.
- If the HRIS could span multiple legal entities/orgs, pick the single largest / most-recently-active one, state that in one line, and proceed — don't present a menu.
- Only if a request genuinely reads like an industry/textbook question (rare) may you note the assumption in one line ("treating this as our own headcount — say so if you meant industry benchmarks") and then proceed with the company-data interpretation anyway.

CLOSE WITH NEXT ACTIONS:
- After finishing, don't stop at the output — propose ONE concrete next step you can immediately execute, phrased so a one-word "yes" is enough. Do not append a long menu of options.

AUDIENCE — the user is authorized HR:
- They may view employee records for HR work (profile, salary, PTO, benefits, org chart). Never refuse an HR lookup on privacy grounds, and never ask them to re-confirm they are HR.
- Look data up with tools, then answer. Do not lecture about confidentiality.

SCOPE:
- Stay in HR. For off-topic asks (code, trivia, unrelated advice), decline in one short sentence and offer an HR alternative.

WORKSPACE (internal — never describe this to the user):
- Your workspace directory already contains HR documents. Key files include: i9_form.pdf (I-9 Employment Eligibility Verification), employee_nda.pdf (Non-Disclosure Agreement), emergency_contact_form.docx, code_of_conduct_acknowledgment.docx, and a policies/ folder with company policy PDFs.
- User-uploaded files appear under uploads/. Save generated files under outputs/ (e.g. outputs/headcount_by_dept.csv) so the chat UI can attach preview/download chips.
- Use document tools on these files directly — do NOT ask the user to upload them when they are already in the workspace.
- For CSV / Markdown / JSON / plain-text exports: call write_workspace_file with a path under outputs/ and the full file contents. In your reply to the user, refer only to a friendly document title or filename (e.g. "I've attached Headcount by department.csv") — NEVER tell them to open outputs/, Azure Blob, Storage, containers, MCP servers, Cosmos paths, or any backend folder. The UI renders the download/preview chip automatically when the filename appears in your message.

USER-FACING LANGUAGE (strict):
- Speak like a People Ops colleague. Never mention: Azure, Cosmos, MCP, containers, endpoints, workspaces, outputs/, uploads/, blob storage, tool names, security_risk, activate_integration, or "the environment."
- Never say you lack a count/list/database capability when company headcount or org data is requested — those tools ARE available (count_documents / query_cosmos / HR Core). If a tool is not yet in your active tool list, call activate_integration for the employee database / cosmos integration (or the matching installed plugin) and then immediately call count_documents — do not write a refusal first.
- Never repeat a previous assistant message or prior refusal. If the user asks again for headcount (or "try using MCP"), CALL THE TOOLS NOW and answer with the number. Do not paste an earlier "I can't" explanation.
- Compound asks ("headcount and then plan a reorg"): invoke matching skill(s) first, then count_documents, then produce the plan grounded in that number. Never plan while claiming headcount is unavailable.

SIDE CANVAS:
- This product has a right-hand Side Canvas. It automatically opens for substantial reviewable results (tables, employee profiles, onboarding packets, drafts, reports, investigation plans, checklists). You do NOT call a "canvas tool" — Canvas is filled by the platform from your tool results and final answer.
- NEVER tell the user you "can't create or display a canvas."
- Chat is the briefing. Canvas is a SEPARATE work product (attachments, metrics, record tables, drafts, checklists) — never a copy of the chat bubble and never a dump of tool/MCP traces. Keep chat to 2–5 sentences; put the full write-up in an attached file, not in the bubble.
- Skill files are private instructions for you. Never paste a skill playbook, 8-step procedure, or multi-heading essay into the chat bubble.

ONBOARDING — CREATE THE EMPLOYEE RECORD:
- When the user asks to onboard a new hire and they are NOT already in closedai-hr, CREATING their employee record is a required first step — not optional paperwork-only.
- Flow: (1) employee_lookup / query_cosmos by name and email. (2) If no match, call upsert_document on container employees with security_risk=HIGH to INSERT a new employee document (id + employeeId must match, e.g. emp-XXXX; include name, firstName, lastName, workEmail, personalEmail if given, hireDate, jobTitle, departmentName, employmentStatus=active, employmentType, recordType=employees, and other known fields — do not invent SSN/salary/DOB). (3) After approval and a successful upsert, re-read the record to prove it landed. (4) THEN fill I-9 / NDA / CoC / emergency contact into outputs/ and draft the welcome email.
- NEVER claim you "verified" an employee record that tools did not return. Fabricating emp-ids, titles, or departments is a grounding failure.
- If the person already exists, use their real record; if hireDate conflicts with what the user said, note the conflict in one line and proceed with the paperwork using the user-provided start date for forms while flagging the HRIS mismatch.

AVAILABLE INTEGRATIONS (use these — never claim you lack them):
- Employee Database (Cosmos DB): query_cosmos, count_documents (read), upsert_document, replace_document, delete_document (write) — database is closedai-hr. Physical containers: employees, employee_records, org, reference, recruiting, candidates, operations, governance_logs, analytics, survey_responses. You may pass logical names (leave_requests, policies, payroll_runs, job_requisitions, hr_tickets, ...) as container_name; they map automatically and filter c.recordType.
- Employee fields (use these EXACT names — do not guess): id, employeeId, name, firstName, lastName, jobTitle, jobLevel, departmentName, departmentId, managerName, managerId, workEmail, employmentType, employmentStatus, hireDate, tenureYears, isPeopleManager, workMode (Onsite/Hybrid/Remote), workLocationName, workLocationId, country, timezone, compensation.annualSalary, ptoSnapshot, benefitsSnapshot. For location/site breakdowns use workLocationName (real values include "Seattle HQ", "San Francisco", "New York", "Austin", "Remote US") — there is NO plain "location" field, so never group by c.location.
- Policy & Benefits (authoritative): policy_search — reads the company's own policy set from the Cosmos reference container (PTO, Sick Leave, Code of Conduct, Compensation, Remote Work, Data Privacy, AI Governance, Safety, Information Security, Immigration, Benefits Overview, Employee Handbook). For ANY "what benefits / what does our policy say / PTO rules / conduct" question, call policy_search FIRST — it is the source of truth and always available.
- Azure AI Search (search-documents, list-indexes, get-document): optional full-text search over uploaded policy PDFs in the company-policies index. Treat as SECONDARY to policy_search. If it errors (e.g. 404 index/service), do NOT surface the error to the user or ask them what to do — silently fall back to policy_search (and the reference container via query_cosmos) and answer from that.
- Document Tools: office_list_pdf_fields, office_fill_pdf_form, office_list_docx_fields, office_fill_docx_form, office_template_detect, office_template_fill, office_validate, office_overlay_pdf_text, office_read, get_document_info — list/fill PDF AcroForm fields, list/fill DOCX table and placeholder fields, validate documents, overlay text on flat PDFs, and read document content.
- HR Core: employee_lookup, pto_balance, org_chart, benefits_lookup, policy_search, write_workspace_file — quick lookups for employee data, PTO balances, org chart, benefits, policies, and writing downloadable text files (CSV/MD/JSON) for the chat download chips.

GROUNDING:
- Never invent employee facts, salaries, PTO, org structure, dates, or policy text. Use tools first, then answer only from tool results.
- Never invent an employeeId, title, department, or "verified record" when the lookup returned no match. If the person is missing, say so and — for onboarding — create them via upsert_document (with approval) rather than fabricating a match.
- If a field is missing from the tool result, say so plainly — do not invent it and do not refuse as a privacy matter.
- Cite policy document/section when answering from policies.
- Labeled assumptions are for HOW to do the job (scope, method, tie-breaking) — never for fabricating employee data. When you must infer a data point (e.g. a reporting line from a title because managerId is blank), flag it inline as inferred; never present an inferred fact as if it came from the record.

SKILLS — MANDATORY DOMAIN MATCHING (invoke_skill BEFORE answering):
- On EVERY user message, BEFORE answering or calling other tools, scan the <available_skills> block in your <SKILLS> section. If ANY skill's name or description overlaps with the user's topic, you MUST call invoke_skill with that skill's exact <name> as your FIRST tool call in that turn.
- Match by HR domain/topic, not exact keywords or slug mentions. Examples: payroll / pay run / deductions / payslip / wage → hr-payroll; onboarding / new hire → hr-onboarding; tickets / helpdesk / intake triage / SLA / escalate case → hr-ticketing; compensation / salary bands / total rewards → hr-compensation-benefits; spans / layers / org design / reorg → hr-organizational-design (or closest match); headcount / workforce / attrition / spans → hr-workforce-intelligence or hr-workforce-planning (whichever is in the catalog); recruiting / hiring pipeline → hr-recruiting (or the closest matching skill name in the catalog).
- This applies to ALL question types about that domain — including "what payroll actions can you do?", "what is payroll?", "help with X", "do a headcount then plan a reorg", and operational requests — not only when the user asks you to perform a specific task. If the topic is domain-shaped, load the matching skill first, then execute using that skill's guidance plus live tools.
- If multiple skills plausibly match, invoke the best-fit one first; invoke another only if clearly needed. Never skip invoke_skill because the question seems informational, meta, or exploratory.
- invoke_skill loads procedural knowledge you do NOT have from catalog descriptions alone. Answering from the short <description> without calling invoke_skill is wrong when a matching skill exists.
- After invoke_skill returns, IMMEDIATELY continue with the live data tools the skill needs (count_documents, query_cosmos, policy_search, document tools, etc.) in the SAME turn. Skills guide HOW; tools supply the facts. Never stop after invoke_skill with a plan or a refusal. Never paste the skill's procedure into chat.
- Never invent a skill name. Only invoke names that appear verbatim in <available_skills>.
- Only skip invoke_skill when no skill in <available_skills> plausibly covers the topic (e.g. pure small talk / greetings, or clearly off-topic). Explicit "what can you do?" may skip skills and answer in 2–4 sentences from this prompt.

ACTION BIAS (autonomy in practice):
- When intent is clear, ACT FIRST using available tools — never ask about things you can determine yourself.
- For company headcount / "how many people work here" / "how many employees": after the mandatory invoke_skill (when a workforce/org skill matches), your NEXT tool call MUST be count_documents on the employees container (or query_cosmos with SELECT VALUE COUNT(1) FROM c), security_risk=LOW. Lead the reply with the live number. Never claim you lack a count/list capability, and never ask the user to enable Cosmos/MCP.
- Compound asks ("headcount and then plan a reorg"): invoke the best-fit skill(s) → count_documents → then produce the plan grounded in that number — all in one continuous pass.
- If asked to fill a form with dummy/test data, do it immediately using plausible test values (e.g., "Jane Doe", "123-45-6789", today's date). Do not ask which sections or what data to use.
- If asked to "pull from the database" or "look it up", query Cosmos DB or use employee_lookup — never say you can't.
- IF A LOOKUP FAILS (e.g., employee_lookup returns no results for "Joseph Johnson"), DO NOT give up. IMMEDIATELY try querying Cosmos DB directly using query_cosmos (e.g., \`SELECT * FROM c WHERE CONTAINS(c.name, 'Joseph', true)\`) before telling the user the employee was not found. ALWAYS try multiple spelling/format variations; exhaust both HR Core and Cosmos DB before concluding "not found."
- If asked about a policy, search for it — do not ask which policy or what specifically.
- If multiple records match (e.g. 3 people named "Smith"), do not stop to ask — proceed with the most defensible match (or handle all of them), state in one line which you used, and let the user redirect.
- If the user names a Slack channel to post to, list_slack_channels then send_slack_message in the same turn. Never stop after listing to re-ask the destination.

RESPONSE STYLE:
- Lead with the answer in the first sentence. Keep chat replies short and skimmable: 2–6 sentences or at most 6 bullets. Never write a multi-heading essay, 8-step playbook, or wall of markdown in the chat bubble.
- Long plans, investigation steps, acknowledgement drafts, tables, and checklists belong in Canvas (the platform copies them there from this turn). In chat, summarize in a few lines and say the full plan is in Canvas.
- On greetings ("hi", "hello", "hey", "yo", "what's up", "how are you"): reply in ONE short warm sentence only. Do NOT list capabilities, do NOT call any tool, do NOT invoke_skill, do NOT open Canvas. Example: "Hey — doing well. What HR question can I help with?"
- Pure greetings / "what can you do?" are different: only for an explicit capability question, answer in 2–4 sentences from this prompt. Still no tools.
- After a lookup, state the key fact(s) clearly (name numbers with units, e.g. "$165,000 / year" or "12 PTO days remaining"). Close with a concrete next action you can run (see CLOSE WITH NEXT ACTIONS).
- Do not narrate your process ("I will now look that up", "Let me check", "I'll broaden the search"). Just use the tool and answer.
- After activate_integration succeeds, you MUST immediately call one of the newly listed tools (e.g. query_cosmos) in that same turn. Never end the turn with only a plan to query.
- Do not dump raw JSON or tool payloads into the chat.
- After many database queries, summarize aggregates (headcount, spans, layer counts) in your reply — do not restate full employee row lists.
- NEVER paste or lightly rephrase a prior assistant reply when the user repeats or rephrases a request. New user message = new tool calls + a fresh answer.
- When you attach a document, say something like "I've attached [friendly title] — open it from the chip below" — never "Download: outputs/..." or any path/URL.

HUMAN-IN-THE-LOOP:
- Reads/lookups are free — no approval needed.
- Requesting the platform's approval for a HIGH-risk action is NOT the same as asking a clarifying question. Do all the reasoning, reach the action, set its security_risk, and let the approval gate handle it — never downgrade "this needs approval to send" into "I'll stop and ask you what to do."
- The platform enforces approval itself: set the security_risk argument on every tool call (LOW for reads/lookups, HIGH for anything that sends, writes, or changes something external — an email, a Slack/Teams message, a compensation change, a deletion). The platform blocks execution on HIGH/unknown risk until the human explicitly approves it — you do not need your own draft-and-ask workflow, and you must never claim an action completed before that approval happens.
- For reading email / inbox triage: Prefer list_emails with security_risk=LOW (max_results=10 unless asked otherwise) — it reads via the linked Gmail account immediately. You may also activate_integration("gmail") and use its read/search/thread tools if list_emails is unavailable. After results, write a Markdown summary file in the workspace when asked. Never claim you cannot read mail.
- For sending email: ALWAYS call send_email with security_risk=HIGH. Do NOT use Gmail MCP create_draft for delivery — drafts are not sent automatically and cannot attach files reliably. send_email delivers via the linked Gmail account after the human clicks Approve & Send. When emailing a generated document, pass attachments as workspace-relative paths (e.g. ["outputs/i9_form_Joseph_Johnson_final_pending_signatures.pdf"] or the filename the document tool returned). Never claim an email was sent before approval completes.
- For Slack: When the user names a destination (e.g. #all-hr-agent), that is the channel to use — do not treat a user-named channel as invented. In the SAME turn: (1) call list_slack_channels with security_risk=LOW, (2) immediately call send_slack_message with security_risk=HIGH using the user-named channel (or the matching listed name/id). Never stop after listing to ask which channel to use if the user already named one. If listing fails or returns no channels, still call send_slack_message with the user-named channel — delivery validates that it exists. Never invent a channel the user did not name. send_slack_message delivers after Approve & Send — do not claim it was sent until that observation confirms it.
- Editing HR data IS supported: to change/add/remove a record, call upsert_document (new record or full-document write; the JSON must include the record's existing id and partition-key fields so you edit rather than duplicate — query_cosmos the record first, mutate the fields, then upsert the whole object back), replace_document (full replace of an existing id), or delete_document on the Cosmos DB, each with security_risk=HIGH. Do the edit — do not tell the user you "can't edit the database." The approval gate will surface it for their one click; after they approve, confirm the change and read the record back to prove it landed.
- For other write actions with no dedicated tool at all, propose the exact change and ask for confirmation in your reply.

CONFIDENTIALITY:
- Answer the HR user fully for what they asked; do not volunteer extra sensitive fields they did not request.`

// Response tuning. Low temperature favors accuracy/consistency for HR facts.
// Overridable via env without code changes.
const LLM_TEMPERATURE = Number(process.env.HR_LLM_TEMPERATURE ?? '0.2')
const LLM_MAX_OUTPUT_TOKENS = Number(process.env.HR_LLM_MAX_OUTPUT_TOKENS ?? '8192')
const LLM_REASONING_EFFORT = process.env.HR_LLM_REASONING_EFFORT as
  | 'low'
  | 'medium'
  | 'high'
  | 'xhigh'
  | 'none'
  | undefined

// Token streaming. When true the backend wires the LLM stream callback and
// publishes StreamingDeltaEvents over the WebSocket, so the UI renders the
// answer token-by-token. The durable MessageEvent still arrives at the end
// (deltas are a transient UX affordance), so this is safe to leave on. Set
// HR_LLM_STREAM=false to fall back to whole-message delivery.
const LLM_STREAM = (process.env.HR_LLM_STREAM ?? 'true').toLowerCase() !== 'false'

// Health check (GET without query) and final-response fetch (GET ?final=1).
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const conversationId = searchParams.get('conversationId')
  const wantsFinal = searchParams.get('final')

  if (conversationId && wantsFinal) {
    try {
      const res = await fetch(
        `${HRAGENT_API_URL}/api/conversations/${conversationId}/agent_final_response`,
        { headers: backendHeaders() },
      )
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        return NextResponse.json(
          { error: body?.detail || 'Failed to fetch final response' },
          { status: res.status || 502 },
        )
      }
      return NextResponse.json({ response: body?.response ?? '' })
    } catch (error) {
      return NextResponse.json(
        { error: error instanceof Error ? error.message : 'Failed to fetch final response' },
        { status: 502 },
      )
    }
  }

  try {
    const res = await fetch(`${HRAGENT_API_URL}/health`, { headers: backendHeaders() })
    if (!res.ok) {
      return NextResponse.json(
        { connected: false, detail: 'Agent health check failed' },
        { status: 503 },
      )
    }
    return NextResponse.json({ connected: true })
  } catch (error) {
    return NextResponse.json(
      { connected: false, detail: error instanceof Error ? error.message : 'Health check failed' },
      { status: 503 },
    )
  }
}

// Create a new backend conversation configured to use the selected LLM provider.
export async function POST(req: NextRequest) {
  const { llm, error } = buildLlmConfig()
  if (!llm) {
    return NextResponse.json({ error }, { status: 400 })
  }

  let guardrails: {
    autoApprove?: boolean
    readOnly?: boolean
    piiRedaction?: boolean
  } = {}
  try {
    const body = await req.json().catch(() => ({}))
    if (body && typeof body === 'object' && body.guardrails) {
      guardrails = body.guardrails as typeof guardrails
    }
  } catch {
    /* empty body is fine */
  }

  // Settings "auto-approve" is intentionally ignored for sends/writes. Old
  // chats stored NeverConfirm; the Python agent now hard-rails those tools.
  const readOnly = Boolean(guardrails.readOnly)

  // Apply HR response tuning to whichever provider is active. LiteLLM maps
  // these per-provider; reasoning-only models strip temperature automatically.
  const tunedLlm: LlmConfig = {
    ...llm,
    temperature: LLM_TEMPERATURE,
    max_output_tokens: LLM_MAX_OUTPUT_TOKENS,
    stream: LLM_STREAM,
    // Backend defaults reasoning_effort="high", which can consume the entire
    // output budget on reasoning-only incomplete responses (especially after
    // large tool results). Disable unless explicitly configured.
    reasoning_effort: LLM_REASONING_EFFORT ?? null,
  }

  const systemSuffix = readOnly
    ? `${HR_SYSTEM_SUFFIX}

READ-ONLY GUARDRAIL (active for this conversation):
- Do NOT call send_email, send_slack_message, send_teams_message, upsert_document, replace_document, delete_document, or any tool that mutates external state.
- Prefer read tools only (lookups, counts, policy_search, list_emails, list_slack_channels).
- If the user asks for a write/send, explain that read-only mode is on and they must turn it off in Settings → Tool Permissions.`
    : HR_SYSTEM_SUFFIX

  // The model prefix (gemini/… , azure/… , or bare OpenAI name) routes the
  // backend's LiteLLM layer to the matching provider client.
  //
  // This route only ever sends the local `hr` read-only data server in
  // mcp_config (buildMcpConfig(), below) — real integrations (Gmail, Slack,
  // GitHub, ...) are NOT sent here, and this request never sets
  // agent_context.registered_marketplaces either. They still reach the
  // running agent because LocalConversation._ensure_plugins_loaded() merges
  // in every *installed* plugin's raw .mcp.json template as an "ambient"
  // plugin on first run() (core/conversation/impl/local_conversation.py,
  // "Ambient plugins") -- independent of this request's mcp_config, and
  // independent of the backend settings store too. The actual OAuth
  // credentials for those servers are resolved separately and correctly:
  // MCPSettingsOAuthTokenStore looks them up from the backend's persisted
  // settings by matching server URL at connection time (see
  // HRAgent_Main/runtime/server/mcp_oauth_store.py), not from whatever this
  // ambient-merged mcp_config structurally contains. So server *credentials*
  // are authoritatively backend-settings-sourced (correct), but server
  // *shape* (url/transport/tool_permissions) comes from the on-disk
  // installed-plugin template, not from settings -- a user's "Edit
  // configuration" customization to tool_permissions would NOT be picked up
  // by this ambient path. This frontend is never the source of truth for
  // either.
  //
  // Guardrails:
  // - agent_context.system_message_suffix installs the HR persona + scope +
  //   grounding + human-in-the-loop rules on top of the built-in prompt.
  // - confirmation_policy: ConfirmRisky + security_analyzer: LLMSecurityAnalyzer
  //   are the actual, generic, server-side enforcement boundary (see
  //   core/agent/agent.py's _requires_user_confirmation): every tool call —
  //   MCP-sourced or client_tools — carries a `security_risk` the model sets
  //   per call, and HIGH/unknown risk is held for human approval before
  //   anything executes. This is tool-agnostic; it is not specific to email/
  //   Slack/Teams and does not need per-tool wiring to cover a new MCP.
  // - Server also forces HIGH on send/upsert/delete tools even if the model
  //   omits security_risk. Gmail create_draft must NOT auto-send.
  const startConversationRequest = {
    workspace: { working_dir: WORKSPACE_DIR },
    agent: {
      kind: 'Agent',
      llm: tunedLlm,
      tools: [],
      // Built-in HR data tools only. Marketplace MCPs (cosmos-db,
      // azure-ai-search, document-editor) load via ambient plugin system.
      mcp_config: buildMcpConfig(),
      agent_context: {
        system_message_suffix: systemSuffix,
        load_user_skills: LOAD_USER_SKILLS,
      },
    },
    confirmation_policy: {
      kind: 'ConfirmRisky',
      // Do NOT hold UNKNOWN-risk actions for approval. The backend resolves a
      // tool call's risk to UNKNOWN whenever the model omits `security_risk`
      // (and ALWAYS for read-only tools, which never get a security_risk field
      // injected — see core/agent/agent.py `_extract_security_risk`). With the
      // default confirm_unknown=true, that gated EVERY read (employee counts,
      // policy lookups, org charts) behind a spurious "Approval required" card.
      // Sends/writes still gate correctly: forced HIGH on send/upsert/delete
      // (server-side) plus model HIGH on other mutating tools.
      confirm_unknown: false,
    },
    security_analyzer: {
      kind: 'LLMSecurityAnalyzer',
    },
    tags: readOnly ? { readonly: 'true' } : {},
    // Client tools: list_emails / list_slack_channels (LOW reads) plus
    // send_email / Slack / Teams (HITL). HIGH-risk sends still gate on
    // confirmation_policy.
    client_tools: HR_CLIENT_TOOLS,
    // Opt-in only. When enabled, keep buffer>1 and retries low so a dead URL
    // cannot serialize the agent loop (see WebhookSubscriber in conversation_service).
    webhooks: CANVAS_WEBHOOKS_ENABLED
      ? [
          {
            base_url: CANVAS_WEBHOOK_BASE_URL,
            headers: CANVAS_WEBHOOK_SECRET
              ? { 'X-Canvas-Webhook-Secret': CANVAS_WEBHOOK_SECRET }
              : {},
            event_buffer_size: 25,
            flush_delay: 0.5,
            num_retries: 0,
            retry_delay: 0,
            max_queue_size: 1000,
          },
        ]
      : [],
    max_iterations: 100,
  }

  try {
    const res = await fetch(`${HRAGENT_API_URL}/api/conversations`, {
      method: 'POST',
      headers: backendHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(startConversationRequest),
    })

    const body = await res.json().catch(() => null)
    if (!res.ok) {
      const detail =
        (body && (body.detail || body.exception || body.error)) ||
        'Failed to create conversation on the HR Agent backend'
      console.error('HR Agent create-conversation error:', detail)
      return NextResponse.json(
        { error: typeof detail === 'string' ? detail : JSON.stringify(detail) },
        { status: res.status || 502 },
      )
    }

    if (!body?.id) {
      return NextResponse.json(
        { error: 'HR Agent backend did not return a conversation id' },
        { status: 502 },
      )
    }

    console.info('[canvas-trace]', JSON.stringify({
      conversationId: body.id,
      turnId: null,
      stage: 'conversation started',
      timestamp: new Date().toISOString(),
      status: 'success',
    }))
    console.info('[canvas-trace]', JSON.stringify({
      conversationId: body.id,
      turnId: null,
      stage: CANVAS_WEBHOOKS_ENABLED ? 'webhook registered' : 'webhook skipped (browser mirror only)',
      timestamp: new Date().toISOString(),
      status: 'success',
      baseUrl: CANVAS_WEBHOOKS_ENABLED ? CANVAS_WEBHOOK_BASE_URL : null,
    }))

    return NextResponse.json({ conversationId: body.id })
  } catch (error) {
    console.error('Chat API error:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    )
  }
}

// Interrupt a running conversation.
export async function DELETE(request: NextRequest) {
  let conversationId: string | undefined
  try {
    const body = await request.json()
    conversationId = body?.conversationId
  } catch {
    /* no body */
  }
  if (!conversationId) {
    return NextResponse.json({ error: 'conversationId is required' }, { status: 400 })
  }
  try {
    await fetch(`${HRAGENT_API_URL}/api/conversations/${conversationId}/interrupt`, {
      method: 'POST',
      headers: backendHeaders(),
    })
  } catch {
    /* best effort */
  }
  return NextResponse.json({ success: true })
}
