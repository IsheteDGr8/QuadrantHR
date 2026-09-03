# Ticket-Genie
This project is an intelligent ticketing platform designed to streamline workplace support by automating routine employee inquiries and administrative workflows.

## Production Architecture (Dual Azure Web Apps)

Ticket-Genie enforces a strict security boundary by separating the frontend UI and backend REST API into two distinct Azure Linux Web Apps:

```text
                                 ┌──────────────────────────────────────────────┐
                                 │   webapp-prod-frontend-ticketgenie           │
  User Browser ────────────────► │   - Nginx UI (Port 80)                       │
                                 │   - HTML / CSS / JS Portal Assets            │
                                 └──────────────────────┬───────────────────────┘
                                                        │ Reverse Proxy /api/
                                                        ▼
                                 ┌──────────────────────────────────────────────┐
                                 │   webapp-prod-backend-ticketgenie            │
                                 │   - FastAPI REST API (Port 8000)             │
                                 │   - Holds DB Connection & AI Secrets         │
                                 └──────────────────────┬───────────────────────┘
                                                        │ SQL Port 1433
                                                        ▼
                                           ┌─────────────────────────┐
                                           │  Azure SQL Database     │
                                           └─────────────────────────┘
```

- **Frontend App**: `webapp-prod-frontend-ticketgenie` (Nginx UI on port 80). Serves static HTML/CSS/JS portals and reverse-proxies `/api/` traffic to the backend.
- **Backend App**: `webapp-prod-backend-ticketgenie` (FastAPI on port 8000). Serves API endpoints and securely accesses Azure SQL Database, OpenAI agents, and Key Vault.

---

## Monitoring & Troubleshooting Logs

### 1. Tail Live Container Logs (Azure CLI)
To view real-time `stdout`/`stderr` startup logs for both Web Apps:

```bash
# Frontend Container Logs (Nginx)
az webapp log tail --resource-group Azure_Rangers --name webapp-prod-frontend-ticketgenie

# Backend Container Logs (FastAPI / Uvicorn)
az webapp log tail --resource-group Azure_Rangers --name webapp-prod-backend-ticketgenie
```

To download historical Docker startup & container failure logs:
```bash
az webapp log download --resource-group Azure_Rangers --name webapp-prod-frontend-ticketgenie --log-file frontend_logs.zip
```

### 2. Azure Portal & Kudu Diagnostic URLs
- **Live Stream Logs:** Azure Portal > Web App (`webapp-prod-frontend-ticketgenie` / `webapp-prod-backend-ticketgenie`) > **Log stream**
- **Deployment Center Logs:** Web App > **Deployment Center** > **Logs**
- **Direct Docker Kudu Log Endpoint:** `https://webapp-prod-frontend-ticketgenie.scm.azurewebsites.net/api/logs/docker`

### 3. How to View Request Traces in Azure Portal

1. Go to **Azure Portal** $\rightarrow$ **Application Insights** (`appi-ticketgenie-westus-prod`).
2. Under **Investigate** on the left menu, click **Transaction Search**.
3. Click **Search** and click any request (e.g. `POST /api/tickets`) to view the full trace waterfall:

```text
[Browser Click]             Submit Ticket (Front-End)
 └── [Browser Dependency]   fetch POST /api/tickets
       └── [Server Request] POST /api/tickets (FastAPI Backend)
             └── [Span]     ticket_service.process_new_ticket
                   ├── [Span] orchestrator.classify_ticket
                   │     ├── [Span] priority_agent.classify_priority
                   │     └── [Span] category_agent.classify_category
                   └── [Span] database.create_ticket
                         └── [Dependency] SQL: INSERT INTO tickets
```

---

## Environment & Secrets Setup

Ticket-Genie uses a `.env` file for managing application configuration and secrets locally.

### Fetching Remote Secrets from Azure Key Vault

To securely fetch environment secrets locally from Azure Key Vault into a `.env` file (works cross-platform on **Windows**, **macOS**, and **Linux**):

```bash
# 1. Log in to Azure
az login

# 2. Run the secret fetch script to populate/update your local .env file
python fetch_secrets.py
```

#### Custom Vault Options:
```bash
# Fetch from specific Key Vault names
python fetch_secrets.py --vault-names kv-app-prod-12345 group-1

# Fetch from specific Key Vault URLs
python fetch_secrets.py --vault-urls https://kv-app-prod-12345.vault.azure.net/

# Output to custom env file location
python fetch_secrets.py --env-file .env.local
```

Both the **Streamlit Frontend** (`app/main.py`) and **FastAPI Backend** (`backend/main.py`) automatically load configuration from the `.env` file at startup using `python-dotenv`.

---

## How to Run

### Option 1: Run with Docker Compose (Recommended)

Launch both the Nginx Frontend UI and FastAPI Backend API together in a single command:

```bash
# Build and start both backend and frontend containers
docker compose up --build -d
```

