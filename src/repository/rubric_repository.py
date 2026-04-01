from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.model.evaluation_rubric import EvaluationCriterion, EvaluationTemplate


class RubricRepository:
    """
    Репозиторий шаблонов и критериев оценки / Repository for evaluation templates and criteria
    """

    def __init__(self, session):
        self.session = session

    async def get_active_template(self, project_type: str) -> EvaluationTemplate:
        """
        Получить активный шаблон по типу проекта / Get active template by project type
        """
        result = await self.session.execute(
            select(EvaluationTemplate)
            .where(
                EvaluationTemplate.project_type == project_type,
                EvaluationTemplate.is_active.is_(True),
            )
            .options(selectinload(EvaluationTemplate.criteria))
        )

        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Не найден активный шаблон оценки для типа проекта: {project_type}")

        return template

    async def get_template_criteria(self, template_id: int) -> list[EvaluationCriterion]:
        """
        Получить критерии шаблона / Get template criteria
        """
        result = await self.session.execute(
            select(EvaluationCriterion)
            .where(EvaluationCriterion.template_id == template_id)
            .order_by(EvaluationCriterion.id.asc())
        )
        return list(result.scalars().all())