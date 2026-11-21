from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def ensure_runtime_schema(conn) -> None:
    """Add columns introduced after the initial database was created.

    The project historically used ``create_all`` without migrations. This keeps
    existing SQLite/Postgres databases usable after the document organisation,
    access-control and semantic-search columns were added.
    """
    dialect = conn.dialect.name
    if dialect == "sqlite":
        document_columns = {
            row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(documents)")).fetchall()
        }
        if "folder_id" not in document_columns:
            await conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN folder_id VARCHAR(36)")
        if "is_restricted" not in document_columns:
            await conn.exec_driver_sql(
                "ALTER TABLE documents ADD COLUMN is_restricted BOOLEAN NOT NULL DEFAULT 0"
            )
        version_columns = {
            row[1]
            for row in (
                await conn.exec_driver_sql("PRAGMA table_info(document_versions)")
            ).fetchall()
        }
        if "embedding" not in version_columns:
            await conn.exec_driver_sql("ALTER TABLE document_versions ADD COLUMN embedding TEXT")
    elif dialect == "postgresql":
        await conn.exec_driver_sql(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS folder_id VARCHAR(36)"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_restricted BOOLEAN NOT NULL DEFAULT FALSE"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS embedding TEXT"
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
