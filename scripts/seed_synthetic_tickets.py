"""Seed replaceable synthetic tickets for the department analytics demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from database.connection import SessionLocal, init_db_schema  # noqa: E402
from services.synthetic_ticket_service import seed_synthetic_tickets  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=360)
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()

    init_db_schema()
    with SessionLocal() as db:
        result = seed_synthetic_tickets(
            db,
            count=args.count,
            replace=True,
            seed=args.seed,
        )
    print(result)


if __name__ == "__main__":
    main()
