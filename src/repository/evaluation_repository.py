from __future__ import annotations
from datetime import UTC, datetime, timedelta, date

from sqlalchemy import and_, select, update, func
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.models import (
    CommissionEvaluation,
    PeerEvaluation,
    PresentationSession,
    Project,
    ProjectParticipation,
)
from src.schema.evaluation import (
    PeerEvaluationSubmit,
    PresentationSessionCreate,
)
from src.model.criterion_score import CriterionScore


class EvaluationRepository:
    """Repository для модуля оценки / Repository for evaluation module"""

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    # ========== СЕССИИ ПРЕЗЕНТАЦИЙ ==========

    async def create_session(self, session_data: PresentationSessionCreate) -> PresentationSession:
        """Создать новую сессию презентации / Create new presentation session"""
        db_session = PresentationSession(
            project_id=session_data.project_id,
            teacher_id=session_data.teacher_id,
            status="PENDING",
            presentation_started_at=datetime.now(UTC),
        )
        self.uow.session.add(db_session)
        await self.uow.session.flush()
        await self.uow.session.refresh(db_session)
        return db_session

    async def get_session_by_id(self, session_id: int) -> PresentationSession | None:
        """Получить сессию по ID / Get session by ID"""
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(PresentationSession.id == session_id)
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return result.scalar_one_or_none()

    async def get_sessions_by_project(self, project_id: int) -> list[PresentationSession]:
        """Получить все сессии проекта / Get all project sessions"""
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(PresentationSession.project_id == project_id)
            .order_by(PresentationSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_today_sessions(self) -> list[PresentationSession]:
        """Получить сессии за сегодня / Get today's sessions"""
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        result = await self.uow.session.execute(
            select(PresentationSession).where(
                and_(
                    PresentationSession.created_at >= today_start,
                    PresentationSession.created_at <= today_end,
                )
            )
        )
        return list(result.scalars().all())
    
    # ========== GESTION DES PROJETS DU JOUR ==========

    async def get_today_projects_with_sessions(self) -> list[dict]:
        """
        Получить проекты с сессиями pour la journée courante
        Get projects with sessions for current day
        """
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        
        # Récupérer toutes les sessions d'aujourd'hui
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.created_at >= today_start,
                    PresentationSession.created_at <= today_end,
                )
            )
            .order_by(PresentationSession.created_at)
            .options(selectinload(PresentationSession.project))
        )
        sessions = list(result.scalars().all())
        
        # Construire la liste des projets avec leur session
        projects_with_sessions = []
        for session in sessions:
            projects_with_sessions.append({
                "project": session.project,
                "session": session,
                "status": session.status,
                "can_start": session.status == "PENDING",
                "can_open_evaluation": session.status == "ACTIVE",
                "can_skip": session.status in ["PENDING", "ACTIVE"],
                "can_resume": session.status == "SKIPPED",
            })
        
        return projects_with_sessions

    async def get_project_today_session(self, project_id: int) -> PresentationSession | None:
        """Получить сессию проекта aujourd'hui / Get today's session for project"""
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.created_at >= today_start,
                    PresentationSession.created_at <= today_end,
                )
            )
            .order_by(PresentationSession.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def skip_session(self, session_id: int) -> PresentationSession | None:
        """
        Пропустить сессию (статус SKIPPED)
        Skip session (status SKIPPED)
        """
        stmt = (
            update(PresentationSession)
            .where(PresentationSession.id == session_id)
            .values(status="SKIPPED")
            .execution_options(synchronize_session="fetch")
        )
        await self.uow.session.execute(stmt)
        return await self.get_session_by_id(session_id)

    async def resume_session(self, session_id: int) -> PresentationSession | None:
        """
        Возобновить пропущенную сессию (статус PENDING)
        Resume skipped session (status PENDING)
        """
        # Vérifier que la session est SKIPPED
        session = await self.get_session_by_id(session_id)
        if not session:
            return None
        
        if session.status != "SKIPPED":
            return None
        
        stmt = (
            update(PresentationSession)
            .where(PresentationSession.id == session_id)
            .values(status="PENDING")
            .execution_options(synchronize_session="fetch")
        )
        await self.uow.session.execute(stmt)
        return await self.get_session_by_id(session_id)

    async def can_project_be_evaluated(self, project_id: int) -> bool:
        """
        Проверить, может ли проект быть оценён (не EVALUATED)
        Check if project can be evaluated (not EVALUATED)
        """
        session = await self.get_project_today_session(project_id)
        if not session:
            return True
        
        return session.status != "EVALUATED"

    async def get_final_session(self, project_id: int) -> PresentationSession | None:
        """
        Получить финальную сессию проекта (is_final = True)
        Get final session for project
        """
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.is_final == True
                )
            )
            .order_by(PresentationSession.created_at.desc())
            .options(selectinload(PresentationSession.project))
        )
        return result.scalar_one_or_none()

    async def update_session_status(self, session_id: int, status: str) -> PresentationSession | None:
        """Обновить статус сессии / Update session status"""
        stmt = (
            update(PresentationSession)
            .where(PresentationSession.id == session_id)
            .values(status=status)
            .execution_options(synchronize_session="fetch")
        )
        await self.uow.session.execute(stmt)
        return await self.get_session_by_id(session_id)

    async def open_evaluation(self, session_id: int) -> PresentationSession | None:
        """Открыть оценивание pour session"""
        now = datetime.now(UTC)
        closes_at = now + timedelta(minutes=10)  # 10 pour le test sinon 2
        stmt = (
            update(PresentationSession)
            .where(PresentationSession.id == session_id)
            .values(
                evaluation_opened_at=now,
                evaluation_closes_at=closes_at,
                status="ACTIVE",
            )
            .execution_options(synchronize_session="fetch")
        )
        await self.uow.session.execute(stmt)
        return await self.get_session_by_id(session_id)

    # ========== ОЦЕНКИ КОМИССИИ ==========

    async def create_commission_evaluation(
        self,
        session_id: int,
        commissioner_id: int,
        project_type: str,
        average_score: float,
        comment: str | None = None,
    ) -> CommissionEvaluation:
        """Создать оценку комиссии / Create commission evaluation"""
        db_evaluation = CommissionEvaluation(
            session_id=session_id,
            commissioner_id=commissioner_id,
            project_type=project_type,
            comment=comment,
            average_score=average_score,
            is_submitted=True,
            submitted_at=datetime.now(UTC),
        )
        
        self.uow.session.add(db_evaluation)
        await self.uow.session.flush()
        await self.uow.session.refresh(db_evaluation)
        
        return db_evaluation

    async def create_criterion_score(
        self,
        evaluation_id: int,
        criterion_id: int,
        score: int
    ) -> CriterionScore:
        """Создать оценку по критерию / Create criterion score"""
        obj = CriterionScore(
            evaluation_id=evaluation_id,
            criterion_id=criterion_id,
            score=score
        )
        self.uow.session.add(obj)
        await self.uow.session.flush()
        await self.uow.session.refresh(obj)
        return obj

    async def get_commission_evaluations_by_session(self, session_id: int) -> list[CommissionEvaluation]:
        """Получить все оценки комиссии для сессии"""
        result = await self.uow.session.execute(
            select(CommissionEvaluation)
            .where(CommissionEvaluation.session_id == session_id)
            .options(
                selectinload(CommissionEvaluation.commissioner),
                selectinload(CommissionEvaluation.criteria_scores)
                .selectinload(CriterionScore.criterion)
            )
        )
        return list(result.scalars().all())

    async def get_commission_evaluation_by_commissioner(
        self, session_id: int, commissioner_id: int
    ) -> CommissionEvaluation | None:
        """Получить оценку конкретного члена комиссии"""
        result = await self.uow.session.execute(
            select(CommissionEvaluation).where(
                and_(
                    CommissionEvaluation.session_id == session_id,
                    CommissionEvaluation.commissioner_id == commissioner_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_evaluation_with_scores(self, evaluation_id: int) -> CommissionEvaluation | None:
        """Получить оценку комиссии со всеми scores / Get evaluation with scores"""
        result = await self.uow.session.execute(
            select(CommissionEvaluation)
            .where(CommissionEvaluation.id == evaluation_id)
            .options(
                selectinload(CommissionEvaluation.commissioner),
                selectinload(CommissionEvaluation.criteria_scores)
                .selectinload(CriterionScore.criterion)
            )
        )
        return result.scalar_one_or_none()

    # ========== ВЗАИМНЫЕ ОЦЕНКИ ==========

    async def create_peer_evaluation(self, evaluation_data: PeerEvaluationSubmit) -> PeerEvaluation:
        """Создать взаимную оценку / Create peer evaluation"""
        is_anonymous = evaluation_data.role == "member_to_leader"
        db_evaluation = PeerEvaluation(
            project_id=evaluation_data.project_id,
            session_id=evaluation_data.session_id,
            evaluator_id=evaluation_data.evaluator_id,
            evaluated_id=evaluation_data.evaluated_id,
            role=evaluation_data.role,
            criteria_scores=evaluation_data.scores,
            comment=evaluation_data.comment,
            is_anonymous=is_anonymous,
            is_submitted=True,
            submitted_at=datetime.now(UTC),
        )
        self.uow.session.add(db_evaluation)
        await self.uow.session.flush()
        await self.uow.session.refresh(db_evaluation)
        return db_evaluation

    async def get_peer_evaluations_by_project(self, project_id: int) -> list[PeerEvaluation]:
        """Получить все взаимные оценки проекта"""
        result = await self.uow.session.execute(
            select(PeerEvaluation)
            .where(PeerEvaluation.project_id == project_id)
            .order_by(PeerEvaluation.submitted_at.desc())
            .options(
                selectinload(PeerEvaluation.criteria_scores)
                .selectinload(CriterionScore.criterion)  # ← Ajouter ceci
            )

        )
        return list(result.scalars().all())

    async def get_peer_evaluations_by_session(self, session_id: int) -> list[PeerEvaluation]:
        """Получить все взаимные оценки сессии"""
        result = await self.uow.session.execute(
            select(PeerEvaluation).where(PeerEvaluation.session_id == session_id)
            .options(
                selectinload(PeerEvaluation.criteria_scores)
                .selectinload(CriterionScore.criterion)  # ← Ajouter ceci
            )

        )
        return list(result.scalars().all())

    # ========== ВЗАИМНЫЕ ОЦЕНКИ ==========

    async def get_leader_evaluations_by_members(self, project_id: int, leader_id: int) -> list[PeerEvaluation]:
        """Получить оценки руководителя членами команды (анонимные)"""
        result = await self.uow.session.execute(
            select(PeerEvaluation).where(
                and_(
                    PeerEvaluation.project_id == project_id,
                    PeerEvaluation.evaluated_id == leader_id,
                    PeerEvaluation.role == "member_to_leader",
                    PeerEvaluation.evaluator_id != leader_id,
                )
            )
        )
        return list(result.scalars().all())

    async def get_member_evaluations_by_leader(self, project_id: int, member_id: int) -> list[PeerEvaluation]:
        """Получить оценки участника руководителем"""
        result = await self.uow.session.execute(
            select(PeerEvaluation).where(
                and_(
                    PeerEvaluation.project_id == project_id,
                    PeerEvaluation.evaluated_id == member_id,
                    PeerEvaluation.role == "leader_to_member",
                )
            )
        )
        return list(result.scalars().all())

    async def has_submitted_peer_evaluation(
        self, session_id: int, evaluator_id: int, evaluated_id: int, role: str
    ) -> bool:
        """Проверить, отправил ли пользователь оценку"""
        result = await self.uow.session.execute(
            select(PeerEvaluation).where(
                and_(
                    PeerEvaluation.session_id == session_id,
                    PeerEvaluation.evaluator_id == evaluator_id,
                    PeerEvaluation.evaluated_id == evaluated_id,
                    PeerEvaluation.role == role,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    # ========== ПРОВЕРКИ И СТАТИСТИКА ==========

    async def get_project_leader_id(self, project_id: int) -> int | None:
        """Получить ID руководителя проекта / Get project leader ID"""
        result = await self.uow.session.execute(
            select(Project.author_id).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()
    
    async def get_project_members(self, project_id: int) -> list[int]:
        """
        Получить ID всех участников проекта (ИСКЛЮЧАЯ руководителя)
        Get all project member IDs (EXCLUDING the leader)
        """
        leader_id = await self.get_project_leader_id(project_id)
        
        result = await self.uow.session.execute(
            select(ProjectParticipation.participant_id)
            .where(ProjectParticipation.project_id == project_id)
        )
        members = list(result.scalars().all())
        
        if leader_id and leader_id in members:
            members.remove(leader_id)
        return members
 
    async def get_active_sessions(self) -> list[PresentationSession]:
        """
        Получить toutes les sessions actives (PENDING ou ACTIVE)
        Get all active sessions (PENDING or ACTIVE)
        """
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(PresentationSession.status.in_(["PENDING", "ACTIVE"]))
            .order_by(PresentationSession.created_at)
            .options(selectinload(PresentationSession.project))
        )
        return list(result.scalars().all())

    async def get_evaluation_stats(self, session_id: int) -> dict:
        """Получить статистику оценок для сессии"""
        commission_result = await self.uow.session.execute(
            select(CommissionEvaluation).where(CommissionEvaluation.session_id == session_id)
        )
        commission_count = len(list(commission_result.scalars().all()))
        
        peer_result = await self.uow.session.execute(
            select(PeerEvaluation).where(PeerEvaluation.session_id == session_id)
        )
        peer_count = len(list(peer_result.scalars().all()))
        
        return {
            "commission_evaluations": commission_count,
            "peer_evaluations": peer_count,
            "has_commission": commission_count > 0,
            "has_peer": peer_count > 0,
        }