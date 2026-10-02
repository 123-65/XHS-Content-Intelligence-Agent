from __future__ import annotations

from typing import Any

import asyncpg


async def append_message(
    conn: asyncpg.Connection,
    session_id: int,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
) -> int:
    return await conn.fetchval(
        "INSERT INTO chat_messages (session_id, role, content, sources) VALUES ($1, $2, $3, $4) RETURNING id",
        session_id,
        role,
        content,
        sources or [],
    )


async def load_recent_history(conn: asyncpg.Connection, session_id: int, limit: int = 10) -> list[dict[str, str]]:
    rows = await conn.fetch(
        "SELECT role, content FROM chat_messages WHERE session_id = $1 "
        "AND role = ANY($2::text[]) ORDER BY created_at DESC, id DESC LIMIT $3",
        session_id,
        ["user", "assistant"],
        limit,
    )
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
