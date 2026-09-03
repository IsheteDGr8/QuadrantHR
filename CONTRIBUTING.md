# Monorepo git safety

This repository (QuadrantHR) is the ONLY git remote we push to.

- **origin** → https://github.com/IsheteDGr8/QuadrantHR.git
- Ticket-Genie application code is at the **repo root** (cloned from
  Azure-Rangers/Ticket-Genie as a starting base). Do **not** push back to
  `Azure-Rangers/Ticket-Genie` or any other team's remote.
- Sibling folders (`EmployeeDirectory/`, `ResumeScreening/`, etc.) are
  reference projects for later integration. Never re-add a nested `.git`
  inside those folders.

Architecture notes: [plan.md](plan.md). Active UI/API base: Ticket-Genie at root.
