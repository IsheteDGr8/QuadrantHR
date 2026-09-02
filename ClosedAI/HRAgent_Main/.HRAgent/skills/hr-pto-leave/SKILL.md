---
name: hr-pto-leave
description: >
  Business knowledge for handling paid time off and leave: checking balances,
  answering accrual/eligibility questions, reasoning about time-off and
  leave-of-absence requests, and knowing which policy governs. Covers what to
  verify, which policy to cite, approvals, and when to escalate. Invoke this when
  the user asks about PTO, vacation, sick time, time off, or a leave of absence.
  Guidance, not a fixed workflow.
triggers:
  - pto
  - paid time off
  - vacation
  - time off
  - sick leave
  - leave of absence
  - loa
  - leave request
metadata:
  owner: people-operations
  maturity: pilot
---
# PTO / Leave Management — Knowledge

## What this is trying to accomplish
Help HR answer time-off questions and process requests correctly: give the right
current balance, apply the right policy, respect eligibility and approval rules,
and communicate clearly. Success means the answer is grounded in real data and
the correct policy — never a guessed number. What you do depends on whether the
user wants a *balance/eligibility answer* or wants to *act on a request*.

## What to verify first
- Who it's about: employee name/ID, and (for requests) their manager and location,
  since policy can vary. Use `employee_lookup`; fall back to `query_cosmos` and try
  name variations before saying they aren't found.
- The current balance and accrual: use `pto_balance` — do not state a number from
  memory. If the tool doesn't return a field, say it's unavailable rather than
  inventing it.
- The request specifics (if any): leave type (vacation / sick / LOA), dates, and
  duration.

## Types of time off and what governs them
Different categories have different rules — cite the governing policy instead of
generalizing:
- **PTO / vacation**: accrual, carryover caps, and blackout rules.
- **Sick leave**: often separate from PTO, with its own accrual and jurisdiction rules.
- **Leave of absence (LOA)**: medical, parental, or personal leave — usually
  eligibility-based, often needs documentation, and may be legally protected.
Look these up with `policy_search` / `search-documents` against the company
policies index and cite the document/section.

## Reasoning about a request (not a hardcoded flow)
Typical things to consider, in whatever order fits: confirm the employee and
current balance; check the request against the relevant policy (enough balance,
eligible, no blackout/conflict); note who approves it; and communicate the outcome.
Decide which of these actually matter for the specific ask.

## Systems and tools that may be involved
- **Balances / records** — `pto_balance`, `employee_lookup`, `query_cosmos`.
- **Policy** — `policy_search`, `search-documents`, `get-document`; always cite.
- **Communications** — `send_email` to confirm decisions or notify a manager
  (HIGH risk; needs approval).

**Systems not yet integrated (dummy references):** actually *booking* or *deducting*
leave in a time-and-attendance / HRIS system is not wired into this agent yet. When
a request needs to be recorded or approved in that system, say so and treat it as a
hand-off — do **not** claim leave was booked or a balance was deducted when you only
checked or drafted something.

## When approval is needed
Reads (balances, policy, eligibility) are free. Approving/booking leave, deducting a
balance, or sending a decision email are HIGH-risk actions that must wait for explicit
human approval. Set the security_risk and don't report a request as approved/booked
before that happens — and manager approval for the leave itself may still be required
beyond the platform's own approval gate.

## When to verify vs. escalate
- **Verify**: re-check the balance with `pto_balance` before relying on it; confirm
  the policy actually covers the situation before quoting a rule.
- **Escalate / hand off**: legally protected or complex leave (medical/parental),
  insufficient balance or policy conflicts, anything needing the time-and-attendance
  system, or manager-level approval. State what's blocked and what you need rather
  than assuming the request is settled.
