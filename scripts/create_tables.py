# scripts/create_tables.py
import asyncio
from src.core.database import Base, engine

# Importer tous les modèles pour que Base connaisse toutes les tables
import src.model.models
import src.model.evaluation_rubric
import src.model.criterion_score


async def main():
    async with engine.begin() as conn:
        # run_sync permet d'exécuter la création de tables de façon synchrone sur AsyncEngine
        await conn.run_sync(Base.metadata.create_all)
    print("Toutes les tables ont été créées avec succès")


if __name__ == "__main__":
    asyncio.run(main())
