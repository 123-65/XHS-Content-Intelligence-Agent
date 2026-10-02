from collections.abc import AsyncGenerator

import asyncpg

from insight_rag.core.config import settings


class AsyncPgPool:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def get(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=settings.async_database_url,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


async_pg_pool = AsyncPgPool()


async def get_async_pg() -> AsyncGenerator[asyncpg.Connection, None]:
    pool = await async_pg_pool.get()
    async with pool.acquire() as conn:
        yield conn

