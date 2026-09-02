from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from settings import DATABASE_URL

# check_same_thread=False is only needed for SQLite (FastAPI can use a
# request's session from a different thread than it was created on) — this
# is a no-op for other database backends.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
