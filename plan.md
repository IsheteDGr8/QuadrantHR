### System Architecture: The Unified Modular Monolith

For a strict 4-week timeline, orchestrating seven distinct microservice repos in production will introduce severe overhead in cross-service authentication, distributed state management, and network latency. The most resilient enterprise architecture is a **Unified Modular Monolith** backed by a shared multi-model data layer.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                 PRESENTATION LAYER (Unified React / Vite)               │
│     [Directory] [Onboarding/Leaves] [Tickets] [Hiring] [Training] [AI]  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTPS / REST / WebSockets
┌────────────────────────────────────▼────────────────────────────────────┐
│              CORE APPLICATION LAYER (FastAPI Modular Monolith)          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │ Auth & RBAC  │ │  Directory   │ │  Helpdesk &  │ │  Hiring & ATS  │  │
│  │   Service    │ │   Service    │ │    Leaves    │ │    Service     │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └───────┬────────┘  │
│  ┌──────┴───────┐ ┌──────┴───────┐ ┌──────┴───────┐ ┌───────┴────────┐  │
│  │  Training &  │ │  AI Policy   │ │  Enterprise  │ │ Background Jobs│  │
│  │  Compliance  │ │  Generator   │ │  AI Copilot  │ │ (Celery/Redis) │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────────┘  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                       UNIFIED AZURE DATA TIER                           │
│  ┌───────────────────────┐ ┌────────────────────┐ ┌──────────────────┐  │
│  │       Azure SQL       │ │  Azure Cosmos DB   │ │Azure Blob Storage│  │
│  │  (Relational Records) │ │  (NoSQL & Vectors) │ │ (Files & Media)  │  │
│  └───────────────────────┘ └────────────────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

```

The application runs as a single FastAPI service internally organized by bounded domains (`/app/modules/directory`, `/app/modules/tickets`, etc.). The existing hackathon repositories are treated purely as **reference codebases**: you harvest their underlying business logic, utility scripts, and schemas, leaving their separate wrappers and individual servers behind.

---



### Data Storage Strategy

No single database efficiently handles relational HR hierarchies, semi-structured conversational threads, and raw resume files. A tri-engine architecture cleanly segments these workloads:


| Storage Engine         | Data Domain            | Data Entities Stored            | Technical Justification |
| ---------------------- | ---------------------- | ------------------------------- | ----------------------- |
| **Azure SQL Database** | **Relational HR Core** | • Employee Profiles & Org Chart |                         |


  
• Leave Requests & Balances  


  
• Helpdesk Tickets & Statuses  


  
• Role-Based Access Control (RBAC)  


  
• Audit Logs & Compliance Records | Enforces strict ACID compliance, relational integrity (foreign keys between employees, managers, and tickets), and complex SQL joins for HR operations. |
| **Azure Cosmos DB** *(NoSQL / Vector)* | **Dynamic & Unstructured Data** | • AI Assistant Chat Sessions & Memory  


  
• Vector Embeddings (Policies, FAQs)  


  
• Dynamic Training Quizzes & Results  


  
• Flexible Application Questionnaires | Handles schema-less JSON payloads, rapid reads/writes for conversational context, and fast cosine-similarity searches for internal knowledge retrieval. |
| **Azure Blob Storage** | **Unstructured Media & Documents** | • Resumes (PDF, DOCX) & Portfolios  


  
• Onboarding Identity & Tax Docs  


  
• Uploaded Company Policies & SOPs  


  
• Training Manuals & Profile Pictures | Cost-efficient, high-durability object storage. Database models store direct, secure SAS (Shared Access Signature) URIs referencing these blobs. |

---



### Domain Decomposition & Code Migration

Each hackathon concept maps to an internal module within the core application repository:

```text
unified-hr-portal/
├── backend/
│   ├── app/
│   │   ├── core/              # Config, security, DB connections
│   │   ├── models/            # SQLAlchemy (SQL) & Pydantic schemas
│   │   ├── modules/
│   │   │   ├── auth/          # Entra ID / Local JWT authentication
│   │   │   ├── directory/     # Extracted from EmployeeDirectory (Mel)
│   │   │   ├── ticketing/     # Extracted from Ticket-Genie (Leave + Tickets)
│   │   │   ├── hiring/        # Extracted from ResumeScreening (ResumeIQ)
│   │   │   ├── training/      # Extracted from TrainingPortal (Quizrant)
│   │   │   ├── policies/      # Extracted from Bug Busters
│   │   │   └── ai_agent/      # Extracted from ClosedAI (Vera) & DecaCore
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                  # Unified React + Tailwind UI shell
├── docker-compose.yml         # Local dev environment
└── infra/                     # Terraform / Bicep for Azure deployment

```

- **Directory Module**: Migrates Mel’s SQLAlchemy models into Azure SQL. Smart search combines relational filters (department, title) with full-text search.
- **Ticketing & Leave Module**: Re-implements Ticket-Genie’s schema inside Azure SQL. Leave requests automatically generate a linked ticket for HR tracking.
- **Hiring & Screening Module**: Ingests resume files into Azure Blob Storage, triggers text extraction, and stores candidate scores and metadata in Azure SQL.
- **Training & Compliance Module**: Serves module content from Blob storage while tracking completion percentages and assessment scores in Azure SQL and Cosmos DB.
- **AI Agent & FAQ Module**: Absorbs DecaCore’s RAG knowledge retrieval and ClosedAI’s tool-calling logic. The agent is exposed as an endpoint that executes Python functions directly within the backend rather than making remote HTTP calls to separate containers.

---



### 4-Week End-to-End Implementation Roadmap

```
Week 1: Infrastructure, DB Schemas & Scaffolding
├── Set up local emulation (Docker: PostgreSQL, Azurite, Redis)
├── Establish Unified Backend repo and React shell
└── Design & execute unified DB migrations (SQLAlchemy / Alembic)

