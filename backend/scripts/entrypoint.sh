#!/bin/sh
set -e
echo "Waiting for Postgres..."
python - <<'PY'
import os, time
import psycopg
url = os.environ.get("DATABASE_URL", "")
dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
for i in range(60):
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute("SELECT 1")
        print("Postgres is ready")
        break
    except Exception as e:
        print(f"  retry {i+1}: {e}")
        time.sleep(1)
else:
    raise SystemExit("Postgres did not become ready")
PY

alembic upgrade head
PYTHONPATH=/app python scripts/seed.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
