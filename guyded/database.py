import os
from typing import Optional
import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"), min_size=2, max_size=10)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool


async def upsert_user(wa_id: str) -> int:
    row = await _get_pool().fetchrow(
        """
        INSERT INTO users (wa_id)
        VALUES ($1)
        ON CONFLICT (wa_id) DO UPDATE SET wa_id = EXCLUDED.wa_id
        RETURNING id
        """,
        wa_id,
    )
    return row["id"]


async def insert_message(user_id: int, direction: str, body: str) -> None:
    await _get_pool().execute(
        "INSERT INTO messages (user_id, direction, body) VALUES ($1, $2, $3)",
        user_id,
        direction,
        body,
    )


async def get_recent_messages(user_id: int, limit: int = 20) -> list[dict]:
    rows = await _get_pool().fetch(
        """
        SELECT direction, body
        FROM messages
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    # Return in chronological order so the Anthropic context reads naturally.
    return [dict(r) for r in reversed(rows)]


async def insert_handler_queue(user_id: int, ai_draft: str) -> None:
    await _get_pool().execute(
        "INSERT INTO handler_queue (user_id, ai_draft) VALUES ($1, $2)",
        user_id,
        ai_draft,
    )
