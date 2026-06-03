import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Auto-detect: use DATABASE_URL env var if set, otherwise fall back to SQLite for zero-config local dev
_configured_url = os.getenv("DATABASE_URL", "")
if _configured_url and not _configured_url.startswith("postgresql://user:pass"):
    DATABASE_URL = _configured_url
else:
    _db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "payshield.db")
    DATABASE_URL = f"sqlite:///{_db_path}"

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
