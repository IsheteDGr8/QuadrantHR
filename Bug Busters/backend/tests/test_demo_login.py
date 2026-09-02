import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

import demo_login_db
import demo_login_repository


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Points the demo DB at a throwaway file per test so tests never
    touch (or depend on) the real backend/demo_login.db."""
    test_db_path = tmp_path / "test_demo_login.db"
    monkeypatch.setattr(demo_login_db, "DB_PATH", test_db_path)
    demo_login_db.init_demo_db()
    return test_db_path


def test_init_demo_db_seeds_exactly_the_real_roster():
    conn = demo_login_db.get_connection()
    try:
        rows = conn.execute("SELECT email, role FROM users ORDER BY email").fetchall()
    finally:
        conn.close()

    assert len(rows) == 10

    roles = sorted(row["role"] for row in rows)
    assert roles == (
        ["Engineer"] * 2 + ["HR"] * 2 + ["Intern"] * 4 + ["Manager"] * 2
    )


def test_init_demo_db_is_idempotent():
    # Calling init again shouldn't duplicate rows or error on the UNIQUE
    # email constraint.
    demo_login_db.init_demo_db()
    demo_login_db.init_demo_db()

    conn = demo_login_db.get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    finally:
        conn.close()

    assert count == 10


def test_init_demo_db_removes_stale_rows_not_in_seed_list():
    # Simulates an old deployment's DB still having the original
    # @bugbusters.demo placeholder accounts - re-running init should
    # remove them, not just add the real roster alongside them.
    conn = demo_login_db.get_connection()
    try:
        conn.execute(
            "INSERT INTO users (email, display_name, role) VALUES (?, ?, ?)",
            ("hr@bugbusters.demo", "Old Demo HR User", "HR"),
        )
        conn.commit()
    finally:
        conn.close()

    demo_login_db.init_demo_db()

    assert demo_login_repository.get_user_by_email("hr@bugbusters.demo") is None

    conn = demo_login_db.get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    finally:
        conn.close()

    assert count == 10


def test_get_user_by_email_found():
    user = demo_login_repository.get_user_by_email("reeha.r@quadranttechnologies.com")

    assert user == {
        "email": "reeha.r@quadranttechnologies.com",
        "display_name": "Reeha R",
        "role": "HR",
    }


def test_get_user_by_email_case_insensitive():
    user = demo_login_repository.get_user_by_email("REEHA.R@QuadrantTechnologies.com")

    assert user["role"] == "HR"


def test_get_user_by_email_not_found():
    assert demo_login_repository.get_user_by_email("nobody@example.com") is None


def test_list_users_returns_full_roster():
    users = demo_login_repository.list_users()

    assert len(users) == 10
    emails = {u["email"] for u in users}
    assert "reeha.r@quadranttechnologies.com" in emails
    assert "i-maria.zia@quadranttechnologies.com" in emails
