from pathlib import Path
from collections.abc import AsyncGenerator

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# Parse DB path and ensure parent dir exists before creating engine
_db_url = settings.database_url
_db_file = _db_url.split(":///")[-1] if ":///" in _db_url else None
if _db_file:
    Path(_db_file).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    _db_url,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_size=1,
    max_overflow=2,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Enable WAL mode for better concurrent read/write
    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))
        await conn.execute(sqlalchemy.text("PRAGMA busy_timeout=10000"))
        await conn.execute(sqlalchemy.text("PRAGMA synchronous=NORMAL"))

    # Migrations: add columns if missing
    async with engine.begin() as conn:
        for col, definition in [
            ("retry_count", "INTEGER NOT NULL DEFAULT 0"),
            ("max_retries", "INTEGER NOT NULL DEFAULT 5"),
            ("source_site", "TEXT NOT NULL DEFAULT 'animeunity'"),
            ("episode_title", "TEXT"),
            ("dest_folder_override", "TEXT"),
            ("filename_template", "TEXT"),
            ("filename_template_type", "TEXT"),
            ("scheduled_download_id", "INTEGER"),
        ]:
            try:
                await conn.execute(
                    sqlalchemy.text(f"ALTER TABLE downloads ADD COLUMN {col} {definition}")
                )
            except Exception:
                pass  # Column already exists
