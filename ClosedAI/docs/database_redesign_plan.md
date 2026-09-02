# ClosedAI HR Database — Redesign & Reseed Plan

**Status:** Proposed target-state spec. This document is the source of truth for a
rebuild of `closedai-db`. It is written to be handed to Claude Code as the
specification for generating/editing data. Claude Code should treat every
schema, enum, ID convention, and integrity rule here as binding.

**Goal:** turn today's inconsistent, partially-orphaned database into a single,
internally-consistent HR system-of-record that any of our 146 skills and 7 tools
can query and get correct, connected answers from — no missing links, no
name-vs-ID confusion, no duplicate people, no conflicting policy numbers.

---

## 0. Why we're doing this (current problems, from an audit of the live DB)

The live database (`closedai-db`, 22 containers, ~517 employee docs) has these
concrete defects. Every one of them is addressed by the target spec below.

| # | Problem | Example | Fix (section) |
|---|---------|---------|---------------|
| 1 | **Orphaned child records** — tickets/checklists reference employees who don't exist in `employees` | `hr_tickets.employeeId = "emp-sam"`; `onboarding_checklists.employee_id` = a UUID never in `employees` | §4 Referential integrity |
| 2 | **FKs hold names, not IDs** | `employees.managerId = "Thiwagar"` (a first name) | §1 Conventions, §2 Employee |
| 3 | **Duplicate person records** | "Ishaan Shete" appears multiple times with different IDs/departments | §4 Dedupe |
| 4 | **snake_case vs camelCase collisions** | `employee_id`/`employee_name` (onboarding, tickets) vs `employeeId`/`name` (everywhere else) | §1 Conventions |
| 5 | **Same fact stored two ways** | `salary` and `annualSalary`; `role` and `title`; `manager` and `managerId` | §1, §2 |
| 6 | **Nonsense values** | exec `annualSalary: 10000` | §2 comp bands drive salaries |
| 7 | **Quick tools can't reach the data** | `pto_balance`/`benefits_lookup` read a nested `pto`/`benefits` object that live `employees` docs don't have | §2 derived snapshots + §3 normalized source |
| 8 | **Conflicting policy numbers** | PTO base = 15 (policies) vs 18–28 (mock) vs 20 (tickets) | §3 policies, §4 reconciliation |
| 9 | **Missing exec reporting lines** | CEO/CxO have blank `managerId`, so they look like separate roots | §4 org tree rules |
| 10 | **Three disconnected policy corpora** | HR Core mock `POLICIES`, Cosmos `policies`, Azure Search `company-policies` | §3 policies (one corpus) |

---

## 1. Global conventions (apply to EVERY container)

These are non-negotiable and make the whole DB self-consistent.

### 1.1 Identity
- Every document has **both** `id` and its typed business key, set to the **same
  value**. e.g. an employee doc has `"id": "emp-0001"` and `"employeeId": "emp-0001"`.
- IDs use a **typed prefix + zero-padded counter**. Never a raw name, never a bare UUID.

| Entity | ID prefix | Example |
|--------|-----------|---------|
| Employee | `emp-` | `emp-0001` |
| Department / org unit | `dept-` | `dept-eng` |
| Job (catalog role) | `job-` | `job-0007` |
| Compensation band | `band-` | `band-ENG-4` |
| Leave request | `leave-` | `leave-0042` |
| Leave balance | `bal-` | `bal-emp-0001-pto-2026` |
| Benefits plan | `plan-` | `plan-med-ppo` |
| Benefits election | `elec-` | `elec-0031` |
| Payroll run | `run-` | `run-2026-08` |
| Pay statement | `pay-` | `pay-0777` |
| HR ticket | `tkt-` | `tkt-0123` |
| Onboarding checklist | `onb-` | `onb-0009` |
| Offboarding checklist | `off-` | `off-0003` |
| Policy | `policy-` | `policy-pto` |
| Document | `doc-` | `doc-0050` |
| Document template | `tmpl-` | `tmpl-i9` |
| Asset | `asset-` | `asset-0210` |
| Job requisition | `req-` | `req-0015` |
| Candidate | `cand-` | `cand-0088` |
| Application | `app-` | `app-0140` |
| Interview | `intv-` | `intv-0301` |
| Offer | `offer-` | `offer-0021` |
| Review cycle | `cycle-` | `cycle-2026-h1` |
| Performance review | `rev-` | `rev-0400` |
| Goal | `goal-` | `goal-0900` |

