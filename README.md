# QuadrantHR

Unified modular monolith for the HR portal — see [plan.md](plan.md).

Hackathon folders (`EmployeeDirectory/`, `Ticket-Genie/`, etc.) are **reference
codebases only**. Runtime code lives in `backend/` + `portal/`.

## Architecture (Week 1+)

| Layer | Local | Production target |
|-------|--------|-------------------|
| API | FastAPI modular monolith `:8080` | Azure Container Apps |
| Relational | PostgreSQL `:5432` | Azure SQL |
| Blobs | Azurite `:10000` | Azure Blob Storage |
| Jobs/cache | Redis `:6379` | Azure Cache / workers |
| Vectors / chat | schema in `infra/cosmos-schema.md` | Azure Cosmos DB |
| UI | React/Vite `portal/` `:5170` | Static Web App / CDN |

## Quick start

```bash
# Data plane + unified backend
docker compose up --build -d

# UI
cd portal && npm install && npm run dev
```

- API docs: http://127.0.0.1:8080/docs  
- Portal: http://localhost:5170  
- Seed login: `hr.admin@quadranthr.local` / `changeme123`

Legacy microservice compose (optional): `docker compose -f docker-compose.legacy.yml up`

## Modules (`backend/app/modules/`)

| Module | Status |
|--------|--------|
| auth | JWT local (Entra in Week 4) |
| directory | Employee search CRUD scaffold |
| ticketing | Tickets + leave→ticket link |
| ai_agent | Mock LLM copilot |
| hiring / training / policies | Status stubs for Weeks 2–3 |

## Git safety

Push **only** to https://github.com/IsheteDGr8/QuadrantHR. Never re-add `.git`
inside hackathon folders. See [CONTRIBUTING.md](CONTRIBUTING.md).
