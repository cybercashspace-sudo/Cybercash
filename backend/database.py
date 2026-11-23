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
# Render supplies postgres:// URLs; SQLAlchemy needs explicit sync/async drivers.
def _normalize_database_url(url: str, *, asynchronous: bool) -> str:
    value = str(url or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]

    if asynchronous and value.startswith("postgresql://"):
        return "postgresql+asyncpg://" + value[len("postgresql://"):]
    if not asynchronous and value.startswith("postgresql+asyncpg://"):
        return "postgresql://" + value[len("postgresql+asyncpg://"):]
    return value


SYNC_DATABASE_URL = _normalize_database_url(
    os.getenv("SYNC_DATABASE_URL", "sqlite:///./cybercash.db"),
    asynchronous=False,
)
ASYNC_DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./cybercash.db"),
    asynchronous=True,
)
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
