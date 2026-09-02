---
name: hr-ticketing
description: >
  Operational guide for HR ticketing and case management: intake triage,
  urgency/SLA, routing to the right specialist, drafting replies, escalating
  sensitive cases, and syncing tickets with the Work Queue. Invoke when the
  user asks about HR tickets, helpdesk cases, intake triage, SLAs, escalations,
  case routing, or closing employee/manager requests.
triggers:
  - ticket
  - ticketing
  - helpdesk
  - intake
  - case management
  - SLA
  - escalate ticket
  - HR request
  - triage
metadata:
  owner: people-operations
  maturity: pilot
  author: ClosedAI
  version: "1.0.0"
---

# HR Ticketing — Operational Guide

Use this skill for **intake → triage → work → resolve** flows in Vera. Prefer
live tools and the product surfaces (Tasks / Work Queue / Alerts) over inventing
ticket systems that do not exist here.

## What good HR ticketing accomplishes

- Every employee or manager request is **captured**, **classified**, and
  **owned** with a clear next step.
- Urgency and SLA match risk (payroll miss, visa, harassment ≠ PTO FAQ).
- Sensitive cases escalate early; routine ones self-serve or resolve fast.
- Outcomes are auditable: what was asked, what was done, who approved.

## Ticket taxonomy (use these labels)

| Cluster | Examples | Typical owner |
|---------|----------|---------------|
| Benefits / payroll | enrollment, deductions, pay issues | Benefits / Payroll |
| Leave / attendance | PTO, LOA, missing punches | People Ops |
| Onboarding / offboarding | new hire setup, access, exits | People Ops |
| Work authorization | visa expiry, I-9, E-Verify | Immigration / Ops |
| Employee relations | conflict, performance concerns | ER / HRBP (escalate) |
| Policy / general | handbook questions | Tier 1 / self-serve |
| Recruiting ops | offer letter, start date change | TA Ops |

## Triage checklist (do this first)

1. **Identify requester** — employee vs manager vs candidate; confirm identity
   with live lookup tools when available (`employee_lookup`, Cosmos query).
2. **Classify urgency**
   - **Urgent:** safety, harassment, payroll-stopping, visa &lt; 14 days, legal hold
   - **High:** benefits cutoff, start-date this week, manager escalations
   - **Normal:** policy FAQ, routine docs, non-blocking questions
3. **Choose disposition**
   - **Auto / self-serve** — policy answer + link; close with confirmation
   - **Copilot draft** — reply or form fill; human approve before send
   - **Human specialist** — ER, Legal, Immigration, Payroll
4. **Open or update Work Queue** — one ticket → one work item when action is
   multi-step or needs approval. Source = ticketing; keep `externalRef` tied to
   the intake id (e.g. `Intake · IN-####`).
5. **Never invent** employee records, ticket ids, or policy text. Use tools.

## SLAs (defaults — adjust if org policy differs)

| Urgency | First response | Resolution target |
|---------|----------------|-------------------|
| Urgent | &lt; 1 hour | Same business day or escalate |
| High | &lt; 4 hours | 2 business days |
| Normal | &lt; 1 business day | 5 business days |

If you cannot meet an SLA, say so and escalate — do not silently stall.

## Escalation rules (hard stops)

Escalate immediately (do **not** auto-close) when the case involves:

- Harassment, discrimination, retaliation, or workplace violence
- Legal holds, investigations, or union/grievance language
- Medical privacy beyond routine benefits admin (treat as sensitive)
- Work authorization already expired or &lt; 14 days with no packet started
- Payroll errors affecting multiple people or current-cycle pay

Draft a short handoff note: facts, risk, what was already tried, asked decision.

## Reply and action patterns

### Routine policy / FAQ

1. Answer from policy tools (`policy_search` / knowledge) with citations.
2. Offer a one-click path if the product has one; otherwise clear next step.
3. Close only after the requester’s question is addressed.

### Document / letter requests

1. Confirm employee identity and what the letter must attest.
2. Draft with document tools; **ConfirmRisky / HITL** before send or portal push.
3. Prefer `send_email` (approved) over inventing a portal send.

### Multi-step cases (onboarding, leave, visa)

1. Invoke the matching domain skill (`hr-onboarding`, `hr-immigration`, leave
   skills, etc.) **after** this triage skill if needed.
2. Track steps on the Work Queue item; pause on `needs_approval` for HIGH risk.

## Tools this org actually has

- **Intake / Tasks** — ticket list and clusters in the UI
- **Work Queue** — live work items (chat, intake, ad hoc) — not dummy seed
- **HR alerts** — birthdays, visas, urgent tickets, approvals
- **MCP / Cosmos** — employee truth, policies, documents
- **Client tools** — `list_emails` / `send_email` with approval for outbound mail

If a ticketing platform (ServiceNow, Jira Service Management, Zendesk) is not
connected via MCP, say so and work in Intake + Work Queue instead of faking
external ticket numbers.

## Anti-patterns

- Closing sensitive cases with a generic FAQ
- Creating duplicate work items for the same intake id
- Skipping approval on outbound email or employee-record writes
- Promising SLAs you cannot measure or meet
- Dumping the full skill text as the user-facing answer — execute, then summarize

## Example user intents that should invoke this skill

- "Triage the open HR tickets"
- "How should we route leave vs ER cases?"
- "Draft an SLA for payroll tickets"
- "Escalate this helpdesk case"
- "Turn this intake item into work and reply to the employee"