### 1.2 Naming
- **camelCase for all field names.** No snake_case. (`employeeId`, `firstName`,
  `createdAt` — never `employee_id`, `created_at`.)
- **Foreign keys are always IDs**, suffixed `Id` (or `Ids` for arrays):
  `managerId`, `departmentId`, `jobId`, `requisitionId`. A FK value MUST be a real
  `id` that exists in the referenced container.
- For display convenience, a FK MAY be accompanied by a **denormalized name**
  field suffixed `Name`, clearly derived: `managerId: "emp-0006"`,
  `managerName: "Priya Nair"`. The `Id` is the source of truth; the `Name` is a
  cache the generator fills and keeps consistent.

### 1.3 Standard metadata (on every document)
```jsonc
{
  "company": "ClosedAI",          // constant for this dataset
  "schemaVersion": 2,              // bump when schema changes
  "createdAt": "2026-01-15T09:00:00Z",  // ISO 8601 UTC
  "updatedAt": "2026-08-01T12:30:00Z"
}
```

### 1.4 Types & formats
- Dates: `date` = `"YYYY-MM-DD"`, timestamps = ISO 8601 UTC `"...Z"`.
- Money: integer or 2-decimal number in **minor-unit-free major units** (e.g.
  `165000` = $165,000), always paired with `currency` (`"USD"`).
- Enums: lower_snake string values from the fixed lists in §5. No free text where
  an enum is defined.
- Missing/unknown: use `null`, never `""` or `"N/A"` or a made-up value.

### 1.5 Partition keys
Keep the existing, sensible partition keys (changing a PK requires recreating the
container — do that only where noted). Target PKs are listed per container in §2/§3.
Rule of thumb: employee-scoped containers partition on `/employeeId`; standalone
catalogs partition on `/id`.

---

## 2. Tier 0 — The spine (must be perfect and fully interconnected)

Everything else references these. Build these first, validate, then fan out.

### 2.1 `employees`  (PK `/employeeId`)

Single source of truth for a person's current state. Target: **one coherent
~200-person ClosedAI org** (see §4.1 for the org-tree rules). Configurable up to
500 with the same generator, but 200 is the canonical, fully-connected set.

```jsonc
{
  "id": "emp-0006",
  "employeeId": "emp-0006",

  // identity
  "firstName": "Priya",
  "lastName": "Nair",
  "name": "Priya Nair",                 // derived: firstName + " " + lastName
  "preferredName": "Priya",
  "workEmail": "priya.nair@closedai.com",
  "personalEmail": "priya.nair@gmail.com",
  "phone": "+1-206-555-0142",
  "dateOfBirth": "1986-02-11",

  // employment
  "employmentStatus": "active",          // enum §5
  "employmentType": "full_time",         // enum §5
  "flsaStatus": "exempt",                // enum §5
  "hireDate": "2020-06-01",
  "terminationDate": null,
  "tenureYears": 6.2,                    // derived from hireDate

  // org placement (all FKs resolve)
  "departmentId": "dept-product",
  "departmentName": "Product",           // derived
  "jobId": "job-0007",
  "jobTitle": "Director of Product",     // derived from jobs.title
  "jobLevel": 5,                          // derived from jobs.level
  "managerId": "emp-0001",               // FK -> employees; null ONLY for CEO
  "managerName": "Diego Moore",          // derived
  "isPeopleManager": true,               // derived: someone has this as managerId
  "directReportCount": 6,                 // derived

  // location
  "workLocationId": "loc-sea",
  "workLocationName": "Seattle, WA",
  "country": "US",
  "workMode": "hybrid",                  // enum §5
  "timezone": "America/Los_Angeles",

  // compensation (source of truth for pay; must sit inside its band, §2.4)
  "compensation": {
    "annualSalary": 210000,
    "currency": "USD",
    "payFrequency": "biweekly",          // enum §5
    "bandId": "band-PROD-5",             // FK -> compensation_bands
    "compaRatio": 0.98                   // derived: salary / band.mid
  },

  // compliance
  "workAuthorization": {
    "status": "citizen",                 // enum §5
    "visaType": null,                    // e.g. "H-1B" when status=visa
    "expirationDate": null
  },

  // derived convenience snapshots (regenerated atomically; NOT source of truth).
  // These let the quick tools (pto_balance/benefits_lookup) answer without a join.
  "ptoSnapshot": {
    "accrualDaysPerYear": 18,            // from leave policy tier (§3.1 rules)
    "usedDays": 6,                        // = sum(approved pto leave_requests this year)
    "remainingDays": 12,                  // accrual - used
    "asOf": "2026-08-01"
  },
  "benefitsSnapshot": {
    "medicalPlanId": "plan-med-ppo",
    "medicalPlanName": "PPO Plus",
    "dentalPlanId": "plan-den-std",
    "visionPlanId": "plan-vis-basic",
    "retirement401kPercent": 6,
    "employerMatchPercent": 4
  },

  // engagement (optional analytics)
  "engagementScore": 7.7,                // 0-10 or null
  "lastSurveyDate": "2026-05-01",

  "company": "ClosedAI",
  "schemaVersion": 2,
  "createdAt": "2020-06-01T09:00:00Z",
  "updatedAt": "2026-08-01T12:00:00Z"
}
```

