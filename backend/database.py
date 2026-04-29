import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

# Load .env variables from the project root explicitly.
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(dotenv_path)

# ==========================================
# DATABASE URLS
# ==========================================
# You can set DATABASE_URL in .env, otherwise fallback to SQLite
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", "sqlite:///./cybercash.db")
ASYNC_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./cybercash.db")

# ==========================================
# SYNC ENGINE & SESSION (for tests / admin scripts)
# ==========================================
engine = create_engine(
    SYNC_DATABASE_URL,
    connect_args={"check_same_thread": False} if SYNC_DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ==========================================
# ASYNC ENGINE & SESSION (for FastAPI / async routes)
# ==========================================
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,  # set True for SQL logging
    future=True,
)

async_session = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Backward-compatible alias expected by some route modules.
AsyncSessionLocal = async_session

# ==========================================
# BASE MODEL
# ==========================================
class Base(DeclarativeBase):
    pass

# ==========================================
# ASYNC SESSION DEPENDENCY (for FastAPI)
# ==========================================
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session

# ==========================================
# INIT DATABASE FUNCTION
# ==========================================
async def init_db():
    async with async_engine.begin() as conn:
        # Creates all tables if not exist
        await conn.run_sync(Base.metadata.create_all)
