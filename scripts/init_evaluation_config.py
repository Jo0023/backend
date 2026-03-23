import asyncio
from src.core.database import AsyncSessionLocal
from src.model.models import EvaluationConfig
from datetime import datetime, UTC

async def init_config():
    async with AsyncSessionLocal() as session:
        # Vérifier si une config existe déjà
        from sqlalchemy import select
        result = await session.execute(select(EvaluationConfig))
        existing = result.scalar_one_or_none()
        
        if not existing:
            config = EvaluationConfig(
                peer_evaluation_days=7,
                commission_evaluation_minutes=2,
                presentation_minutes=5,
                evaluation_opening_minutes=10,
                is_active=True,
                created_at=datetime.now(UTC),
            )
            session.add(config)
            await session.commit()
            print("Configuration initiale créée")
        else:
            print("Configuration déjà existante")

if __name__ == "__main__":
    asyncio.run(init_config())