**Removed/renamed from current:** drop bare `role` (→ `jobTitle` derived from
`jobId`), drop bare `salary` (→ `compensation.annualSalary`), `manager` string →
`managerId`+`managerName`, `start_date`→`hireDate`, `employment_type` no longer
overloaded with `status`.

> **Design note (tools):** `ptoSnapshot`/`benefitsSnapshot` are deliberately
> denormalized so `pto_balance` and `benefits_lookup` keep working with no code
> change. The **ledgers** (`leave_requests`, `benefits_elections`) remain the
> source of truth; the generator computes the snapshot from them so they can
> never disagree at seed time. (Follow-up option: update those two tools to join
> the ledgers directly and drop the snapshots.)

### 2.2 `departments`  (org units)  (PK `/id`)  — **NEW/UPGRADED**

Replaces the free-text `department` string with a real, hierarchical org unit
table so org-design / spans-and-layers / analytics skills work.

```jsonc
{
  "id": "dept-product",
  "departmentId": "dept-product",
  "name": "Product",
  "parentDepartmentId": "dept-company",   // FK -> departments; null for the root
  "leaderEmployeeId": "emp-0001",         // FK -> employees
  "leaderName": "Diego Moore",            // derived
  "costCenter": "CC-2000",
  "layerLevel": 2,                         // derived: depth from root (root=1)
  "headcount": 42,                         // derived: employees in this + child units
  "company": "ClosedAI", "schemaVersion": 2,
  "createdAt": "2020-01-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z"
}
```
Seed ~8–10 departments under one root `dept-company` (Engineering, Product, Data
& Analytics, Sales, Customer Success, Marketing, Finance, People/HR, Operations).

### 2.3 `jobs`  (job catalog)  (PK `/jobId`)  — **NEW/UPGRADED**

The catalog of roles. Employees reference a `jobId`; requisitions reference a
`jobId`; comp bands map to job families.

```jsonc
{
  "id": "job-0007",
  "jobId": "job-0007",
  "title": "Director of Product",
  "jobFamily": "PROD",                    // FK-ish -> compensation_bands.jobFamily
  "level": 5,                              // 1=IC entry ... 8=CEO (see §5 leveling)
  "flsaStatus": "exempt",
  "isManagerJob": true,
  "description": "Leads product management for a business line.",
  "requiredSkills": ["product_strategy", "roadmapping", "stakeholder_mgmt"],
  "company": "ClosedAI", "schemaVersion": 2,
  "createdAt": "...", "updatedAt": "..."
}
```

### 2.4 `compensation_bands`  (PK `/jobFamily`)

```jsonc
{
  "id": "band-PROD-5",
  "bandId": "band-PROD-5",
  "jobFamily": "PROD",
  "level": 5,
  "currency": "USD",
  "min": 180000, "mid": 215000, "max": 250000,
  "geoZone": "US-national",
  "company": "ClosedAI", "schemaVersion": 2,
  "createdAt": "...", "updatedAt": "..."
}
```
**Rule:** every `employees.compensation.annualSalary` must fall within its
`bandId` min/max. The generator sets salary = band.mid × (0.85–1.15) jittered.

---

## 3. Tier 1 — Operational containers (tool-backed; used constantly)

### 3.1 `leave_requests`  (PK `/employeeId`)  + `leave_balances`  (PK `/employeeId`)

