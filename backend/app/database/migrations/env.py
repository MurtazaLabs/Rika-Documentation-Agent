"""Alembic environment.

The database URL comes from application settings, never from alembic.ini, so
there is only one place to configure it and no password in a tracked file.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.database.base import Base
from app.database.models import *  # noqa: F401,F403 - registers every table

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# ConfigParser reads % as interpolation, so escape any literal percent sign
# that could appear in a URL-encoded password.
config.set_main_option(
    "sqlalchemy.url", get_settings().database_url.replace("%", "%%")
)

target_metadata = Base.metadata

# PostgreSQL-only columns that exist in migrations but cannot be mapped.
#
# ``document_chunks.search_vector`` is a stored generated tsvector column;
# SQLite cannot evaluate ``to_tsvector`` when it creates the test schema, and a
# Column has no dialect-conditional DDL (an Index does, see the model). Without
# this filter autogenerate reports the reflected column as removed and would
# emit ``DROP COLUMN search_vector``, silently killing keyword search.
UNMODELLED_COLUMNS = {("document_chunks", "search_vector")}


def include_object(
    object_, name: str | None, type_: str, reflected: bool, compare_to
) -> bool:
    """Hide the PostgreSQL-only generated column from autogenerate."""
    if type_ == "column" and reflected and compare_to is None:
        table = getattr(object_, "table", None)
        if table is not None and (table.name, object_.name) in UNMODELLED_COLUMNS:
            return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
