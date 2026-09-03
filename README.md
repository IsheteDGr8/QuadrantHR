# QuadrantHR

**Ticket-Genie is the primary HR portal / dashboard base** for this monorepo.
Its application code lives at the **repository root** (not under a nested
`Ticket-Genie/` folder). Other hackathon projects remain as sibling folders for
later feature harvest.

## Run the portal (Ticket-Genie)

```bash
# Requires Docker Desktop running
cp .env.example .env   # or use the committed local template values in .env (gitignored)
docker compose up --build -d
```

| Surface | URL |
|---------|-----|
| Frontend (Nginx UI) | http://localhost:8080 |
| Backend API / docs | http://localhost:8000/docs |

Upstream project docs: [README.ticket-genie.md](README.ticket-genie.md)  
Source template: https://github.com/Azure-Rangers/Ticket-Genie  

## Other projects (reference / later integration)

| Folder | Role |
|--------|------|
| `EmployeeDirectory/` | Directory / Mel |
| `ResumeScreening/` | Hiring / ResumeIQ |
| `TrainingPortal/` | Training & compliance |
| `ClosedAI/` | AI HR Copilot (Vera) |
| `Bug Busters/` | Policy generator |
| `Decacore-Employee-FAQ-Chatbot/` | FAQ chatbot |
| `_archive/week1-monolith/` | Earlier unified-monolith scaffold (not the active UI) |

## Git safety

- Push **only** to https://github.com/IsheteDGr8/QuadrantHR
- Do **not** push this tree to `Azure-Rangers/Ticket-Genie` or other team remotes
- Nested `.git` folders inside module directories must stay deleted
- See [CONTRIBUTING.md](CONTRIBUTING.md) and [plan.md](plan.md)