Ledger of leave + a per-year balance rollup. Source of truth for PTO.

```jsonc
// leave_requests
{
  "id": "leave-0042", "leaveRequestId": "leave-0042",
  "employeeId": "emp-0031",               // FK -> employees (MUST exist)
  "employeeName": "Mia Brown",            // derived
  "leaveType": "pto",                     // enum §5
  "startDate": "2026-08-10", "endDate": "2026-08-14",
  "businessDays": 5,                       // derived, excludes weekends/holidays
  "status": "approved",                    // enum §5
  "approverId": "emp-0006",               // FK -> employees
  "requestedDate": "2026-07-20",
  "reason": null,
  "company": "ClosedAI", "schemaVersion": 2,
  "createdAt": "...", "updatedAt": "..."
}

// leave_balances (one per employee × leaveType × year)
{
  "id": "bal-emp-0031-pto-2026", "employeeId": "emp-0031",
  "leaveType": "pto", "year": 2026,
  "accruedDays": 18, "usedDays": 5, "pendingDays": 0, "availableDays": 13,
  "asOf": "2026-08-01",
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}
```
**Accrual policy (reconciles the conflicting numbers — this is now THE rule):**
- Base PTO accrual by tenure: `<2 yrs = 15`, `2–5 yrs = 18`, `5+ yrs = 22` days/year.
- Sick leave: flat 10 days/year.
- These numbers must match the `policy-pto` document text (§3.6) exactly.

### 3.2 `benefits_plans` (PK `/planId`), `benefits_elections` (PK `/employeeId`), `benefits_catalog` (PK `/id`)

```jsonc
// benefits_plans
{
  "id": "plan-med-ppo", "planId": "plan-med-ppo",
  "planName": "PPO Plus", "planType": "medical",   // enum §5
  "carrier": "BlueCross",
  "monthlyPremiumEmployee": 120, "monthlyPremiumDependent": 300,
  "deductible": 1000, "outOfPocketMax": 4000, "companyContributionPercent": 80,
  "currency": "USD",
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}

// benefits_elections  (one per active employee; references real plans)
{
  "id": "elec-0031", "electionId": "elec-0031",
  "employeeId": "emp-0031", "employeeName": "Mia Brown",   // FK + derived
  "medicalPlanId": "plan-med-ppo",       // FK -> benefits_plans
  "dentalPlanId": "plan-den-std",
  "visionPlanId": "plan-vis-basic",
  "retirement401kPercent": 6, "employerMatchPercent": 4,
  "dependentsEnrolled": 1,
  "effectiveDate": "2026-01-01", "endDate": null, "status": "active",
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}
```
**Rule:** `employees.benefitsSnapshot` for an employee must match that employee's
active `benefits_elections` row exactly.

### 3.3 `payroll_runs` (PK `/id`)  + `pay_statements` (PK `/employeeId`)

```jsonc
// payroll_runs
{
  "id": "run-2026-08", "payRunId": "run-2026-08",
  "payGroup": "US-biweekly", "periodStart": "2026-08-01", "periodEnd": "2026-08-15",
  "payDate": "2026-08-20", "status": "processed",   // enum §5
  "employeeCount": 200, "grossTotal": 812340.55, "currency": "USD",
  "approvedById": "emp-0009",
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}

// pay_statements  (one per employee per run)
{
  "id": "pay-0777", "payStatementId": "pay-0777",
  "employeeId": "emp-0031", "payRunId": "run-2026-08",   // both FKs resolve
  "grossPay": 3461.54, "netPay": 2450.10, "currency": "USD",
  "lineItems": [
    { "type": "earning",   "code": "base",    "amount": 3461.54 },
    { "type": "tax",       "code": "federal", "amount": -620.00 },
    { "type": "deduction", "code": "401k",    "amount": -207.69 },
    { "type": "benefit",   "code": "medical", "amount": -60.00 }
  ],
  "ytdGross": 55384.64, "ytdTax": 9920.00,
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}
```
**Rule:** `grossPay ≈ employees.compensation.annualSalary / payPeriodsPerYear`.

### 3.4 `hr_tickets`  (PK `/employeeId`)

