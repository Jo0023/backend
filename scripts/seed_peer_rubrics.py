import asyncio

from src.core.database import AsyncSessionLocal
from src.model.evaluation_rubric import EvaluationTemplate, EvaluationCriterion

async def seed_peer_templates():
    async with AsyncSessionLocal() as session:
        
        # Template pour member_to_leader (membres évaluent le leader)
        member_template = EvaluationTemplate(
            name="Оценка руководителя командой",
            project_type="peer_member_to_leader",
            academic_year="2026",
            is_active=True
        )
        session.add(member_template)
        await session.flush()
        
        member_criteria = [
            ("leadership", "Качество лидерства", 1.0),
            ("communication", "Навыки коммуникации", 1.0),
            ("task_delegation", "Делегирование задач", 1.0),
            ("decision_making", "Принятие решений", 1.0),
            ("conflict_resolution", "Разрешение конфликтов", 1.0),
        ]
        
        for name, desc, weight in member_criteria:
            session.add(EvaluationCriterion(
                template_id=member_template.id,
                name=name,
                description=desc,
                weight=weight
            ))
        
        # Template pour leader_to_member (leader évalue les membres)
        leader_template = EvaluationTemplate(
            name="Оценка члена команды руководителем",
            project_type="peer_leader_to_member",
            academic_year="2026",
            is_active=True
        )
        session.add(leader_template)
        await session.flush()
        
        leader_criteria = [
            ("technical_skills", "Технические навыки", 1.0),
            ("teamwork", "Командная работа", 1.0),
            ("initiative", "Инициативность", 1.0),
            ("reliability", "Надежность", 1.0),
            ("communication", "Коммуникация", 1.0),
        ]
        
        for name, desc, weight in leader_criteria:
            session.add(EvaluationCriterion(
                template_id=leader_template.id,
                name=name,
                description=desc,
                weight=weight
            ))
        
        await session.commit()
        print("Templates pour évaluations mutuelles créés avec succès")

if __name__ == "__main__":
    asyncio.run(seed_peer_templates())