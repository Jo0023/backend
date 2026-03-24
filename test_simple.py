from __future__ import annotations

import asyncio

import asyncpg


async def test_simple():
    try:
        print("🟡 Tentative de connexion...")
        conn = await asyncpg.connect(
            user="postgres", password="postgres", database="postgres", host="localhost", port=5432, timeout=5
        )
        print("✅ CONNEXION RÉUSSIE !")
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ ÉCHEC: {type(e).__name__}: {e}")
        return False


asyncio.run(test_simple())