```jsonc
{
  "id": "tkt-0123", "ticketId": "tkt-0123",
  "employeeId": "emp-0031", "employeeName": "Mia Brown",   // FK MUST exist
  "category": "pto_leave",                 // enum §5
  "priority": "medium",                    // enum §5
  "status": "resolved",                    // enum §5
  "subject": "How many PTO days do I have left?",
  "description": "Employee asking about remaining PTO balance for 2026.",
  "assigneeId": "emp-0009",               // FK -> employees (HR staff)
  "policyReferenceId": "policy-pto",      // FK -> policies (nullable)
  "openedDate": "2026-07-18T10:00:00Z",
  "resolvedDate": "2026-07-18T15:00:00Z",
  "slaDueDate": "2026-07-21T10:00:00Z",
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}
```
**This is the container that had `emp-sam` orphans — every ticket now points at a
real `emp-####`.**

### 3.5 `onboarding_checklists` (PK `/employeeId`) + `offboarding_checklists` (PK `/employeeId`)

```jsonc
// onboarding_checklists  (renamed employee_id -> employeeId; real FK)
{
  "id": "onb-0009", "checklistId": "onb-0009",
  "employeeId": "emp-0198", "employeeName": "Areef Shaik",   // FK MUST exist
  "jobId": "job-0021", "departmentId": "dept-eng",
  "startDate": "2026-08-25", "status": "in_progress",        // enum §5
  "hrOwnerId": "emp-0009", "managerId": "emp-0006",
  "tasks": [
    { "key": "i9",             "label": "I-9 Verification",  "status": "pending", "dueDate": "2026-08-28" },
    { "key": "it_provisioning","label": "IT Provisioning",   "status": "pending", "dueDate": "2026-08-25" },
    { "key": "benefits_enroll","label": "Benefits Enrollment","status": "pending","dueDate": "2026-09-08" }
  ],
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}
```
Offboarding mirrors this with `separationType` (`voluntary`/`involuntary`),
`lastDay`, and revoke/return tasks.

### 3.6 `policies`  (PK `/policyId`)  — the ONE policy corpus

```jsonc
{
  "id": "policy-pto", "policyId": "policy-pto",
  "title": "Paid Time Off (PTO) Policy",
  "category": "leave",                     // enum §5
  "version": "2026.1", "effectiveDate": "2026-01-01", "jurisdiction": "US",
  "acknowledgmentRequired": false,
  "summary": "Full-time employees accrue 15–22 PTO days/year based on tenure.",
  "content": "Full-time employees accrue PTO by tenure: 15 days (<2 yrs), 18 days (2–5 yrs), 22 days (5+ yrs). ...",
  "sourceDocument": "HR-Handbook-2026.pdf, p.14",
  "embeddingId": "emb-policy-pto",        // for the Azure Search index sync
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}
```
**Rule:** the numbers in policy `content` must match the accrual rules in §3.1 and
any ticket `policyReferenceId` must point here. This becomes the single corpus the
HR Core `policy_search`, the Cosmos `policies` container, **and** the Azure Search
`company-policies` index are all populated from (same text, same numbers).

### 3.7 `documents` (PK `/documentId`) + `document_templates` (PK `/templateId`)
`assets` (PK `/employeeId`) + `asset_policies` (PK `/policyId`)

```jsonc
// documents
{
  "id": "doc-0050", "documentId": "doc-0050",
  "employeeId": "emp-0031",               // FK MUST exist (nullable for templates-only)
  "type": "offer_letter",                 // enum §5
  "templateId": "tmpl-offer",             // FK -> document_templates
  "status": "generated", "generatedDate": "2026-01-05", "verified": true,
  "blobUrl": "blob://generated-reports/doc-0050-offer-letter.pdf",
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}

// assets
{
  "id": "asset-0210", "assetId": "asset-0210",
  "employeeId": "emp-0031",               // FK MUST exist (null if unassigned/in-stock)
  "assetType": "laptop", "model": "MacBook Pro 14", "serialNumber": "C02X...",
  "assignedDate": "2026-01-06", "returnedDate": null, "status": "assigned",
  "company": "ClosedAI", "schemaVersion": 2, "createdAt": "...", "updatedAt": "..."
}
```

---

## 4. Referential integrity — the rules that make it all connect

These are validated after generation; a build with any violation is rejected.

### 4.1 The org tree (fixes orphaned execs + name-FKs + duplicates)
- Exactly **one** employee has `managerId: null` — the CEO (`emp-0001`).
- Every other employee's `managerId` is a real `emp-####` that exists in `employees`.
- The manager graph is a **tree** (no cycles), resolving from every employee up to
  the CEO in ≤ 5 hops → **max 5 layers**.
