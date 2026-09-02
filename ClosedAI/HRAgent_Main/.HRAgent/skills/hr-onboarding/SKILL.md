---
name: hr-onboarding
description: >
  Business knowledge for onboarding a new (or newly hired) employee: what
  onboarding is trying to accomplish, what to verify about the person, common
  requirements and paperwork, which systems are usually involved, when approval
  is needed, and when to escalate instead of assuming a step is done. Invoke this
  when the user asks to onboard, set up, or prepare paperwork for a new hire.
  This is guidance, not a fixed script — decide at runtime which parts apply and
  which tools to use.
triggers:
  - onboard
  - onboarding
  - new hire
  - new employee
  - onboarding checklist
  - set up new employee
metadata:
  owner: people-operations
  maturity: pilot
  author: Tuan Duc Tran
  version: "1.0.1"
---

# Employee Onboarding — Operational Guide

This skill combines **this organization's onboarding process** (documents, tools,
approvals, and verification) with broader HR onboarding knowledge in
`content/`, `prompts/`, and `examples/`. **Follow the operational sections
below first** when running onboarding in this agent — they describe how to use
the workspace, document tools, and email flow that actually exist here.

## What onboarding is trying to accomplish

Onboarding turns an accepted offer into a productive, compliant, and welcomed
employee. A good onboarding leaves the person with: a correct employee record,
completed legal/compliance paperwork, access to the systems they need, enrolled
benefits, and a clear first-week plan. Treat these as *outcomes to confirm*, not
a rigid order of operations — the right sequence depends on the employee, their
start date, and what is already done.

## What to verify about the new employee first

Before doing anything that writes or sends, confirm you actually have the person
and their key facts. Look them up rather than assuming:

- Identity & role: full legal name, employee ID, job title, department, manager,
  work location, and **start date**. Use `employee_lookup` first; if it returns
  nothing, fall back to `query_cosmos` (e.g. a `CONTAINS(c.name, ...)` query) and
  try spelling/format variations before concluding the person isn't in the system.
- Employment specifics that change the paperwork: employment type (FT/PT/contract),
  work authorization / visa status (this drives I-9 attestation), and remote vs.
  on-site (drives equipment and access).

If a required fact is genuinely missing after you've tried the tools, ask the
user for that specific fact — don't invent it and don't stall on things you can
look up yourself.

## Common onboarding requirements

Not every hire needs all of these; use judgment based on role and location.

- **Compliance paperwork**: Form I-9 (employment eligibility), tax withholding,
  and signed acknowledgments (NDA, Code of Conduct). Blank templates live in the
  workspace (`i9_form.pdf`, `employee_nda.pdf`, `code_of_conduct_acknowledgment.docx`,
  `emergency_contact_form.docx`).
- **Benefits enrollment**: confirm eligibility and enrollment window; point to the
  correct policy rather than quoting numbers from memory.
- **Access & equipment**: accounts, email, tools, and hardware appropriate to the role.
- **First-week setup**: manager intro, team, required training, and a welcome note.

## Document workflow (this workspace)

Use document tools to work with forms directly — do **not** ask the user to upload
templates that are already in the workspace.

1. **Discover fields** — `office_list_pdf_fields` for PDFs (I-9, NDA);
   `office_list_docx_fields` for DOCX forms (emergency contact, code of conduct).
2. **Fill forms** — `office_fill_pdf_form` or `office_fill_docx_form` with real
   values from employee lookup. Save filled copies under `outputs/`
   (e.g. `outputs/i9_form_Jane_Doe.pdf`) so the user can preview and download.
3. **Flat PDFs (NDA)** — if a PDF has no AcroForm fields, use
   `office_overlay_pdf_text` for signature/name/date at the correct coordinates.
4. **Validate** — run `office_validate` (and re-read with `office_read`) after
   filling; confirm the right person and fields before claiming the form is done.

Fill only fields you have real values for. Never fabricate SSNs, dates, or
document numbers.

## Systems and tools that may be involved

Use the tools you actually have; don't claim you lack them:

- **Employee records** — `employee_lookup`, `query_cosmos`, `count_documents`.
- **Documents / forms** — `office_read`, `get_document_info`, `office_list_pdf_fields`,
  `office_fill_pdf_form`, `office_list_docx_fields`, `office_fill_docx_form`,
  `office_overlay_pdf_text`, `office_validate`.
- **Policies / benefits** — `search-documents` / `policy_search` / `benefits_lookup`;
  cite the document and section.
- **Communications** — `send_email` for welcome notes or sending completed forms
  (HIGH risk; see approvals below). Pass workspace-relative attachment paths
  (e.g. `["outputs/i9_form_Jane_Doe.pdf"]`).

**Systems not yet integrated:** IT account/equipment provisioning and payroll
setup are *not* wired into this agent yet. When a step needs them, say so plainly
and treat it as a hand-off/escalation — do **not** pretend a provisioning ticket
or payroll entry was created.

## Handling missing information

If you're missing something the task needs, first try to retrieve it (database,
documents, policies). Only ask the user for what you truly cannot derive, and ask
for the *specific* item.

## When approval is needed

Reads and lookups are free. Anything that sends, writes, or changes something
external is HIGH risk and must be held for explicit human approval — e.g. emailing
a form or welcome message (`send_email`). Set `security_risk=HIGH` on the call and
never claim it happened before the human approves in chat.

## When to verify vs. escalate

- **Verify** that a step actually completed: after filling a form, run
  `office_validate` / re-read it; after a lookup, confirm you got the right person.
- **Escalate / hand off** when a required system isn't available (IT, payroll), when
  approvals are outside HR's authority, or when data conflicts (e.g. two employees
  with the same name). Tell the user what's blocked and what you need — don't
  declare onboarding "complete" prematurely.

---

## Supplementary onboarding knowledge

The sections below and the files in this skill directory provide broader HR
onboarding and offboarding guidance (program design, pre-boarding, remote
onboarding, measurement, exit interviews). Use when the user asks for plans,
checklists, or best practices beyond executing this organization's document and
email workflow.

### Supported tasks (general)

- Creating onboarding plans, checklists, and timelines
- Designing orientation programs and buddy/mentor programs
- Pre-boarding activities and virtual/remote onboarding
- Measuring onboarding effectiveness (30/60/90-day check-ins)
- Offboarding, exit interviews, and knowledge transfer (see also `hr-offboarding`)

### Reference material in this skill

- `content/managing-employee-transitions-effectively.md` — lifecycle transitions,
  modern onboarding/offboarding practices
- `prompts/employee-onboarding.md` — reusable prompt templates
- `examples/designing-a-new-hire-onboarding-plan.md` — sample onboarding plan
- `examples/create-30-60-90-day-onboarding-plan.md` — 30/60/90-day plan example

### Tips

- Start onboarding before day one — strong pre-boarding reduces first-day anxiety.
- Extend onboarding beyond the first week — effective programs often span 3–6 months.
- Assign a buddy/mentor to every new hire when possible.
- Gather feedback at 30, 60, and 90 days to improve the experience.
- Treat offboarding as seriously as onboarding — positive exits protect employer brand.
