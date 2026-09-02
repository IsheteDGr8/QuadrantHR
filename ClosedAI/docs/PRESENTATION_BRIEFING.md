# Vera — AI HR Copilot (ClosedAI)
## Presentation Briefing Document

**Purpose of this file:** One dense source of truth for building an ~45–60 minute product presentation (leave room for Q&A). Use sections as slide groups; bold items are natural slide titles.

**Product names (use consistently on stage)**  
| Name | Role |
|------|------|
| **Vera** | Brand / people-facing agent name in the UI |
| **AI HR Copilot** | Category / system description |
| **ClosedAI** | Repo name, demo company, and fictional employer in the HR dataset |

**Audience of the product:** Authorized HR / People Ops staff (not employee self-service).  
**Runtime (demo):** Backend `http://127.0.0.1:8001` + UI `http://localhost:3000` (`chat_interface`).

---

# PART A — Non-technical (business & product)

## 1. What the system is meant for

Vera is an **agentic HR operations assistant**: a chat-first “action layer” that sits on top of HR data, policies, documents, and outbound communications.

It is designed so an HR professional can:

1. **Ask in natural language** (“What’s Sarah’s PTO?”, “How many employees do we have?”, “What’s our remote work policy?”).
2. **Have the agent gather facts** from live systems (Cosmos DB / HR tools / policy search / document tools)—not invent them.
3. **See structured results** in a Side Canvas (PTO card, org chart, policy excerpt, form fields) while the chat stays readable.
4. **Take irreversible actions only with human approval** (send email/Slack/Teams, write employee records)—HITL (“Approve & Send”).
5. **Run multi-step People Ops workflows** guided by Skills (onboarding, payroll process knowledge, workforce planning, etc.) when the task is procedural—not for every simple lookup.

**Strategic framing (from project strategy docs):** In ~48 hours of intensive build, the goal was less “another chatbot” and more an **MCP-powered action layer** that can *look up, fill, draft, and (with approval) act*—with Intake / Work Queue / Automations as the longer-term operating model around the agent.

---

## 2. Who it is for / who it is not for

| For | Not for (today) |
|-----|-----------------|
| HR business partners, People Ops, HRIS admins | Employee self-service portals |
| Managers asking HR *through* HR (with HR in the loop) | Fully unsupervised mass emails / payroll commits |
| Demo/pilot of “HR + AI + enterprise tools” | Production-hardened multi-tenant SaaS (still a pilot-grade system) |

Confidentiality model in the agent prompt: answer the **authorized HR user** fully for what they asked; don’t volunteer extra sensitive fields they didn’t request; **never invent** employee facts.

---

## 3. Feature map (product surfaces)

### 3.1 Chat (core product)

- Conversational interface with **Vera** (streaming token-by-token answers).
- **New Chat / Recent / Favorites** in the sidebar.
- Attachments upload into the agent workspace.
- Stop / interrupt a running agent turn.
- Inline **approval cards** when a high-risk action is pending.

### 3.2 Side Canvas (review surface)

- Right-hand panel that opens when there is something to *review*, not just read in chat.
- Deterministic modules from HR tools (employee profile, PTO, org chart, benefits, policy, document results).
- Also supports richer “UI blocks” generated for substantial multi-step outcomes.
- Designed so chat stays short while artifacts (org trees, form field lists, drafts) stay inspectable.

### 3.3 Agent Activity / Execution panel

- Live timeline of what Vera is doing: thinking, invoking skills, calling tools (Cosmos, policy search, document fill), responding.
- Builds trust: the user sees *how* the answer was produced, not a black box.

### 3.4 Skills

- **In chat (real):** Procedural Markdown skills the agent can load (`invoke_skill`) for workflows (e.g. onboarding). Large library under the agent skill paths (100+ HR-oriented skills in the project skill tree).
- **Skills page in UI:** Catalog/management chrome; historically partly mock vs live backend—**do not oversell the Skills admin page as fully wired**; sell **skills-in-chat** as the real capability.

### 3.5 MCP Connections & Marketplace

- **MCP (Model Context Protocol)** = standard way to plug tools into the agent (databases, search, Office docs, Gmail, Slack, etc.).
- **Marketplace:** Discover/install integrations (Cosmos DB, Azure AI Search, document editor, Gmail, Slack, M365, GitHub, Jira, Notion, …).
- **Connections:** See what’s installed/configured; secrets stay server-side.

### 3.6 Intake / Tasks, Work Queue, Automations, Systems, Memory, Settings

