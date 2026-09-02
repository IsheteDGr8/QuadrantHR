# QuadrantHR Portal

Unified React shell for the seven in-scope HR modules. Lives only in this monorepo — it does **not** push to team GitHub repos.

## Run

```bash
# Terminal A — APIs (from repo root)
docker compose up -d employee-directory

# Terminal B — portal
cd portal
npm install
npm run dev
```

Open http://localhost:5170

Directory calls Mel via Vite proxy `/api/directory` → `http://127.0.0.1:8101`.

Demo login (Mel AUTH_MODE=dev): `naomi.lewis@example.com` / `orghub2026`
