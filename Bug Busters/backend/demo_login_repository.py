"""Lookup logic for the demo login fallback. Kept separate from
demo_login_db.py (connection/schema) and main.py (the endpoint) so each
piece can be tested and touched independently.
"""

from demo_login_db import get_connection


def get_user_by_email(email: str) -> dict | None:
    """Case-insensitive email lookup. Returns a plain dict (not a
    sqlite3.Row) so callers - including main.py's response model - don't
    need to know anything about the storage layer.
    """
    conn = get_connection()

    try:
        row = conn.execute(
            "SELECT email, display_name, role FROM users WHERE LOWER(email) = LOWER(?)",
            (email.strip(),),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return {"email": row["email"], "display_name": row["display_name"], "role": row["role"]}


def list_users() -> list[dict]:
    """Full roster, ordered by name - used to give the chat widget
    grounded answers to "who is X" questions instead of guessing.
    """
    conn = get_connection()

    try:
        rows = conn.execute(
            "SELECT email, display_name, role FROM users ORDER BY display_name"
        ).fetchall()
    finally:
        conn.close()

    return [{"email": r["email"], "display_name": r["display_name"], "role": r["role"]} for r in rows]
