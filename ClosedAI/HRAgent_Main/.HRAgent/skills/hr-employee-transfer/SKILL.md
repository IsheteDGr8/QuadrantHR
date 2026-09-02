---
name: hr-employee-transfer
description: >
  Business knowledge for moving an existing employee to a new role, team,
  manager, department, or location — internal transfers, reorganizations,
  promotions that change reporting, and relocations. Covers what to confirm,
  what usually changes, approvals, and when to escalate. Invoke this when the
  user asks to transfer, move, reassign, relocate, or change the department /
  manager of an employee. Guidance, not a fixed workflow.
triggers:
  - transfer
  - relocation
  - relocate
  - department change
  - change department
  - reassign
  - internal move
  - change manager
metadata:
  owner: people-operations
  maturity: pilot
---
# Employee Transfer — Knowledge

## What a transfer is trying to accomplish
A transfer moves an employee into a new position (team, manager, department,
level, or location) while keeping their employment continuous and their records
accurate. Success means: the change is authorized, the employee record reflects
the new state, downstream effects (access, comp, location, org chart) are handled
or handed off, and the people involved are informed. The order depends on the
case — don't force a fixed sequence.

## What to confirm before changing anything
Look the employee up before acting; don't assume:
- Who is moving: full name, employee ID, **current** role, department, manager,
  and location. Use `employee_lookup`, then `query_cosmos` if needed, trying name
  variations before concluding they aren't found.
- The target state: new role/title, new manager, new department, new location, and
  the **effective date**.
- Type of move: lateral vs. promotion vs. relocation, and whether it affects
  compensation. Compensation changes are sensitive and typically need approval.

If any of these are missing and you can't derive them, ask for the specific item.

## What usually changes in a transfer
Use judgment about which apply:
- **Employee record**: manager, department, title, level, location, cost center.
- **Reporting / org chart**: the old and new manager relationships (`org_chart`).
- **Access**: systems and permissions tied to the old role/team may need to be
  removed and new ones granted.
- **Compensation / location**: pay, allowances, or tax/location data may change —
  treat these as approval-gated and cite policy rather than guessing figures.
- **Communications**: notify the employee and the old/new managers as appropriate.

## Systems and tools that may be involved
- **Employee records** — `employee_lookup`, `query_cosmos`, `count_documents`,
  `org_chart`.
- **Policy** — `search-documents` / `policy_search` for transfer, relocation, or
  compensation-change policy; cite the source.
- **Documents** — `office_*` tools if a transfer letter or form needs to be prepared
  and saved under `outputs/`.
- **Communications** — `send_email` to notify stakeholders (HIGH risk; needs approval).

**Systems not yet integrated (dummy references):** direct writes to the HRIS to
*commit* a role/manager change, plus IT access re-provisioning and payroll updates,
are not wired into this agent yet. When the task needs them, state clearly that the
record change must be made in the system of record / handed off — do **not** claim
the transfer was committed if you only drafted or described it.

## When approval is needed
Reads are free. Anything that changes an external record, alters compensation, or
sends a message is HIGH risk and must wait for explicit human approval. Set the
security_risk accordingly and never report the transfer as done before approval.

## When to verify vs. escalate
- **Verify**: re-read the record (or confirm via `employee_lookup`) after a change
  is supposed to have happened; confirm you're acting on the right person when names
  collide.
- **Escalate / hand off**: compensation changes needing sign-off, moves that cross
  legal entities or countries, conflicting data, or anything requiring the HRIS /
  IT / payroll systems that aren't available here. Say what's blocked and what you
  need instead of assuming completion.