- Shape for ~200 people: CEO → ~8 function heads (level 6–7) → managers (level 5) →
  ICs (levels 1–4). Target manager span 5–9; flag/avoid managers with 1 report.
- `departments.leaderEmployeeId` is a real employee whose `departmentId` is that dept.
- **No duplicate persons:** `name` + `workEmail` is unique. `workEmail` is unique.
  `employeeId` is unique. (Kills the "Ishaan Shete ×N" problem.)

### 4.2 Cross-container FK rules
Every one of these must resolve to an existing `id` in the target container:

| Field | Lives in | Must exist in |
|-------|----------|---------------|
| `managerId`, `approverId`, `assigneeId`, `hrOwnerId`, `leaderEmployeeId`, `hiringManagerId`, `recruiterId`, `reviewerId`, `incumbentEmployeeId` | many | `employees` |
| `employeeId` | leave/benefits/pay/tickets/onboarding/assets/docs/reviews/goals | `employees` |
| `departmentId`, `parentDepartmentId` | employees, jobs, reqs | `departments` |
| `jobId` | employees, requisitions | `jobs` |
| `bandId` | employees.compensation | `compensation_bands` |
| `medicalPlanId`/`dentalPlanId`/`visionPlanId` | elections, snapshots | `benefits_plans` |
| `payRunId` | pay_statements | `payroll_runs` |
| `policyReferenceId` | tickets | `policies` |
| `requisitionId` | applications, offers | `job_requisitions` |
| `candidateId` | applications | `candidates` |
| `applicationId` | interviews, offers | `applications` |
| `templateId` | documents | `document_templates` |

### 4.3 Derived-field consistency
`name`, `managerName`, `departmentName`, `jobTitle`, `jobLevel`, `directReportCount`,
`headcount`, `tenureYears`, `compaRatio`, `ptoSnapshot`, `benefitsSnapshot`,
`leave_balances.availableDays`, and every `*Name` cache must be **recomputed from
its source of truth** by the generator, not hand-set. Validation recomputes them
and fails on mismatch.

### 4.4 Coverage rules (so the DB feels "complete")
- 100% of active employees: valid `managerId` (except CEO), one `benefits_elections`
  row + matching snapshot, one `leave_balances` row per leave type for 2026, ≥1
  `pay_statements` row in the latest `payroll_runs`, ≥1 assigned `asset`.
- ≥ 60 `hr_tickets` spread across categories, all referencing real employees.
- ~10–15 recent hires with `onboarding_checklists`; ~5 with `offboarding_checklists`.
- Talent pipeline (Tier 2): ~15 open `job_requisitions`, ~80 `candidates`, ~120
  `applications`, ~40 `interviews`, ~10 `offers` — all FK-consistent.

---

## 5. Canonical enums (use these exact string values)

```
employmentStatus:  active | on_leave | terminated
employmentType:    full_time | part_time | contract | intern
flsaStatus:        exempt | non_exempt
workMode:          onsite | hybrid | remote
payFrequency:      weekly | biweekly | semimonthly | monthly | annual
workAuth.status:   citizen | permanent_resident | visa
jobLevel:          1..8   (1-4 IC, 5 manager, 6 director/head, 7 VP/CxO, 8 CEO)
leaveType:         pto | sick | parental | fmla | bereavement | jury_duty | unpaid
leaveRequest.status: pending | approved | rejected | cancelled
benefits.planType: medical | dental | vision | retirement_401k | hsa | fsa | life
payroll.status:    draft | processing | processed | paid | cancelled
ticket.category:   pto_leave | benefits | payroll | onboarding | offboarding | policy | it_access | compensation | employee_relations | other
ticket.priority:   low | medium | high | urgent
ticket.status:     open | in_progress | waiting | resolved | closed
checklist.status:  not_started | in_progress | completed | overdue
task.status:       pending | in_progress | completed | blocked | na
policy.category:   leave | benefits | conduct | compensation | safety | security | remote_work | immigration | general
document.type:     offer_letter | i9 | nda | w4 | handbook_ack | emergency_contact | other
separationType:    voluntary | involuntary
requisition.status: draft | open | on_hold | filled | cancelled
application.stage:  applied | screening | phone_screen | onsite | offer | hired | rejected | withdrawn
offer.status:      draft | pending_approval | extended | accepted | declined | rescinded | expired
review.rating:     1 | 2 | 3 | 4 | 5   (1 below, 3 meets, 5 exceeds)
```

