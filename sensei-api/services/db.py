from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from config import get_settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # statement_cache_size=0: Supavisor's transaction-mode pooler doesn't
        # support prepared statements (each pooled connection can be handed
        # to a different client between statements) — verified empirically
        # against the live pooler (DuplicatePreparedStatementError otherwise).
        _pool = await asyncpg.create_pool(
            get_settings().SUPABASE_DB_DSN, statement_cache_size=0
        )
    return _pool


@asynccontextmanager
async def user_scoped_tx(user_id: str) -> AsyncIterator[asyncpg.Connection]:
    """Open a transaction with RLS scoped to `user_id` (ADR-0009).

    `SET LOCAL` is transaction-scoped, so it can never bleed across pooled
    connections — must run inside this transaction, never a bare `SET`.
    """
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SELECT set_config('app.current_user_id', $1, true)", user_id)
        yield conn
