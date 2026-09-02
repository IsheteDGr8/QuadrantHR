# QuadrantHR

Unified HR Automation & Intelligence Portal monorepo. Legacy hackathon apps live side-by-side as services; a shared FastAPI gateway, MCP tool layer, and portal shell come next.

## Services (Phase 0)

| Module | Folder | Host port | Notes |
|--------|--------|-----------|--------|
| Employee Directory (Mel) | `EmployeeDirectory/` | **8101** | FastAPI |
| Resume Screening (ResumeIQ) | `ResumeScreening/` | **8102** | FastAPI, mock Azure |
| Helpdesk / Leave / Onboarding | `Ticket-Genie/` | **8103** | FastAPI |
| Training & Compliance | `TrainingPortal/` | **8104** | Local `devserver.py` |
| AI HR Copilot (Vera) | `ClosedAI/` | **8105** | Agent server |
| AI Policy Generator | `Bug Busters/` | **8106** | Compose profile `full` |

Incoming: a dedicated **Employee FAQ Chatbot** codebase (and any refined Policy Generator tree) will be added as additional services when available. Ticket-Genie’s RAG chatbot covers FAQ for now.

Excluded from product scope: Career Advisor, HR Analytics Dashboard.

## Quick start

```bash
cp .env.example .env
docker compose up --build -d
docker compose --profile full up --build -d   # also start policy-generator
```

All API containers join the `quadranthr-net` Docker network so a future gateway can reach them by service name.

Frontends are not in compose yet — run each project’s Vite/Next UI locally against the mapped ports above.

## Architecture direction

Keep each backend intact → wrap with gateway + MCP → ship one React portal shell that absorbs modules domain-by-domain (strangler fig). Do not big-bang merge the five UIs.
