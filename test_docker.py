# test_docker.py (version simplifiée)
from __future__ import annotations

import asyncio

import asyncpg


async def test():
    try:
        conn = await asyncpg.connect(
            user="postgres", password="postgres", database="backend", host="localhost", port=5432
        )
        print("✅ CONNEXION RÉUSSIE !")
        await conn.close()
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")


asyncio.run(test())
