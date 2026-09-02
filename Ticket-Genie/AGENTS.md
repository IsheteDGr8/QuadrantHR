# Workspace Guidelines & Rules

- **Architectural & Organizational Decisions**: Do not account for coding time when making architectural decisions or organizational changes. Focus purely on clean design, long-term scalability, maintainability, and correctness.
- **Task Completion Verification & Output**: When completing a task, always present concrete verification results—such as UI screenshots, API response payloads, command outputs, or test results—demonstrating that the work is finished and verified.
- **Zero-Trust Authentication & No Fallback Defaults**: Never use silent fallback dictionaries or hardcode mock user credentials/OIDs in authentication verifiers (`jwt_verifier.py`). Missing or invalid `Authorization: Bearer <token>` headers on protected backend routes MUST strictly return `401 Unauthorized`.
- **Bearer Token Identity Scoping**: The Bearer JWT Token (`verify_azure_user`) is the single source of truth for user identity (`oid`, `email`, `role`). Never rely on client-supplied `requester_id` or `user_id` query parameters for non-admin user requests.
- **Dynamic RBAC & No Hardcoded OIDs**: Never hardcode specific GUIDs/OIDs (`if oid == "..."`) in source code logic.
- **Docker Container Verification & Rebuilds**: Whenever changes are made to the codebase or configuration, rerun `docker compose up -d --build` (or `docker-compose`) to ensure the updated code is built and deployed in the running Docker containers.




