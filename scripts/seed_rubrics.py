import asyncio

from src.core.database import AsyncSessionLocal
from src.model.evaluation_rubric import EvaluationTemplate, EvaluationCriterion


async def create_template(session, name, project_type, criteria):
    template = EvaluationTemplate(
        name=name,
        project_type=project_type,
        academic_year="2026",
        is_active=True
    )

    session.add(template)
    await session.flush()

    for criterion_name, description, weight in criteria:
        session.add(
            EvaluationCriterion(
                template_id=template.id,
                name=criterion_name,
                description=description,
                weight=weight
            )
        )


async def seed():
    async with AsyncSessionLocal() as session:

        # PRODUCT PROJECT
        await create_template(
            session,
            "Оценка продуктового проекта",
            "product",
            [
                ("presentation_clarity", "Ясность презентации", 0.2),
                ("teamwork", "Командная работа", 0.2),
                ("product_understanding", "Понимание продукта", 0.2),
                ("ux_demo", "Демонстрация UX", 0.2),
                ("product_value", "Ценность продукта", 0.2),
            ]
        )

        # TECHNICAL PROJECT
        await create_template(
            session,
            "Оценка технического проекта",
            "technical",
            [
                ("presentation_clarity", "Ясность презентации", 0.2),
                ("teamwork", "Командная работа", 0.2),
                ("architecture_understanding", "Понимание архитектуры", 0.2),
                ("solution_demo", "Демонстрация решения", 0.2),
                ("solution_explanation", "Объяснение решения", 0.2),
            ]
        )

        # RESEARCH PROJECT
        await create_template(
            session,
            "Оценка исследовательского проекта",
            "research",
            [
                ("presentation_clarity", "Ясность презентации", 0.2),
                ("teamwork", "Командная работа", 0.2),
                ("research_understanding", "Понимание исследования", 0.2),
                ("data_analysis", "Анализ данных", 0.2),
                ("scientific_logic", "Научная логика", 0.2),
            ]
        )

        await session.commit()
        print("Шаблоны оценки успешно созданы")


if __name__ == "__main__":
    asyncio.run(seed())
