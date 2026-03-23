from __future__ import annotations

import asyncio

import asyncpg


async def test():
    try:
        print("🟡 Tentative de connexion à PostgreSQL...")
        conn = await asyncpg.connect(
            user="postgres", password="postgres", database="backend", host="localhost", port=5432
        )
        print("✅ CONNEXION RÉUSSIE !")
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ ÉCHEC: {type(e).__name__}: {e}")
        return False


asyncio.run(test())