Week 2: Core Operational HR Modules
├── Implement Directory, Profiles, and Org Tree
├── Build Leave Tracking & Ticket-Genie Helpdesk workflows
└── Wire Unified Frontend navigation and data-fetching hooks

Week 3: AI Intelligence, Documents & Compliance
├── Ingest Company Policies into Blob & index into Cosmos DB (RAG)
├── Port Resume Screening pipeline (Blob upload + parsing logic)
└── Integrate AI Copilot endpoint with internal module tool calls

Week 4: Cloud Provisioning, Security & Final Deployment
├── Deploy Azure SQL, Cosmos DB, and Blob Storage
├── Containerize frontend/backend to Azure Container Apps
└── Wire Azure Entra ID and execute end-to-end integration tests

```



#### Week 1: Foundation & Data Layer Scaffolding

- **DevOps (Ishaan)**: Build a local development environment using Docker Compose with PostgreSQL (local substitute for Azure SQL), Azurite (local emulator for Azure Blob Storage), and Redis. Establish the monorepo CI pipeline with GitHub Actions.
- **Backend (Saketh)**: Initialize the single FastAPI project. Define the unified SQLAlchemy models for employees, tickets, leaves, and roles. Configure Alembic migrations.
- **Frontend (Manvitha)**: Scaffold the React/Vite portal shell with Tailwind CSS, unified navigation, authentication wrappers, and shared state management.
- **AI / Data (Harshita)**: Design the data schema for vector storage in Cosmos DB. Set up mock LLM interfaces and local embedding models so the team can build without waiting on active cloud API keys.



#### Week 2: Core Operational Services (Directory, Leaves, Ticketing)

- **DevOps (Ishaan)**: Configure Azurite file-upload pipelines for employee profile images and documents. Prepare containerization scripts (`Dockerfile`) for the unified backend.
- **Backend (Saketh)**: Implement the business logic for the Directory and Ticket-Genie modules. Build transactional endpoints for submitting leave requests and ticket escalation rules.
- **Frontend (Manvitha)**: Build out the Employee Directory views, search filters, and the Helpdesk/Leave management dashboard components.
- **AI / Data (Harshita)**: Harvest the Quizrant logic to build training module endpoints and evaluation schemas. Set up background task workers (Celery/Redis) for asynchronous processing.



#### Week 3: Document Workflows & AI Integration

- **DevOps (Ishaan)**: Implement secure SAS token generation for direct-to-blob browser uploads. Write infrastructure-as-code (Terraform or Azure Bicep) for Azure Container Apps, Azure SQL, and Cosmos DB.
- **Backend (Saketh)**: Implement the Policy Generator logic (Bug Busters) and integrate resume ingestion endpoints (ResumeIQ) to parse files saved in Blob storage.
- **Frontend (Manvitha)**: Design the HR Copilot slide-out interface, the resume upload/candidate evaluation dashboard, and training module views.
- **AI / Data (Harshita)**: Implement the RAG pipeline over uploaded company documents using Cosmos DB vector search. Bind internal service tools (e.g., `get_leave_balance()`, `lookup_employee()`) to the Copilot orchestration engine.



#### Week 4: Cloud Provisioning, Hardening & Production Launch

- **DevOps (Ishaan)**: Provision the Azure resources upon subscription activation. Set up the production CI/CD deployment to Azure Container Apps. Secure environment secrets in Azure Key Vault.
- **Backend (Saketh)**: Switch database connection strings from local emulators to live Azure SQL and Cosmos DB instances. Enforce role-based access control (RBAC) across all routes.
- **Frontend (Manvitha)**: Connect the frontend build to the live Azure API domain, handle edge-case loading states, and run cross-browser accessibility and UI polish.
- **AI / Data (Harshita)**: Configure production Azure OpenAI / AI endpoints with production API keys. Perform latency optimization and tuning on vector retrieval and model prompts.
- **Team Joint Effort**: Execute comprehensive integration testing across the complete lifecycle: an employee signs in, searches the directory, requests leave, submits a helpdesk ticket, takes a compliance quiz, and queries the AI assistant.

---



### Local-to-Cloud Parity Strategy

To ensure uninterrupted progress while waiting for Azure subscriptions and API keys:

1. **Relational Layer**: Use a local PostgreSQL container. SQLAlchemy abstracts the dialect differences, making the transition to Azure SQL seamless via connection string updates.
2. **Blob Storage**: Run **Azurite** via Docker Compose. The official Azure Storage SDK communicates with Azurite locally using standard storage endpoints and switches to the live cloud URL upon deployment.
3. **LLMs & Embeddings**: Wrap AI interactions behind an abstract base class (`LLMProvider`). Use a local mock provider or a local Ollama instance for initial integration; swap in Azure OpenAI endpoints once API keys are provisioned.