| Surface | Intent | Honesty for presenters |
|---------|--------|------------------------|
| **Intake / Tasks** | Cluster/triage incoming HR work | Largely **demo UI / mock data** today |
| **Work Queue** | Track multi-step work items | Largely **mock** progress/steps |
| **Automations** | Recurring or triggered HR flows | UI exists; **not the live agent core** |
| **Systems** | Connected system inventory | Product chrome / incomplete shell wiring |
| **Memory** | Longer-term agent memory UI | Product chrome |
| **Settings** | Agent name (Vera), prefs | Real UI prefs; LLM provider is mainly **server env** |

**Presenter rule:** Lead with **Chat + Canvas + tools + HITL**. Treat Intake/Work/Automations as **roadmap / operating model vision**, not as fully live backends unless you verify that day.

---

## 4. Capabilities (what Vera can actually do)

### 4.1 People & org intelligence

- Employee lookup (role, department, manager, location, tenure, compensation fields when present).
- **Headcount** / company size via live Cosmos count (fast path—no unnecessary skill load).
- Org chart / reporting lines.
- PTO / leave balance snapshots.
- Benefits enrollment summaries.

### 4.2 Policy & compliance Q&A

- Authoritative **policy_search** over company policy set in Cosmos reference data (PTO, sick leave, CoC, remote work, benefits overview, handbook themes, etc.).
- Optional secondary **Azure AI Search** over indexed policy PDFs (`company-policies` index)—with graceful fallback if Search fails.
- Answers expected to **cite** policy document/section when grounded in policy tools.

### 4.3 Documents & onboarding paperwork

- Fill **I-9** AcroForm PDFs, list/validate fields; overlay text on flat PDFs (e.g. NDA); work with DOCX where structure allows.
- Source forms live in Azure Blob (`onboarding-forms`: i9, NDA, CoC acknowledgment, emergency contact).
- Write downloadable workspace files (CSV/MD/JSON) for exports.
- Onboarding **skill** teaches process honesty: verify employee exists; create record with approval if missing; don’t fabricate checklist/I-9 matches.

### 4.4 Communications (human-in-the-loop)

- Draft and stage **email / Slack / Teams** via client tools.
- UI shows **Approve & Send**—nothing irreversible goes out until a human clicks.
- High-risk Cosmos writes (upsert/replace/delete employee or HR records) also gate on approval.

### 4.5 Extensibility

- New tools = install MCP from marketplace (or add stdio servers), not rewrite the agent.
- New workflows = add Skills Markdown, not hardcode `if onboarding: …` in app code.

---

## 5. High-impact / critical situations (use cases to emphasize)

Frame these as **“minutes instead of hours / tickets / swivel-chair”** for HR:

| Situation | Why it matters | How Vera helps |
|-----------|----------------|----------------|
| **Urgent manager ask** (“What’s Jordan’s PTO before I deny leave?”) | Bad decisions without data; slow ticket loops | Live PTO/org lookup + Canvas card |
| **Policy dispute / compliance question** | Legal/ER risk if wrong | Grounded policy search + citation |
| **Headcount / org snapshot for leadership** | Board/ops meetings need a number *now* | `count_documents` / Cosmos queries, optional CSV export |
| **New hire day-0 onboarding** | I-9 timing, missing records, email chaos | Skill-guided flow + form fill + draft welcome email (approve to send) |
| **Offboarding / access-sensitive changes** | Irreversible; audit-sensitive | Propose + HIGH-risk gate; no silent deletes |
| **Mass communication risk** | Wrong “all-hands” email = incident | Always Approve & Send; never claim sent early |
| **Benefits open enrollment Q&A** | High volume, repetitive | Policy/benefits tools, consistent answers |
| **Investigations / ER prep** | Need org + tenure + manager chain fast | Employee + org tools, no invented facts |
| **Audit / DSAR-style lookups** (directional) | Data accuracy + logging themes in schema | Query path + governance containers in data model |
| **Demo / executive buy-in** | Show AI that *acts* with guardrails | Live tool trace + Canvas + approval card |

---

## 6. Suggested live demo script (~12–15 min)

Use a **New Chat** each session (avoids stale backend conversation config).

1. **Greeting** — “hi” → short reply (shows responsiveness).  
2. **PTO** — “What is Sarah Chen's PTO balance?” → tool + Canvas PTO card.  
3. **Org** — “Show me Marcus Johnson's org chart.” → org module.  
4. **Headcount** — “How many employees do we have?” → count, first sentence = number.  
5. **Policy** — “What’s our PTO policy?” → policy_search + citation.  
6. **HITL** — “Draft an email to sarah.chen@example.com about the PTO policy.” → Approve & Send card; explain nothing sends until click.  
7. *(Optional advanced)* Onboarding / I-9 fill — longer; may need a nudge if the model stops mid-plan on long chains.

