"""SQLite backing store for the demo login fallback.

This is intentionally the ONLY SQL database in the project — every other
feature persists to Azure Blob Storage via storage_service.py. A single
`users` lookup table doesn't need a document store; SQLite keeps this
isolated, zero-config, and easy to turn into an ER diagram (one table,
explicit columns, no ORM layer to abstract the schema away).

Kept as its own module (not folded into storage_service.py or main.py)
so this whole flow can be deleted in one piece once real Entra login is
confirmed working and the fallback is no longer needed.
"""

import sqlite3
import tempfile
from pathlib import Path

# Local/ephemeral disk, not next to the source file — Azure App Service
# Linux persists /home (including the app's own code directory) on Azure
# Files, an SMB-backed network share that doesn't support the POSIX file
# locking SQLite needs for commits. Writes there can report success
# without becoming visible to the next connection (a fresh one is opened
# per request — see get_connection() below), which is exactly what was
# happening: init_demo_db()'s seed ran without error on every startup,
# but every /demo-login lookup still 404'd. tempfile.gettempdir() is
# real local disk on both Linux App Service (/tmp) and dev machines, so
# this fixes prod without needing any new app setting.
DB_PATH = Path(tempfile.gettempdir()) / "demo_login.db"

# role is deliberately a free-text column (not a foreign-keyed roles
# table) - there are exactly four fixed values app-wide (see
# Frontend/src/roleConfig.js) and a second table for four static rows
# would be overhead, not structure. The CHECK constraint below is what
# actually enforces the fixed set.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('HR', 'Manager', 'Intern', 'Engineer')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# The real Quadrant Technologies team, per exact instruction: only these
# ten accounts exist, no other roles, nothing extra. Names are derived
# from each email's local part since that's all that was given.
SEED_USERS = [
    ("areef.shaik@quadranttechnologies.com", "Areef Shaik", "Manager"),
    ("sai.saketh@quadranttechnologies.com", "Sai Saketh", "Manager"),
    ("moinuddin.m@quadranttechnologies.com", "Moinuddin M", "HR"),
    ("reeha.r@quadranttechnologies.com", "Reeha R", "HR"),
    ("i-khusum.r@quadranttechnologies.com", "Khusum R", "Intern"),
    ("i-maria.zia@quadranttechnologies.com", "Maria Zia", "Intern"),
    ("i-pranay.a@quadranttechnologies.com", "Pranay A", "Intern"),
    ("i-chaithra.allapuraju@quadranttechnologies.com", "Chaithra Allapuraju", "Intern"),
    ("i-dhruv.k@quadranttechnologies.com", "Dhruv K", "Engineer"),
    ("i-abhishek.s@quadranttechnologies.com", "Abhishek S", "Engineer"),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_demo_db() -> None:
    """Creates the schema and makes SEED_USERS the authoritative
    contents of the table - deletes anything not in that list (e.g. the
    original @bugbusters.demo placeholder accounts on an already-running
    deployment) rather than just appending to whatever's there. Safe to
    call on every app startup; running it twice in a row is a no-op.
    """
    conn = get_connection()

    try:
        conn.execute(SCHEMA)
        conn.execute("DELETE FROM users")

        conn.executemany(
            "INSERT INTO users (email, display_name, role) VALUES (?, ?, ?)",
            SEED_USERS,
        )

        conn.commit()
    finally:
        conn.close()
