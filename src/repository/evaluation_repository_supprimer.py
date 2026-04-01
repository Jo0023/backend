"""
Evaluation Repository - STRICT DATA ACCESS LAYER (FAANG-grade)

Design constraints:
- No business logic
- No implicit domain rules
- Fully typed queries
- Safe SQL aggregation
- Deterministic behaviors
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.models import (
    CommissionEvaluation,
    PeerEvaluation,
    PresentationSession,
    Project,
    ProjectParticipation,
    PresentationSchedule,
)
from src.model.commission_score import CommissionCriterionScore
from src.model.peer_score import PeerCriterionScore
from src.schema.evaluation import PeerEvaluationSubmit, PresentationSessionCreate


# =========================================================
# ENUMS (STRICT CONTRACT LAYER)
# =========================================================

class SessionStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EVALUATED = "EVALUATED"
    SKIPPED = "SKIPPED"


class ScheduleStatus(str, Enum):
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    COMPLETED = "COMPLETED"


class EvaluationRole(str, Enum):
    MEMBER_TO_LEADER = "member_to_leader"
    LEADER_TO_MEMBER = "leader_to_member"


# =========================================================
# REPOSITORY
# =========================================================

class EvaluationRepository:
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    # =====================================================
    # SESSION - CORE
    # =====================================================

    async def create_session(
        self,
        data: PresentationSessionCreate,
    ) -> PresentationSession:
        session = PresentationSession(
            project_id=data.project_id,
            teacher_id=data.teacher_id,
            status=SessionStatus.PENDING,
            presentation_started_at=datetime.now(timezone.utc),
        )
        self.uow.session.add(session)
        await self.uow.session.flush()
        await self.uow.session.refresh(session)
        return session

    async def get_session_by_id(
        self,
        session_id: int,
    ) -> Optional[PresentationSession]:
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(PresentationSession.id == session_id)
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return result.scalar_one_or_none()

    async def update_session_status(
        self,
        session_id: int,
        status: SessionStatus,
    ) -> None:
        await self.uow.session.execute(
            update(PresentationSession)
            .where(PresentationSession.id == session_id)
            .values(status=status)
        )

    async def set_evaluation_window(
        self,
        session_id: int,
        duration_minutes: int,
    ) -> PresentationSession:
        now = datetime.now(timezone.utc)
        closes_at = now + timedelta(minutes=duration_minutes)

        await self.uow.session.execute(
            update(PresentationSession)
            .where(PresentationSession.id == session_id)
            .values(
                evaluation_opened_at=now,
                evaluation_closes_at=closes_at,
                status=SessionStatus.ACTIVE,
            )
        )
        return await self.get_session_by_id(session_id)

    # =====================================================
    # SESSION - COMPLEMENT
    # =====================================================

    async def get_sessions_by_project(
        self,
        project_id: int,
    ) -> List[PresentationSession]:
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(PresentationSession.project_id == project_id)
            .order_by(PresentationSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_final_session(
        self,
        project_id: int,
    ) -> Optional[PresentationSession]:
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.is_final.is_(True),
                )
            )
            .order_by(PresentationSession.created_at.desc())
            .options(selectinload(PresentationSession.project))
        )
        return result.scalar_one_or_none()

    async def get_session_by_project_and_date_range(
        self,
        project_id: int,
        start_utc: datetime,
        end_utc: datetime,
    ) -> Optional[PresentationSession]:
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.created_at >= start_utc,
                    PresentationSession.created_at <= end_utc,
                )
            )
            .order_by(PresentationSession.created_at.desc())
        )
        return result.scalar_one_or_none()
    
    async def get_project_today_session(self, project_id: int) -> Optional[PresentationSession]:
        """Get today's session for a project"""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day.replace(hour=23, minute=59, second=59)
        
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.created_at >= start_of_day,
                    PresentationSession.created_at <= end_of_day,
                )
            )
            .order_by(PresentationSession.created_at.desc())
        )
        return result.scalar_one_or_none()

    # =====================================================
    # SCHEDULE - CORE
    # =====================================================

    async def create_schedule(
        self,
        project_id: int,
        presentation_date: datetime,
        order_index: int,
    ) -> PresentationSchedule:
        schedule = PresentationSchedule(
            project_id=project_id,
            presentation_date=presentation_date,
            order_index=order_index,
            status=ScheduleStatus.PENDING,
        )
        self.uow.session.add(schedule)
        await self.uow.session.flush()
        await self.uow.session.refresh(schedule)
        return schedule

    async def update_schedule_status(
        self,
        schedule_id: int,
        status: ScheduleStatus,
    ) -> None:
        await self.uow.session.execute(
            update(PresentationSchedule)
            .where(PresentationSchedule.id == schedule_id)
            .values(status=status)
        )

    async def update_schedule_order(
        self,
        schedule_id: int,
        order_index: int,
    ) -> None:
        await self.uow.session.execute(
            update(PresentationSchedule)
            .where(PresentationSchedule.id == schedule_id)
            .values(order_index=order_index)
        )

    async def delete_schedules_by_range(
        self,
        start: datetime,
        end: datetime,
    ) -> int:
        result = await self.uow.session.execute(
            delete(PresentationSchedule).where(
                and_(
                    PresentationSchedule.presentation_date >= start,
                    PresentationSchedule.presentation_date <= end,
                )
            )
        )
        await self.uow.session.flush()
        return result.rowcount

    async def get_schedule_by_range(
        self,
        start: datetime,
        end: datetime,
    ) -> List[PresentationSchedule]:
        result = await self.uow.session.execute(
            select(PresentationSchedule)
            .where(
                and_(
                    PresentationSchedule.presentation_date >= start,
                    PresentationSchedule.presentation_date <= end,
                )
            )
            .order_by(PresentationSchedule.order_index)
            .options(selectinload(PresentationSchedule.project))
        )
        return list(result.scalars().all())

    # =====================================================
    # SCHEDULE - COMPLEMENT
    # =====================================================

    async def get_schedule_by_date(
        self,
        date_utc: datetime,
    ) -> List[PresentationSchedule]:
        start_of_day = date_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day.replace(hour=23, minute=59, second=59)
        return await self.get_schedule_by_range(start_of_day, end_of_day)

    async def get_distinct_schedule_dates(self) -> List[datetime]:
        result = await self.uow.session.execute(
            select(PresentationSchedule.presentation_date).distinct()
        )
        return list(result.scalars().all())

    # =====================================================
    # COMMISSION - CORE
    # =====================================================

    async def create_commission_evaluation(
        self,
        session_id: int,
        commissioner_id: int,
        project_type: str,
        average_score: float,
        comment: Optional[str],
    ) -> CommissionEvaluation:
        evaluation = CommissionEvaluation(
            session_id=session_id,
            commissioner_id=commissioner_id,
            project_type=project_type,
            average_score=average_score,
            comment=comment,
            is_submitted=True,
            submitted_at=datetime.now(timezone.utc),
        )
        self.uow.session.add(evaluation)
        await self.uow.session.flush()
        await self.uow.session.refresh(evaluation)
        return evaluation

    async def create_criterion_score(
        self,
        evaluation_id: int,
        criterion_id: int,
        score: int,
    ) -> CriterionScore:
        obj = CriterionScore(
            evaluation_id=evaluation_id,
            criterion_id=criterion_id,
            score=score,
        )
        self.uow.session.add(obj)
        await self.uow.session.flush()
        await self.uow.session.refresh(obj)
        return obj

    async def get_commission_evaluations_by_session(
        self,
        session_id: int,
    ) -> List[CommissionEvaluation]:
        result = await self.uow.session.execute(
            select(CommissionEvaluation)
            .where(CommissionEvaluation.session_id == session_id)
            .options(
                selectinload(CommissionEvaluation.commissioner),
                selectinload(CommissionEvaluation.criteria_scores).selectinload(
                    CriterionScore.criterion
                ),
            )
        )
        return list(result.scalars().all())

    async def get_commission_evaluation_by_commissioner(
        self,
        session_id: int,
        commissioner_id: int,
    ) -> Optional[CommissionEvaluation]:
        result = await self.uow.session.execute(
            select(CommissionEvaluation).where(
                and_(
                    CommissionEvaluation.session_id == session_id,
                    CommissionEvaluation.commissioner_id == commissioner_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_evaluation_with_scores(
        self,
        evaluation_id: int,
    ) -> Optional[CommissionEvaluation]:
        result = await self.uow.session.execute(
            select(CommissionEvaluation)
            .where(CommissionEvaluation.id == evaluation_id)
            .options(
                selectinload(CommissionEvaluation.commissioner),
                selectinload(CommissionEvaluation.criteria_scores).selectinload(
                    CriterionScore.criterion
                ),
            )
        )
        return result.scalar_one_or_none()

    # =====================================================
    # PEER - CORE
    # =====================================================

    async def create_peer_evaluation(
        self,
        data: PeerEvaluationSubmit,
    ) -> PeerEvaluation:
        evaluation = PeerEvaluation(
            project_id=data.project_id,
            session_id=data.session_id,
            evaluator_id=data.evaluator_id,
            evaluated_id=data.evaluated_id,
            role=data.role,
            criteria_scores=data.scores,
            comment=data.comment,
            is_anonymous=(data.role == EvaluationRole.MEMBER_TO_LEADER),
            is_submitted=True,
            submitted_at=datetime.now(timezone.utc),
        )
        self.uow.session.add(evaluation)
        await self.uow.session.flush()
        await self.uow.session.refresh(evaluation)
        return evaluation

    async def has_peer_evaluation(
        self,
        session_id: int,
        evaluator_id: int,
        evaluated_id: int,
        role: EvaluationRole,
    ) -> bool:
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

    async def get_leader_evaluations_by_members(
        self,
        project_id: int,
        leader_id: int,
    ) -> List[PeerEvaluation]:
        result = await self.uow.session.execute(
            select(PeerEvaluation).where(
                and_(
                    PeerEvaluation.project_id == project_id,
                    PeerEvaluation.evaluated_id == leader_id,
                    PeerEvaluation.role == EvaluationRole.MEMBER_TO_LEADER,
                    PeerEvaluation.evaluator_id != leader_id,
                )
            )
        )
        return list(result.scalars().all())

    async def get_member_evaluations_by_leader(
        self,
        project_id: int,
        member_id: int,
    ) -> List[PeerEvaluation]:
        result = await self.uow.session.execute(
            select(PeerEvaluation).where(
                and_(
                    PeerEvaluation.project_id == project_id,
                    PeerEvaluation.evaluated_id == member_id,
                    PeerEvaluation.role == EvaluationRole.LEADER_TO_MEMBER,
                )
            )
        )
        return list(result.scalars().all())

    # =====================================================
    # PROJECT (READ ONLY)
    # =====================================================

    async def get_project_leader_id(
        self,
        project_id: int,
    ) -> Optional[int]:
        result = await self.uow.session.execute(
            select(Project.author_id).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_project_members(
        self,
        project_id: int,
    ) -> List[int]:
        result = await self.uow.session.execute(
            select(ProjectParticipation.participant_id).where(
                ProjectParticipation.project_id == project_id
            )
        )
        return list(result.scalars().all())

    # =====================================================
    # STATS (SAFE AGGREGATION)
    # =====================================================

    async def get_session_stats(
        self,
        session_id: int,
    ) -> Dict[str, Any]:
        result = await self.uow.session.execute(
            select(
                func.count(func.distinct(CommissionEvaluation.id)),
                func.count(func.distinct(PeerEvaluation.id)),
            )
            .select_from(PresentationSession)
            .outerjoin(
                CommissionEvaluation,
                CommissionEvaluation.session_id == PresentationSession.id,
            )
            .outerjoin(
                PeerEvaluation,
                PeerEvaluation.session_id == PresentationSession.id,
            )
            .where(PresentationSession.id == session_id)
        )

        commission_count, peer_count = result.one()

        return {
            "commission_evaluations": commission_count or 0,
            "peer_evaluations": peer_count or 0,
            "has_commission": (commission_count or 0) > 0,
            "has_peer": (peer_count or 0) > 0,
        }