**Prefer demos that are single-tool FAST PATH** for reliability under time pressure.

---

## 7. Competitive / narrative positioning (talk track)

- Not a generic LLM wrapper: **tools + data + skills + HITL**.
- Not a full Workday replacement: an **agent that operates across** HRIS-like data, files, and channels.
- Trust story: **grounding rules**, visible activity, Canvas for review, **ConfirmRisky** for writes/sends.
- Platform story: **MCP marketplace** so IT can plug systems without rewriting Vera.

---

## 8. Honest limitations (builds credibility in Q&A)

- Intake / Work Queue / Automations are **largely visionary UI** today; Chat is the production-shaped core.
- Skills **admin page** ≠ live skill library used by the agent.
- Multi-step tool chains occasionally **stop on a planning sentence** until nudged—single-tool asks are more reliable.
- Document DOCX “template fill” doesn’t match all real HR forms (some are table/static layouts).
- Local/dev ops matter (ports, env, LLM keys); wrong canvas webhook URL historically caused multi-minute delays.
- Confirm which Cosmos database the live env points at (`closedai-hr` redesign vs older `closedai-db`) before quoting headcount on stage.

---

# PART B — Semi-technical (architecture for mixed audiences)

## 9. System at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  Browser — Vera UI (Next.js, chat_interface, :3000)          │
│  Chat · Canvas · Activity · Skills/MCP/Settings chrome      │
└───────────────┬────────────────────────────▲────────────────┘
                │ REST (create chat, confirm, proxies)        │
                │ WebSocket (live agent events / streaming)   │
                ▼                                             │
┌─────────────────────────────────────────────────────────────┐
│  Next.js BFF — keeps LLM API keys & session secrets         │
│  POST /api/chat → builds agent config + HR system prompt    │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│  HRAgent_Main — FastAPI agent server (:8001)                │
│  Conversations · event stream · confirmation · plugins      │
└───────────────┬─────────────────────────────────────────────┘
                │ MCP (stdio / HTTP tools)
        ┌───────┼───────────┬────────────────┐
        ▼       ▼           ▼                ▼
     hr-mcp   Cosmos     Azure AI         Document
     (HR UX   DB MCP     Search MCP       editor MCP
      tools)  (closedai-hr) (policies)    (PDF/DOCX)
