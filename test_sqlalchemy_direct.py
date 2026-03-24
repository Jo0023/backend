from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def test():
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/backend"
    print(f"🟡 Tentative avec: {DATABASE_URL}")

    engine = create_async_engine(DATABASE_URL, echo=True)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"✅ SUCCÈS: {result.scalar()}")
    except Exception as e:
        print(f"❌ ÉCHEC: {type(e).__name__}: {e}")
    finally:
        await engine.dispose()


asyncio.run(test())
