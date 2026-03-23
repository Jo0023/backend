from pydantic import create_model, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.model.evaluation_rubric import EvaluationTemplate


async def get_scores_model(session: AsyncSession, project_type: str):
    """
    Génère dynamiquement un modèle Pydantic pour les scores
    """

    result = await session.execute(
        select(EvaluationTemplate)
        .where(EvaluationTemplate.project_type == project_type)
        .where(EvaluationTemplate.is_active == True)
        .options(selectinload(EvaluationTemplate.criteria))
    )

    template = result.scalars().first()

    if not template:
        raise ValueError(
            f"Aucun template trouvé pour project_type='{project_type}'"
        )

    # ⚡ Champs dynamiques AVEC validation
    fields = {
        criterion.name: (
            int,
            Field(..., ge=1, le=5, description=criterion.description)
        )
        for criterion in template.criteria
    }

    DynamicScoresModel = create_model(
        f"{project_type.capitalize()}Scores",
        **fields
    )

    return DynamicScoresModel
