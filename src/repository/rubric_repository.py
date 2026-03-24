from sqlalchemy import select
from src.model.evaluation_rubric import EvaluationTemplate, EvaluationCriterion


class RubricRepository:

    def __init__(self, session):
        self.session = session

    async def get_active_template(self, project_type: str):

        result = await self.session.execute(
            select(EvaluationTemplate)
            .where(
                EvaluationTemplate.project_type == project_type,
                EvaluationTemplate.is_active == True
            )
        )

        template = result.scalar_one_or_none()

        if not template:
            raise ValueError(
                f"Не найден активный шаблон оценки для типа проекта: {project_type}"
            )

        return template

    async def get_template_criteria(self, template_id: int):

        result = await self.session.execute(
            select(EvaluationCriterion)
            .where(EvaluationCriterion.template_id == template_id)
        )

        return result.scalars().all()