---

## 6. Tier 2 & 3 — Talent lifecycle + management (lighter schemas)

Full field lists follow the same conventions; abbreviated here for brevity.

- **`job_requisitions`** (PK `/requisitionId`): `title`, `jobId`, `departmentId`,
  `hiringManagerId`, `recruiterId`, `workLocationId`, `employmentType`, `headcount`,
  `status`, `openDate`, `targetFillDate`, `bandId`.
- **`candidates`** (PK `/id`): `name`, `email`, `phone`, `resumeUrl`, `source`,
  `talentPoolTags[]`.
- **`applications`** (PK `/requisitionId`): `candidateId`, `requisitionId`, `stage`,
  `status`, `appliedDate`, `dispositionReason`, `referrerEmployeeId`.
- **`interviews`** (PK `/id`): `applicationId`, `type`, `scheduledAt`,
  `interviewerIds[]`, `status`, `scores` (per-competency), `recommendation`.
- **`offers`** (PK `/id`): `applicationId`, `requisitionId`, `baseSalary`, `bonus`,
  `equity`, `startDate`, `status`, `expiryDate`, `approverIds[]`. On `accepted` →
  generator creates the corresponding `employees` + `onboarding_checklists` rows
  (the Candidate→Employee lifecycle).
- **`review_cycles`** (PK `/id`): `name`, `type`, `startDate`, `endDate`, `status`.
- **`performance_reviews`** (PK `/employeeId`): `cycleId`, `employeeId`, `reviewerId`,
  `overallRating`, `summary`, `status`.
- **`goals`** (PK `/employeeId`): `employeeId`, `cycleId`, `title`, `weight`,
  `progress`, `status`, `parentGoalId`.

**Analytics note:** attrition, headcount, spans/layers, comp-ratio distributions,
time-to-fill, engagement, etc. are all **computable** from the tiers above — do
not seed separate "metric snapshot" containers. Keep `reports`/`work_items`/
`integrations`/`schedules`/`timesheets` as-is only if something reads them;
otherwise defer them (see §7 mapping).

---

## 7. Current → target container mapping (what Claude Code should do to each)

