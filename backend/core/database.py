"""
Database configuration
Includes database connection, session management, and dependency injection
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
from backend.models.base import Base

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or DATABASE_URL == "sqlite:///autoclip.db":
    try:
        from .config import get_database_url
        DATABASE_URL = get_database_url()
    except Exception:
        DATABASE_URL = "sqlite:///./data/clipfarm.db"

# Ensure SQLite storage directory exists and migrate legacy autoclip.db if needed
if DATABASE_URL.startswith("sqlite:///"):
    raw_path = DATABASE_URL.replace("sqlite:///", "")
    if raw_path and raw_path != ":memory:":
        try:
            db_path = Path(raw_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            if "clipfarm.db" in db_path.name:
                legacy_db = db_path.parent / "autoclip.db"
                if legacy_db.exists() and (not db_path.exists() or db_path.stat().st_size == 0):
                    import shutil
                    shutil.copy2(legacy_db, db_path)
        except Exception:
            pass

# Create database engine
if "sqlite" in DATABASE_URL:
    sqlite_kwargs = {
        "connect_args": {
            "check_same_thread": False,
            "timeout": 30
        },
        "pool_pre_ping": True,
        "echo": False
    }
    if ":memory:" in DATABASE_URL:
        sqlite_kwargs["poolclass"] = StaticPool
        
    engine = create_engine(DATABASE_URL, **sqlite_kwargs)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.close()
        except Exception:
            pass
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency injection
    For FastAPI's dependency injection system
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """Drop all database tables"""
    Base.metadata.drop_all(bind=engine)

def reset_database():
    """Reset database"""
    drop_tables()
    create_tables()

from sqlalchemy import text

def test_connection() -> bool:
    """Test database connection"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        return True
    except Exception as e:
        print(f"Database connection test failed: {e}")
        return False

# Database initialization
def init_database():
    """Initialize database"""
    print("Initializing database...")
    
    # Test connection
    if not test_connection():
        print("❌ Database connection failed")
        return False
    
    # Create table
    try:
        create_tables()
        print("✅ Database table creation successful")
        return True
    except Exception as e:
        print(f"❌ Database table creation failed: {e}")
        return False

if __name__ == "__main__":
    # When running this file directly, initialize the database
    init_database()