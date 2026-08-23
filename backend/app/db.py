"""
Database engine/session. Uses SQLite by default (zero-config, file-based,
perfect for a conference/demo deployment) but every model here is plain
SQLAlchemy — pointing DATABASE_URL at Postgres (e.g.
'postgresql://user:pass@host/db') works with no other code changes.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./foodbridge.db")

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
