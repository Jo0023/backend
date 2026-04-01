from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.models import PeerEvaluation
from src.model.peer_score import PeerCriterionScore


class PeerEvaluationRepository:
    """
    Репозиторий взаимной оценки / Peer evaluation repository
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    async def create_peer_evaluation(
        self,
        project_id: int,
        session_id: int,
        evaluator_id: int,
        evaluated_id: int,
        template_id: int,
        role: str,
        comment: str,
        is_anonymous: bool,
    ) -> PeerEvaluation:
        """
        Создать запись взаимной оценки / Create peer evaluation record
        """
        evaluation = PeerEvaluation(
            project_id=project_id,
            session_id=session_id,
            evaluator_id=evaluator_id,
            evaluated_id=evaluated_id,
            template_id=template_id,
            role=role,
            comment=comment,
            is_anonymous=is_anonymous,
            submitted_at=datetime.now(UTC),
            is_submitted=True,
        )
        self.uow.session.add(evaluation)
        await self.uow.session.flush()
        await self.uow.session.refresh(evaluation)
        return evaluation

    async def create_peer_scores(
        self,
        peer_evaluation_id: int,
        criterion_scores: list[tuple[int, int]],
    ) -> list[PeerCriterionScore]:
        """
        Создать оценки по критериям взаимной оценки / Create peer criterion scores

        criterion_scores format:
        [(criterion_id, score), ...]
        """
        created_rows: list[PeerCriterionScore] = []

        for criterion_id, score in criterion_scores:
            row = PeerCriterionScore(
                peer_evaluation_id=peer_evaluation_id,
                criterion_id=criterion_id,
                score=score,
            )
            self.uow.session.add(row)
            created_rows.append(row)

        await self.uow.session.flush()
        return created_rows

    async def get_peer_evaluation_with_scores(self, evaluation_id: int) -> PeerEvaluation | None:
        """
        Получить одну взаимную оценку со всеми критериями / Get one peer evaluation with all criterion scores
        """
        result = await self.uow.session.execute(
            select(PeerEvaluation)
            .where(PeerEvaluation.id == evaluation_id)
            .options(
                selectinload(PeerEvaluation.template),
                selectinload(PeerEvaluation.criterion_scores).selectinload(
                    PeerCriterionScore.criterion
                ),
            )
        )
        return result.scalar_one_or_none()

    async def has_submitted_peer_evaluation(
        self,
        session_id: int,
        evaluator_id: int,
        evaluated_id: int,
        role: str,
    ) -> bool:
        """
        Проверить, отправлял ли пользователь такую форму / Check if peer evaluation already exists
        """
        result = await self.uow.session.execute(
            select(PeerEvaluation.id).where(
                and_(
                    PeerEvaluation.session_id == session_id,
                    PeerEvaluation.evaluator_id == evaluator_id,
                    PeerEvaluation.evaluated_id == evaluated_id,
                    PeerEvaluation.role == role,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_peer_evaluations_by_session(self, session_id: int) -> list[PeerEvaluation]:
        """
        Получить все взаимные оценки по сессии / Get all peer evaluations by session
        """
        result = await self.uow.session.execute(
            select(PeerEvaluation)
            .where(PeerEvaluation.session_id == session_id)
            .order_by(PeerEvaluation.submitted_at.asc())
            .options(
                selectinload(PeerEvaluation.template),
                selectinload(PeerEvaluation.criterion_scores).selectinload(
                    PeerCriterionScore.criterion
                ),
            )
        )
        return list(result.scalars().all())

    async def get_leader_evaluations_by_members(
        self,
        project_id: int,
        leader_id: int,
        session_id: int | None = None,
    ) -> list[PeerEvaluation]:
        """
        Получить оценки руководителя от членов команды / Get leader evaluations from members
        """
        conditions = [
            PeerEvaluation.project_id == project_id,
            PeerEvaluation.evaluated_id == leader_id,
            PeerEvaluation.role == "member_to_leader",
        ]

        if session_id is not None:
            conditions.append(PeerEvaluation.session_id == session_id)

        result = await self.uow.session.execute(
            select(PeerEvaluation)
            .where(and_(*conditions))
            .order_by(PeerEvaluation.submitted_at.asc())
            .options(
                selectinload(PeerEvaluation.template),
                selectinload(PeerEvaluation.criterion_scores).selectinload(
                    PeerCriterionScore.criterion
                ),
            )
        )
        return list(result.scalars().all())

    async def get_member_evaluations_by_leader(
        self,
        project_id: int,
        member_id: int,
        session_id: int | None = None,
    ) -> list[PeerEvaluation]:
        """
        Получить оценки участника от руководителя / Get member evaluations from leader
        """
        conditions = [
            PeerEvaluation.project_id == project_id,
            PeerEvaluation.evaluated_id == member_id,
            PeerEvaluation.role == "leader_to_member",
        ]

        if session_id is not None:
            conditions.append(PeerEvaluation.session_id == session_id)

        result = await self.uow.session.execute(
            select(PeerEvaluation)
            .where(and_(*conditions))
            .order_by(PeerEvaluation.submitted_at.asc())
            .options(
                selectinload(PeerEvaluation.template),
                selectinload(PeerEvaluation.criterion_scores).selectinload(
                    PeerCriterionScore.criterion
                ),
            )
        )
        return list(result.scalars().all())

    async def count_peer_evaluations_by_session(self, session_id: int) -> int:
        """
        Подсчитать количество взаимных оценок / Count peer evaluations by session
        """
        result = await self.uow.session.execute(
            select(func.count(PeerEvaluation.id)).where(
                PeerEvaluation.session_id == session_id
            )
        )
        return int(result.scalar_one() or 0)