```

**Mental model:** The LLM is the *reasoner*; MCP tools are the *hands*; Skills are the *playbooks*; ConfirmRisky is the *brake*.

---

## 10. End-to-end message flow

1. User sends a message in Chat.  
2. UI opens/reuses a WebSocket to `/sockets/events/{conversationId}`.  
3. If no backend conversation yet: Next `POST /api/chat` creates one with:
   - LLM provider config (from env),
   - long **HR system prompt** (persona, grounding, FAST PATH, HITL rules),
   - `hr-mcp` config,
   - `ConfirmRisky` + `LLMSecurityAnalyzer`,
   - client_tools for email/Slack/Teams,
   - optional canvas webhooks (prefer browser mirror locally).  
4. Backend runs the agent loop: may `invoke_skill`, call MCP tools, stream tokens.  
5. UI maps events → assistant bubble + activity steps + Canvas.  
6. If status is `waiting_for_confirmation`, UI shows approval; `POST /api/chat/confirm` resumes.

---

## 11. Data platform (closedai-hr)

Greenfield Cosmos design for the demo company **ClosedAI** (~200 employees in seed scripts; older `closedai-db` had ~500+ and messier containers).

**Physical containers (conceptual):**

| Container | What lives there |
|-----------|------------------|
| `employees` | Employee spine (SoR) |
| `employee_records` | Leave, tickets, onboarding/offboarding, reviews, … keyed by employee |
| `org` | Departments, jobs, bands, locations, positions |
| `reference` | Policies, leave policies, benefits plans, templates |
| `recruiting` | Reqs, applications, interviews, offers |
| `candidates` | Talent pool |
| `operations` | Payroll runs, audits, integrations |
| `governance_logs` | Access / AI usage / data quality themes |
| `analytics` | Snapshots, workforce plans |
| `survey_responses` | Survey data |

**Also:** Azure Storage `closedaidevstg` for real PDFs/DOCX (onboarding-forms, policy blobs). Cosmos `documents` often holds **metadata + blobUrl**, not file bytes.

---

## 12. Tooling layers

| Layer | Examples | Notes |
|-------|----------|-------|
| **hr-mcp** | `employee_lookup`, `pto_balance`, `org_chart`, `benefits_lookup`, `policy_search`, `write_workspace_file` | Built-in; Canvas `_canvas` hints; Cosmos or local seed |
| **Cosmos MCP** | `query_cosmos`, `count_documents`, upsert/replace/delete | Live DB; writes = HIGH risk |
| **Azure AI Search** | `search-documents`, `list-indexes`, hybrid/semantic | Policy PDFs; secondary to `policy_search` |
| **Document editor** | `office_fill_pdf_form`, validate, overlay, DOCX tools | GPL subprocess MCP; real I-9 AcroForms |
| **Client tools** | `send_email`, Slack, Teams | UI approval; not silent send |
| **Skills** | `hr-onboarding`, workforce/payroll/… library | Procedural knowledge via `invoke_skill` |

**FAST PATH (important product+tech story):** For headcount, simple lookups, policy Q&A, greetings—**skip** heavy advisory skills and go straight to tools / short prose. Prevents “load workforce-intelligence skill to count employees” anti-pattern.

---

## 13. Security & trust model (semi-tech)

- **`ConfirmRisky`:** Model attaches `security_risk` (LOW/HIGH). HIGH/unknown-sensitive actions pause for human confirmation. Reads should not spuriously block (`confirm_unknown: false` tuned for that).  
- **`LLMSecurityAnalyzer`:** Additional analyzer in the confirmation path.  
- **Grounding rules in prompt:** No invented employees, salaries, policies; say when data is missing; label inferences.  
- **Secrets:** LLM keys and session API keys stay on the Next/server side for conversation create; browser only holds the event WebSocket.  
- **Infrastructure (Terraform):** Azure Web App for frontend; public UI (no mandatory client certs); free-tier-friendly skips for zone redundancy / Always On in CI Checkov.

---

# PART C — Technical depth (for technical Q&A)

## 14. Repository layout

```
ClosedAI/
├── chat_interface/     # Next.js 16 UI + BFF (the live frontend)
├── HRAgent_Main/       # Python 3.13 agent server (uv), marketplaces, skills
├── hr_mcp/             # Built-in HR MCP server (FastMCP)
├── terraform/          # Azure Web App IaC + Checkov posture
├── docs/               # Audits, bug fixes, architecture, strategy PDF
└── .env / chat_interface/.env.local
```

Backend boot: `HRAgent_Main\start_server.ps1` (forces UTF-8—critical on Windows).  
Frontend boot: `chat_interface\npm run dev`.

---

## 15. Key frontend modules

| Module | Role |
|--------|------|
| `lib/chat-store.ts` | Zustand: messages, WS dispatch, streaming, approvals, activity, canvas mirror |
| `app/api/chat/route.ts` | Create conversation payload: LLM, `HR_SYSTEM_SUFFIX`, MCP, HITL, tools |
| `app/api/chat/confirm/route.ts` | HITL accept/reject → backend |
| `lib/agent-runtime.tsx` | Execution panel state mirrored from chat activity |
| `lib/canvas-store.ts` / `canvas-server.ts` / `side-canvas` / `ui-block-canvas` | Canvas UX + optional LLM block pipeline |
| `lib/mcp-store.tsx` / `mcp-api.ts` | Marketplace & connections via proxied APIs |
| `lib/backend-proxy.ts` | Forwards `/api/{mcp,skills,plugins,settings,…}` to `:8001` |

---

## 16. Key backend concepts

- **Conversation service:** Creates agents, event streams, webhooks, interrupt.  
- **Event kinds (UI cares about):** `StreamingDeltaEvent`, `MessageEvent`, `ActionEvent`, `ObservationEvent`, `ConversationStateUpdateEvent`, error events.  
- **Ambient plugins:** Installed marketplace MCPs merge into the agent at run time (not only what `/api/chat` sends).  
- **Skills discovery:** User/project/public skill tiers; keyword triggers (e.g. onboarding).  
- **Workspace:** `HRAgent_Main/workspace/` for uploads/outputs and staged forms.

---

## 17. LLM providers

Configured via env (`LLM_PROVIDER`): TokenRouter, Groq, OpenAI, classic Azure OpenAI, or **Azure AI Foundry** via OpenAI-compatible base URL (use `openai` provider path, not classic `azure/` host assumptions). Temperature low (~0.2) for HR factuality; streaming on by default.

---

## 18. Operational pitfalls worth one slide (“lessons learned”)

| Issue | Symptom | Lesson |
|-------|---------|--------|
| Canvas webhook → wrong port (`:3001` vs `:3000`) | Greetings take ~1 minute | Don’t await dead webhooks on every stream token |
| Azure Search bad hostname | ~30s delay every new chat | Validate MCP endpoints |
| Windows cp1252 | Backend crash on emoji | UTF-8 everywhere (`start_server.ps1`) |
| Fictional Search tool names | “Working” MCP that can’t be called | Verify real tool schemas |
| Skills page mock vs chat skills | Confusing demos | Separate “UI catalog” from “runtime skills” |
| Long tool chains | Intermediate “I’ll query…” without final | Prefer short demos or nudge finalize |

---

## 19. CI / quality story (short)

- Semgrep / pip-audit / npm audit / Checkov / gitleaks in GitHub Actions.  
- Hardening examples: urllib→requests, shell=False+shlex, defused/html escape, dependency bumps, Terraform free-tier Checkov skips.

---

# PART D — Slide outline (~45–50 min + Q&A)

Use this as a deck skeleton (≈1–2 min per slide unless noted).

| # | Slide | Minutes | Source section |
|---|-------|---------|----------------|
| 1 | Title: Vera — AI HR Copilot for ClosedAI | 1 | Names |
| 2 | The problem: HR swivel-chair & slow answers | 2 | §1, §5 |
| 3 | What Vera is / isn’t | 2 | §1–2 |
| 4 | Live product tour (screenshot) | 2 | §3 |
| 5 | Core loop: Ask → Tools → Canvas → Approve | 3 | §9–10 |
| 6 | Demo 1: Lookup + Canvas (PTO/org) | 4 | §6 |
| 7 | Demo 2: Headcount FAST PATH | 2 | §6, §12 |
| 8 | Demo 3: Policy with citation | 3 | §4.2 |
| 9 | Demo 4: Draft email + Approve & Send | 4 | §4.4 |
| 10 | Skills = playbooks, not hardcoded if-statements | 3 | §4.5, docs/skills |
| 11 | MCP marketplace = plug in systems | 3 | §3.5, §12 |
| 12 | Data: closedai-hr model (one diagram) | 3 | §11 |
| 13 | Trust & HITL | 3 | §13 |
| 14 | Architecture (one diagram) | 3 | §9 |
| 15 | High-impact situations | 3 | §5 |
| 16 | Roadmap: Intake / Work / Automations vision | 2 | §3.6 |
| 17 | Honest status & lessons | 2 | §8, §18 |
| 18 | Closing + ask | 1 | — |
| — | **Q&A** | **10–15** | Parts B–C |

**Total talk ≈ 45 min; Q&A ≈ 15 min.**

---

# PART E — Speaker cheat sheet (one page)

- **Brand:** Vera · **Category:** AI HR Copilot · **Company data:** ClosedAI.  
- **Hero capability:** Natural language → live HR tools → Canvas → human approval for sends/writes.  
- **Do not say:** “Fully autonomous HR system” or “Intake/Work Queue is fully live.”  
- **Do say:** “Action layer with guardrails”; “MCP-extensible”; “Grounded in Cosmos + policies + forms.”  
- **Best demo order:** PTO → org → headcount → policy → email approval.  
- **If slow:** New Chat; confirm backend `:8001` and UI `:3000`; avoid old conversations with bad webhook config.  
- **If asked tech depth:** Point to Next BFF + HRAgent + MCP + ConfirmRisky; offer architecture diagram.

---

# PART F — Appendix: glossary

| Term | Meaning |
|------|---------|
| **MCP** | Model Context Protocol — standard tool/server interface for agents |
| **HITL** | Human-in-the-loop — approval before irreversible actions |
| **Skill** | Markdown procedural guide the agent can load mid-conversation |
| **Canvas** | Side panel for structured artifacts |
| **FAST PATH** | Prompt rule to skip skills for simple factual asks |
| **ConfirmRisky** | Policy that pauses HIGH-risk tool calls for confirmation |
| **BFF** | Backend-for-frontend (Next.js API routes holding secrets) |
| **Ambient plugins** | Marketplace MCPs auto-merged into the agent at run |

---

*Generated for presentation prep from the ClosedAI codebase and docs (`STARTUP.md`, `docs/project_audit.md`, `docs/Automations.md`, `docs/bug_fixes.md`, `docs/skills.md`, `docs/architecture/*`, strategy PDF themes, `chat_interface` / `HRAgent_Main` / `hr_mcp`). Update env-specific numbers (headcount, endpoints) against the live deployment the day you present.*