- **Frontend Application UI:** [http://localhost:8080](http://localhost:8080)
- **FastAPI Backend Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **FastAPI Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

### Synthetic Analytics Data (Local/Demo)

The local Docker Compose setup enables `ENABLE_SYNTHETIC_ANALYTICS=true` so the Department Analytics dashboard has meaningful demo data. On startup, the backend creates 360 deterministic synthetic tickets only when no synthetic tickets already exist. Real tickets are never replaced or deleted.

For a teammate setting up the project:

```bash
git pull origin dev
docker compose up -d --build
```

To confirm whether the data was created or already existed:

```bash
docker compose logs backend
```

Look for a `Synthetic analytics data` message with a status such as `seeded` or `already_seeded`.

To regenerate the demo dataset manually:

```bash
docker compose exec -T backend python -c "from database.connection import SessionLocal; from services.synthetic_ticket_service import seed_synthetic_tickets; db=SessionLocal(); print(seed_synthetic_tickets(db, count=360)); db.close()"
```

For native development outside Docker, the equivalent command is:

```bash
python scripts/seed_synthetic_tickets.py --count 360
```

Synthetic tickets are marked with `is_synthetic=true`. Regeneration replaces only those records and preserves real company tickets. Disable automatic demo data outside local/demo environments by setting:

```env
ENABLE_SYNTHETIC_ANALYTICS=false
```

> **Warning:** `docker compose down -v` deletes the entire local database volume, including both synthetic data and any local real tickets. The synthetic dataset will be recreated on the next startup while the feature is enabled.

To stop the containers:
```bash
docker compose down
```

---

### Option 2: Run Containers Manually with Docker

```bash
# 1. Build backend and frontend images
docker build --target backend -t ticketgenie-backend .
docker build --target frontend -t ticketgenie-frontend .

# 2. Create Docker network
docker network create ticketgenie-net

# 3. Run Backend container on Port 8000
docker run -d --name backend --network ticketgenie-net -p 8000:8000 ticketgenie-backend

# 4. Run Frontend container on Port 8080
docker run -d --name frontend --network ticketgenie-net -p 8080:80 ticketgenie-frontend
```

---

### Option 3: Run Natively

For local development without Docker:

```bash
# Install core, backend, and dev dependencies
pip install -e '.[backend,dev]'

# Launch Uvicorn dev server at http://localhost:8000
uvicorn backend.main:app --reload --port 8000
```

---

### Running Tests and Quality Checks

```bash
# Run pytest test suite (includes app, backend, secret fetcher, and openapi monitoring tests)
pytest

# Run Ruff linter and formatting check
ruff check .
ruff format --check .
```

### Updating OpenAPI Spec & Monitoring Artifacts

When modifying API endpoints in `backend/`, re-generate and commit the updated specs and monitoring rules:

```bash
python scripts/export_openapi.py
python scripts/generate_openapi_monitoring.py
git add openapi/ artifacts/ terraform/openapi_alerts.tf
```

---

## Branching Strategy

Use short-lived branches for active work:

- `feature/<short-desc>` or `feat/<issue-id>` for new capabilities.
- `fix/<issue-id>` or `bugfix/<short-desc>` for non-urgent bug fixes.
- `hotfix/<issue-id>` for urgent production fixes.

Keep `main` reserved for production-ready changes. Pull requests should include testing steps, linked issues, and any relevant safety notes using the PR template in `.github/PULL_REQUEST_TEMPLATE.md`.

## Directory Structure

```text
Ticket-Genie/
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       ├── pr-checks.yml       # Ruff linting, pytest, OpenAPI drift check, & Docker smoke testing
│       └── deploy-prod.yml     # ACR build/push & Azure handoff
├── artifacts/                  # Generated Azure Monitor Artifacts
│   ├── openapi_kql_queries.kql # Pre-built Application Insights KQL queries
│   └── openapi_workbook.json   # Azure Application Insights Workbook dashboard JSON
├── backend/                    # FastAPI Backend Service
│   ├── main.py                 # FastAPI application entrypoint
│   ├── telemetry.py            # Azure Monitor OpenTelemetry setup
│   ├── api/                    # API route controllers (tickets, genie)
│   ├── models/                 # Pydantic data schemas
│   ├── services/               # Business logic & AI classification services
│   ├── database/               # Database connection & CRUD handlers
│   └── requirements.txt        # Backend dependencies (-e .[backend])
├── frontend/                   # Nginx HTML/CSS/JS Frontend UI
│   ├── index.html              # Main dashboard view
│   ├── css/                    # Custom stylesheets
│   ├── js/                     # Client JavaScript API integration
│   └── pages/                  # Portal pages (HR, IT, Knowledge Base, My Tickets)
├── openapi/                    # Exported OpenAPI 3.0 Contract Specifications
│   ├── openapi.json
│   └── openapi.yaml
├── scripts/
│   ├── export_openapi.py       # OpenAPI schema exporter script
│   ├── fetch_secrets.py        # Entrypoint for fetching Key Vault secrets
│   └── generate_openapi_monitoring.py # OpenAPI-driven Azure Monitor generator script
├── terraform/                  # Infrastructure definitions for Azure
│   ├── main.tf
│   ├── monitoring.tf           # Log Analytics Workspace & App Insights definitions
│   ├── openapi_alerts.tf       # Auto-generated Azure Monitor Metric Alerts
│   ├── outputs.tf
│   └── variables.tf
├── tests/
│   ├── test_backend_api.py     # FastAPI endpoint tests
│   ├── test_fetch_secrets.py   # Secret fetcher tests
│   └── test_openapi_monitoring.py # Telemetry & OpenAPI monitoring generator tests
├── .dockerignore
├── .gitignore
├── Dockerfile                  # Multi-stage Docker build file (backend & Nginx frontend)
├── docker-compose.yml          # Multi-container orchestration config
├── nginx.conf                  # Nginx static server & /api/ reverse proxy config
├── fetch_secrets.py            # Cross-platform Azure Key Vault to .env fetcher script
├── pyproject.toml              # Central config for dependencies, Ruff, pytest
└── README.md
```

The repository follows a monorepo structure with an Nginx HTML/CSS/JS frontend under `frontend/` and a FastAPI REST API backend service under `backend/`.