| Current container | Action | Target |
|-------------------|--------|--------|
| `employees` | **Rebuild** to §2.1 (200 coherent people, real FKs, snapshots) | `employees` |
| — | **Add** | `departments` (§2.2) |
| `jobs` | **Upgrade** to §2.3 catalog | `jobs` |
| `compensation_bands` | Keep, conform to §2.4 | `compensation_bands` |
| `leave_requests` | Rebuild to §3.1, add `leave_balances` | `leave_requests`, `leave_balances` (new) |
| `benefits_plans` | Keep, conform §3.2 | `benefits_plans` |
| `benefits_elections` | Rebuild to §3.2, 1 per active emp | `benefits_elections` |
| `benefits_catalog` | Keep, conform | `benefits_catalog` |
| `payroll_runs` | Conform §3.3 | `payroll_runs` |
| — | **Add** | `pay_statements` (new; per-employee) |
| `payroll_cases` | Merge into `hr_tickets` (category=`payroll`) | `hr_tickets` |
| `hr_tickets` | Rebuild to §3.4, real FKs | `hr_tickets` |
| `onboarding_checklists` | Rebuild to §3.5 (`employeeId`, real FK) | `onboarding_checklists` |
| — | **Add** | `offboarding_checklists` (new) |
| `policies` | Rebuild to §3.6 as the one corpus | `policies` |
| `documents` | Conform §3.7, real `employeeId` | `documents` |
| `document_templates` | Keep, conform | `document_templates` |
| `assets` | Conform §3.7 | `assets` |
| `asset_policies` | Keep, conform | `asset_policies` |
| `applicants` | Split into `candidates` + `applications` (§6) | `candidates`, `applications` |
| — | **Add** | `job_requisitions`, `interviews`, `offers` (§6) |
| — | **Add** | `review_cycles`, `performance_reviews`, `goals` (§6) |
| `timesheets`, `schedules`, `reports`, `integrations`, `work_items` | **Defer** (keep container, don't reseed) unless a tool/skill demo needs it | same |

> Cosmos partition keys can't be altered in place. For any container whose PK
> changes (e.g. splitting `applicants`), Claude Code should **create the new
> container with the target PK, write into it, then delete the old one** — never
> assume an in-place PK change.

---

## 8. Execution plan (phased — one coherent build, validated at each gate)

**Phase A — Spine.** Generate `departments`, `jobs`, `compensation_bands`, then
`employees` (200) with a valid manager tree and salaries inside bands. Recompute
all derived fields. **Gate:** every `managerId` resolves; one root; ≤5 layers; no
dup emails; every salary in band.

**Phase B — Operational.** Generate `leave_requests`+`leave_balances`,
`benefits_plans`+`elections`, `payroll_runs`+`pay_statements`, `hr_tickets`,
`onboarding`/`offboarding`, `policies`, `documents`, `assets`. Fill
`employees.ptoSnapshot`/`benefitsSnapshot` from the ledgers. **Gate:** §4.4
coverage met; every child `employeeId` exists; snapshots match ledgers; policy
numbers match accrual rules.

**Phase C — Talent lifecycle.** `job_requisitions`, `candidates`, `applications`,
`interviews`, `offers`; wire accepted offers to the newest hires. **Gate:** all
ATS FKs resolve.

**Phase D — Talent management.** `review_cycles`, `performance_reviews`, `goals`.
**Gate:** all FKs resolve.

**Phase E — Validate & sync.** Run the full referential-integrity check (§4).
Re-sync the `policies` text into the Azure Search `company-policies` index so all
three policy surfaces agree. Run `count_documents` on every container and confirm
against expected counts.

---

## 9. Prompt to hand to Claude Code

> You are rebuilding the Azure Cosmos DB `closedai-db` for the ClosedAI HR agent.
> The complete target specification is in `docs/database_redesign_plan.md` — read
> it fully and treat it as binding. Connection settings are in `.env`
> (`COSMOS_URI`, `COSMOS_KEY`, `COSMOS_DATABASE=closedai-db`).
>
> Write an idempotent Python seed/migration script (using `azure-cosmos`) under
> `HRAgent_Main/scripts/seed_database.py` that:
> 1. Implements the global conventions in §1 (typed IDs, camelCase, FKs-as-IDs
>    with derived `*Name` caches, standard metadata, enums from §5).
> 2. Builds the data in the phased order of §8 (A→E), following the container
>    schemas in §2, §3, §6 and the current→target mapping in §7. For any
>    container whose partition key changes, create-new-then-delete-old per §7.
> 3. Generates ONE coherent ~200-person ClosedAI org with a valid manager tree
>    (§4.1), all salaries inside their comp bands, and 100% of the coverage rules
>    in §4.4.
> 4. Recomputes ALL derived fields from their sources (§4.3) — never hand-set them.
> 5. Ends with a `--validate` mode that checks every referential-integrity rule in
>    §4 and every enum in §5, printing a per-container pass/fail report and a
>    document count per container. The build fails loudly on any violation.
> 6. Re-syncs the reconciled `policies` text (§3.6) into the Azure AI Search
>    `company-policies` index so all policy surfaces report the same numbers.
>
> Make it re-runnable (upsert by `id`, delete-orphans pass). Print a summary table
> at the end. Do not invent field names or numbers that contradict the spec; if
> the spec is ambiguous, pick the most consistent option and note it in a comment.

---

## 10. Decisions I made (state-and-proceed; override any of these)

1. **Canonical headcount = ~200**, single company `ClosedAI`, one clean org tree
   (matches our org-design/spans-layers use cases). Generator is parameterized so
   this can scale to 500 with identical rules. *(Current DB has ~517 inconsistent
   docs; a clean 200 beats a messy 517. Say the word to target 500 instead.)*
2. **PTO accrual reconciled to 15/18/22 by tenure** (aligns with the live
   `policies` container's "15" base). All other surfaces conform to this.
3. **Normalized ledgers are source of truth; employees carry derived snapshots**
   so the existing `pto_balance`/`benefits_lookup` tools keep working with no code
   change. Alternative is a tool code change to join ledgers — deferred.
4. **Defer** `timesheets`/`schedules`/`reports`/`integrations`/`work_items`
   reseeding (nothing queries them today); the spine + operational + talent tiers
   cover the real skill/tool query surface.
5. **One policy corpus** feeds HR Core, the Cosmos `policies` container, and Azure
   Search — same text, same numbers.
