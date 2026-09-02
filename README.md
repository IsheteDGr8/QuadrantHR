# QuadrantHR

Unified HR Automation & Intelligence Portal monorepo.

Of the original 11 hackathon concepts, 9 were built. Two of those nine are out of
scope for this portal, leaving **7 modules** — all present in this repo.

## In-scope modules (7)

| Module | Folder | Host port |
|--------|--------|-----------|
| Employee Directory | `EmployeeDirectory/` | **8101** |
| Resume Screening | `ResumeScreening/` | **8102** |
| Intelligent Helpdesk (+ leave / onboarding flows) | `Ticket-Genie/` | **8103** |
| Training & Compliance | `TrainingPortal/` | **8104** |
| AI HR Copilot | `ClosedAI/` | **8105** |
| AI Policy Generator | `Bug Busters/` | **8106** |
| Employee FAQ Chatbot | `Decacore-Employee-FAQ-Chatbot/` | **8107** |

Out of product scope: Career Advisor, HR Analytics Dashboard (and any other of the nine you intentionally skip as standalone apps).

## Quick start

```bash
cp .env.example .env
docker compose up --build -d
cd portal && npm install && npm run dev   # http://localhost:5170
```

All API containers join `quadranthr-net` so a future gateway / MCP layer can reach them by service name.

The **portal** shell (`portal/`) is the unified UI. Directory is live first; other modules are stubs until wired. Team app folders are vendored snapshots — see [CONTRIBUTING.md](CONTRIBUTING.md) (push only to QuadrantHR, never to other teams’ remotes).

## Architecture direction

Keep each backend intact → FastAPI gateway + MCP tools → one React portal shell that absorbs modules domain-by-domain (strangler fig).
