import os
import urllib.parse
from typing import Any, Dict, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database.models_db import Base

# Azure SQL / Environment config
DATABASE_URL = os.getenv("DATABASE_URL")
DB_SERVER = os.getenv("DB_SERVER", "")
DB_NAME = os.getenv("DB_NAME", "TicketGenieDB")
DB_USER = os.getenv("DB_USER", "sqladmin")
DB_PASSWORD = os.getenv("DB_ADMIN_PASSWORD") or os.getenv("DB_PASSWORD", "")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

IS_AZURE_CONFIGURED = bool(DATABASE_URL or (DB_SERVER and DB_PASSWORD))


def _get_sqlalchemy_url() -> str:
    if DATABASE_URL:
        # Use complete SQLAlchemy URLs directly (SQLite, MSSQL, PostgreSQL, etc.).
        if "://" in DATABASE_URL:
            return DATABASE_URL
        # If raw ADO.NET / ODBC style string: "Server=tcp:...;Database=...;..."
        params = urllib.parse.quote_plus(DATABASE_URL)
        return f"mssql+pyodbc:///?odbc_connect={params}"

    if DB_SERVER and DB_PASSWORD:
        driver = DB_DRIVER.replace(" ", "+")
        is_port_in_server = "," in DB_SERVER or ":" in DB_SERVER
        server_str = DB_SERVER if is_port_in_server else f"{DB_SERVER},{DB_PORT}"
        user_str = urllib.parse.quote_plus(DB_USER)
        pwd_str = urllib.parse.quote_plus(DB_PASSWORD)
        return (
            f"mssql+pyodbc://{user_str}:{pwd_str}@{server_str}/{DB_NAME}"
            f"?driver={driver}&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30"
        )

    # Fallback to local SQLite database when Azure DB is not configured
    return "sqlite:///./ticketgenie.db"


def create_db_engine():
    db_url = _get_sqlalchemy_url()
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    try:
        engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        print(f"⚠️ Primary DB connection ({db_url.split('@')[-1]}) failed: {e}")
        print("💡 Falling back to local SQLite engine...")
        fallback_url = "sqlite:///./ticketgenie.db"
        return create_engine(
            fallback_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
        )


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db_schema():
    """Create database tables if they do not exist and ensure missing columns are added."""
    try:
        Base.metadata.create_all(bind=engine)
        # Handle SQLite column additions gracefully if table pre-existed
        if engine.dialect.name == "sqlite":
            with engine.connect() as conn:
                existing_cols = [
                    r[1]
                    for r in conn.execute(text("PRAGMA table_info(tickets)")).fetchall()
                ]
                if "queue" not in existing_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE tickets ADD COLUMN queue VARCHAR(100) DEFAULT 'IT - Service Desk'"
                        )
                    )
                if "parent_ticket_id" not in existing_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE tickets ADD COLUMN parent_ticket_id VARCHAR(50)"
                        )
                    )
                if "auto_resolved" not in existing_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE tickets ADD COLUMN auto_resolved BOOLEAN DEFAULT 0"
                        )
                    )
                if "is_synthetic" not in existing_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE tickets ADD COLUMN is_synthetic BOOLEAN DEFAULT 0"
                        )
                    )
                if "requester_id" not in existing_cols:
                    conn.execute(
                        text("ALTER TABLE tickets ADD COLUMN requester_id VARCHAR(150)")
                    )
                if "assigned_to" not in existing_cols:
                    conn.execute(
                        text("ALTER TABLE tickets ADD COLUMN assigned_to VARCHAR(150)")
                    )
                additions = {
                    "classification_status": "VARCHAR(50) DEFAULT 'Classified'",
                    "classification_confidence": "VARCHAR(20)",
                    "classification_reason": "TEXT",
                    "needs_human_review": "BOOLEAN DEFAULT 0",
                    "model_deployment": "VARCHAR(100)",
                    "onboarding_id": "VARCHAR(50)",
                    "due_date": "VARCHAR(50)",
                }
                for column_name, column_type in additions.items():
                    if column_name not in existing_cols:
                        conn.execute(
                            text(
                                f"ALTER TABLE tickets ADD COLUMN {column_name} {column_type}"
                            )
                        )

                # user_profiles column additions
                profile_cols = [
                    r[1]
                    for r in conn.execute(
                        text("PRAGMA table_info(user_profiles)")
                    ).fetchall()
                ]
                if "azure_object_id" not in profile_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE user_profiles ADD COLUMN azure_object_id VARCHAR(100)"
                        )
                    )

                onboarding_cols = [
                    r[1]
                    for r in conn.execute(
                        text("PRAGMA table_info(onboarding)")
                    ).fetchall()
                ]
                onboarding_additions = {
                    "employee_email": "VARCHAR(150)",
                    "manager": "VARCHAR(150)",
                    "location": "VARCHAR(150)",
                    "created_by": "VARCHAR(150)",
                }
                for column_name, column_type in onboarding_additions.items():
                    if column_name not in onboarding_cols:
                        conn.execute(
                            text(
                                f"ALTER TABLE onboarding ADD COLUMN {column_name} {column_type}"
                            )
                        )

                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_tickets_onboarding_id "
                        "ON tickets (onboarding_id)"
                    )
                )

                conn.commit()
        elif engine.dialect.name == "mssql":
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "IF COL_LENGTH('tickets', 'is_synthetic') IS NULL "
                        "ALTER TABLE tickets ADD is_synthetic BIT NOT NULL "
                        "CONSTRAINT DF_tickets_is_synthetic DEFAULT 0"
                    )
                )
                conn.execute(
                    text(
                        "IF COL_LENGTH('tickets', 'onboarding_id') IS NULL "
                        "ALTER TABLE tickets ADD onboarding_id VARCHAR(50) NULL"
                    )
                )
                conn.execute(
                    text(
                        "IF COL_LENGTH('tickets', 'due_date') IS NULL "
                        "ALTER TABLE tickets ADD due_date VARCHAR(50) NULL"
                    )
                )
                for column_name, column_type in {
                    "employee_email": "VARCHAR(150) NULL",
                    "manager": "VARCHAR(150) NULL",
                    "location": "VARCHAR(150) NULL",
                    "created_by": "VARCHAR(150) NULL",
                }.items():
                    conn.execute(
                        text(
                            f"IF COL_LENGTH('onboarding', '{column_name}') IS NULL "
                            f"ALTER TABLE onboarding ADD {column_name} {column_type}"
                        )
                    )
                conn.execute(
                    text(
                        "IF NOT EXISTS (SELECT 1 FROM sys.indexes "
                        "WHERE name = 'ix_tickets_onboarding_id') "
                        "CREATE INDEX ix_tickets_onboarding_id "
                        "ON tickets (onboarding_id)"
                    )
                )
    except Exception as e:
        print(f"⚠️ Error creating database schema: {e}")


def get_db_config() -> Dict[str, Any]:
    """Return configured database connection parameters."""
    return {
        "server": DB_SERVER or "Azure SQL",
        "database": DB_NAME,
        "user": DB_USER,
        "password": "***" if DB_PASSWORD else None,
        "is_configured": IS_AZURE_CONFIGURED,
        "dialect": engine.dialect.name,
    }


def check_db_health() -> bool:
    """Check connection status for database backend."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_db() -> Generator[Session, None, None]:
    """Dependency injection provider for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
