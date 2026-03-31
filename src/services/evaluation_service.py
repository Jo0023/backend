from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, List, Tuple
from enum import Enum
from collections import defaultdict
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

# --- Exceptions ---
from src.core.exceptions import NotFoundError, PermissionError, ValidationError
from src.core.logging_config import get_logger

# --- Repositories ---
from src.repository.evaluation_repository import EvaluationRepository
from src.repository.project_repository import ProjectRepository
from src.repository.user_repository import UserRepository
from src.repository.config_repository import ConfigRepository
from src.repository.rubric_repository import RubricRepository

# --- Schemas ---
from src.schema.evaluation import (
    CommissionEvaluationSubmit,
    CommissionEvaluationResponse,
    PeerEvaluationSubmit,
    PeerEvaluationResponse,
    PeerEvaluationLeaderSummary,
    FinalGradeResponse,
    PresentationSessionCreate,
    PresentationSessionStartResponse,
    PresentationSessionResponse,
    PresentationSessionOpenResponse,
    ProjectEvaluationStatus,
)

from src.core.dynamic_scores import get_scores_model

# =========================================================
# ENUMS
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
    LEADER_TO_MEMBER = "leader_to_member"
    MEMBER_TO_LEADER = "member_to_leader"


class UserRole(str, Enum):
    LEADER = "leader"
    MEMBER = "member"


# =========================================================
# CONSTANTS
# =========================================================

SECONDS_PER_MINUTE = 60
SECONDS_PER_DAY = 86400


# =========================================================
# SERVICE
# =========================================================

class EvaluationService:
    def __init__(
        self,
        evaluation_repository: EvaluationRepository,
        project_repository: ProjectRepository,
        user_repository: UserRepository,
    ):
        self.evaluation_repo = evaluation_repository
        self.project_repo = project_repository
        self.user_repo = user_repository
        self.config_repo = ConfigRepository(self.evaluation_repo.uow)
        self.session = self.evaluation_repo.uow.session
        self.rubric_repo = RubricRepository(self.session)
        self.logger = get_logger(self.__class__.__name__)

    # =========================================================
    # SESSION
    # =========================================================

    async def start_presentation(self, project_id: int, teacher_id: int) -> PresentationSessionStartResponse:
        project = await self._get_project_or_fail(project_id)

        sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        if any(s.status in {SessionStatus.PENDING.value, SessionStatus.ACTIVE.value} for s in sessions):
            raise ValidationError("Active session already exists")

        config = await self.config_repo.get_or_create_default_config()

        async with self.evaluation_repo.uow:
            session = await self.evaluation_repo.create_session(
                PresentationSessionCreate(project_id=project_id, teacher_id=teacher_id)
            )

        return PresentationSessionStartResponse(
            session_id=session.id,
            status=session.status,
            timer_seconds=config.presentation_minutes * SECONDS_PER_MINUTE,
            message="Presentation started",
        )

    async def open_evaluation(self, session_id: int) -> PresentationSessionOpenResponse:
        session = await self._get_session_or_fail(session_id)

        if session.status == SessionStatus.EVALUATED.value:
            raise ValidationError("Session already completed")

        if session.evaluation_opened_at:
            raise ValidationError("Evaluation already opened")

        config = await self.config_repo.get_or_create_default_config()

        async with self.evaluation_repo.uow:
            updated = await self.evaluation_repo.set_evaluation_window(
                session_id, config.commission_evaluation_minutes
            )

        closes_at = updated.evaluation_closes_at or (
            datetime.now(UTC) + timedelta(minutes=10)
        )

        return PresentationSessionOpenResponse(
            session_id=updated.id,
            status=updated.status,
            timer_seconds=config.commission_evaluation_minutes * SECONDS_PER_MINUTE,
            closes_at=closes_at,
            message="Evaluation opened",
        )

# =========================================================
    # PROJECT MANAGEMENT
    # =========================================================

    async def skip_project_session(self, project_id: int, teacher_id: int) -> Dict:
        """
        Skip a project session (mark as SKIPPED)
        """
        self.logger.info(f"Skipping project {project_id}, teacher {teacher_id}")
        
        # Vérifier que le projet existe
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Проект с ID {project_id} не найден")
        
        # Récupérer la session du jour
        session = await self.evaluation_repo.get_project_today_session(project_id)
        if not session:
            raise NotFoundError(f"Не было найдено ни одной сессии для проекта {project_id} сегодня")
        
        # Vérifier que la session peut être skip
        if session.status == SessionStatus.EVALUATED.value:
            raise ValidationError("Нельзя пропустить уже оценённый проект")
        
        if session.status == SessionStatus.SKIPPED.value:
            raise ValidationError("Проект уже пропущен")
        
        # Marquer comme SKIPPED
        async with self.evaluation_repo.uow:
            await self.evaluation_repo.update_session_status(session.id, SessionStatus.SKIPPED.value)
        
        # Également marquer le schedule comme SKIPPED
        from src.core.config import get_today_utc_range
        start_utc, end_utc = get_today_utc_range()
        schedules = await self.evaluation_repo.get_schedule_by_range(start_utc, end_utc)
        
        for schedule in schedules:
            if schedule.project_id == project_id:
                await self.evaluation_repo.update_schedule_status(schedule.id, ScheduleStatus.SKIPPED)
                break
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "session_id": session.id,
            "status": SessionStatus.SKIPPED.value,
            "message": f"Проект '{project.name}' пропущен"
        }

    async def resume_project_session(self, project_id: int, teacher_id: int) -> Dict:
        """
        Resume a skipped project session
        """
        self.logger.info(f"Resuming project {project_id}, teacher {teacher_id}")
        
        # Vérifier que le projet existe
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Проект с ID {project_id} не найден")
        
        # Récupérer la session du jour
        session = await self.evaluation_repo.get_project_today_session(project_id)
        if not session:
            raise NotFoundError(f"Aucune session trouvée pour le projet {project_id} aujourd'hui")
        
        # Vérifier que la session est SKIPPED
        if session.status != SessionStatus.SKIPPED.value:
            raise ValidationError("Только пропущенные проекты можно возобновить")
        
        # Marquer comme PENDING
        async with self.evaluation_repo.uow:
            await self.evaluation_repo.update_session_status(session.id, SessionStatus.PENDING.value)
        
        # Également reprendre le schedule
        from src.core.config import get_today_utc_range
        start_utc, end_utc = get_today_utc_range()
        schedules = await self.evaluation_repo.get_schedule_by_range(start_utc, end_utc)
        
        for schedule in schedules:
            if schedule.project_id == project_id:
                await self.evaluation_repo.update_schedule_status(schedule.id, ScheduleStatus.PENDING)
                break
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "session_id": session.id,
            "status": SessionStatus.PENDING.value,
            "message": f"Проект '{project.name}' возобновлён"
        }

    async def finalize_session(self, session_id: int, teacher_id: int) -> Dict:
        """
        Finalize a session (mark as final)
        """
        self.logger.info(f"Finalizing session {session_id}, teacher {teacher_id}")
        
        session = await self.evaluation_repo.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")
        
        if session.status != SessionStatus.EVALUATED.value:
            raise ValidationError("Только оценённые сессии можно финализировать")
        
        # Démarquer toutes les autres sessions du projet
        all_sessions = await self.evaluation_repo.get_sessions_by_project(session.project_id)
        
        async with self.evaluation_repo.uow:
            for s in all_sessions:
                if s.id != session_id and s.is_final:
                    # Mettre à jour directement via update
                    await self.evaluation_repo.uow.session.execute(
                        update(PresentationSession)
                        .where(PresentationSession.id == s.id)
                        .values(is_final=False)
                    )
            
            # Marquer cette session comme finale
            await self.evaluation_repo.uow.session.execute(
                update(PresentationSession)
                .where(PresentationSession.id == session_id)
                .values(is_final=True)
            )
        
        updated_session = await self.evaluation_repo.get_session_by_id(session_id)
        
        return {
            "session_id": session_id,
            "project_id": session.project_id,
            "is_final": updated_session.is_final if updated_session else True,
            "message": f"Session {session_id} marquée comme finale"
        }
    # =========================================================
    # COMMISSION
    # =========================================================

    async def submit_commission_evaluation(self, data: CommissionEvaluationSubmit) -> CommissionEvaluationResponse:
        session = await self._get_session_or_fail(data.session_id)

        if session.evaluation_closes_at and datetime.now(UTC) > session.evaluation_closes_at:
            raise ValidationError("Evaluation expired")

        if await self._already_submitted_commission(data):
            raise ValidationError("Already submitted")

        project = await self._get_project_or_fail(session.project_id)
        project_type = project.project_type or "product"

        template = await self.rubric_repo.get_active_template(project_type)
        criteria = await self.rubric_repo.get_template_criteria(template.id)

        await self._validate_dynamic_scores(data.scores, project_type)
        self._validate_scores(data.scores, criteria)

        avg = self._compute_weighted_average(data.scores, criteria)

        try:
            async with self.evaluation_repo.uow:
                evaluation = await self.evaluation_repo.create_commission_evaluation(
                    session_id=data.session_id,
                    commissioner_id=data.commissioner_id,
                    project_type=project_type,
                    average_score=avg,
                    comment=data.comment,
                )

                await self._save_scores(evaluation.id, criteria, data.scores)

        except IntegrityError:
            raise ValidationError("Already submitted")

        evaluation = await self.evaluation_repo.get_evaluation_with_scores(evaluation.id)

        return CommissionEvaluationResponse(
            id=evaluation.id,
            session_id=evaluation.session_id,
            commissioner_id=evaluation.commissioner_id,
            scores={c.criterion.name: c.score for c in evaluation.criteria_scores},
            comment=evaluation.comment,
            project_type=evaluation.project_type,
            average_score=evaluation.average_score,
            submitted_at=evaluation.submitted_at,
            is_submitted=evaluation.is_submitted,
        )
    
    async def get_commission_evaluations(self, session_id: int) -> List[CommissionEvaluationResponse]:
        """Get all commission evaluations for a session"""
        self.logger.info(f"Getting commission evaluations for session {session_id}")
        
        evaluations = await self.evaluation_repo.get_commission_by_session(session_id)
        
        return [
            CommissionEvaluationResponse(
                id=e.id,
                session_id=e.session_id,
                commissioner_id=e.commissioner_id,
                scores={cs.criterion.name: cs.score for cs in e.criteria_scores},
                comment=e.comment,
                project_type=e.project_type,
                average_score=e.average_score,
                submitted_at=e.submitted_at,
                is_submitted=e.is_submitted,
            )
            for e in evaluations
        ]
    
    async def get_commission_average(self, session_id: int) -> Optional[float]:
        """Get average commission score for a session"""
        evaluations = await self.evaluation_repo.get_commission_evaluations_by_session(session_id)
        if not evaluations:
            return None
        return round(sum(e.average_score for e in evaluations) / len(evaluations), 2)


    # =========================================================
    # PEER
    # =========================================================

    async def submit_peer_evaluation(self, data: PeerEvaluationSubmit) -> PeerEvaluationResponse:
        session = await self._get_session_or_fail(data.session_id)

        if session.status != SessionStatus.EVALUATED.value:
            raise ValidationError("Peer evaluation not available")

        if data.evaluator_id == data.evaluated_id:
            raise ValidationError("Cannot evaluate yourself")

        if not await self._within_deadline(session):
            raise ValidationError("Deadline expired")

        await self._validate_peer_permissions(data)
        await self._validate_peer_scores(data)

        if await self.evaluation_repo.has_peer_evaluation(
            data.session_id, data.evaluator_id, data.evaluated_id, data.role
        ):
            raise ValidationError("Already submitted")

        async with self.evaluation_repo.uow:
            evaluation = await self.evaluation_repo.create_peer_evaluation(data)

        return PeerEvaluationResponse(
            id=evaluation.id,
            project_id=evaluation.project_id,
            session_id=evaluation.session_id,
            evaluator_id=evaluation.evaluator_id,
            evaluated_id=evaluation.evaluated_id,
            role=evaluation.role,
            scores=evaluation.criteria_scores,
            comment=evaluation.comment,
            is_anonymous=evaluation.is_anonymous,
            submitted_at=evaluation.submitted_at,
            is_submitted=evaluation.is_submitted,
        )

    # =========================================================
    # FINAL GRADE
    # =========================================================

    async def calculate_final_grade(self, project_id: int, student_id: int, role: UserRole) -> FinalGradeResponse:
        session = await self._get_latest_session(project_id)

        commission_avg = await self.get_commission_average(session.id) or 0

        if role == UserRole.LEADER:
            final, peer_avg = await self._leader_grade(project_id, student_id, session.id, commission_avg)
            leader_grade = None
        else:
            final, leader_grade = await self._member_grade(project_id, student_id, session.id, commission_avg)
            peer_avg = None

        return FinalGradeResponse(
            student_id=student_id,
            project_id=project_id,
            role=role.value,
            auto_grade=None,
            commission_grade=commission_avg,
            peer_grade=peer_avg,
            leader_grade=leader_grade,
            final_grade=final,
            grade_5_scale=self._to_5(final),
        )

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================

    async def _get_project_or_fail(self, project_id: int):
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        return project

    async def _get_session_or_fail(self, session_id: int):
        session = await self.evaluation_repo.get_session_by_id(session_id)
        if not session:
            raise NotFoundError("Session not found")
        return session

    async def _already_submitted_commission(self, data):
        return await self.evaluation_repo.get_commission_evaluation_by_commissioner(
            session_id=data.session_id,
            commissioner_id=data.commissioner_id,
        ) is not None

    async def _validate_dynamic_scores(self, scores: Dict, project_type: str):
        model = await get_scores_model(self.session, project_type)
        model(**scores)

    def _validate_scores(self, scores: Dict[str, int], criteria):
        expected = {c.name for c in criteria}
        if set(scores.keys()) != expected:
            raise ValidationError("Invalid criteria")

        for k, v in scores.items():
            if v is None or not (1 <= v <= 5):
                raise ValidationError(f"Invalid score for {k}")

    def _compute_weighted_average(self, scores, criteria) -> float:
        total_weight = sum(c.weight for c in criteria)
        if total_weight == 0:
            raise ValidationError("Invalid weight config")

        return round(sum(scores[c.name] * c.weight for c in criteria) / total_weight, 2)

    async def _save_scores(self, evaluation_id: int, criteria, scores):
        for c in criteria:
            await self.evaluation_repo.create_criterion_score(
                evaluation_id, c.id, scores[c.name]
            )

    async def _within_deadline(self, session) -> bool:
        config = await self.config_repo.get_or_create_default_config()
        deadline = session.presentation_started_at + timedelta(days=config.peer_evaluation_days)
        return datetime.now(UTC) <= deadline

    async def _validate_peer_permissions(self, data: PeerEvaluationSubmit):
        leader_id = await self.evaluation_repo.get_project_leader_id(data.project_id)
        members = await self.evaluation_repo.get_project_members(data.project_id)

        if data.role == EvaluationRole.LEADER_TO_MEMBER.value:
            if data.evaluator_id != leader_id:
                raise PermissionError("Only leader can evaluate members")
            if data.evaluated_id not in members:
                raise ValidationError("Invalid member")

        elif data.role == EvaluationRole.MEMBER_TO_LEADER.value:
            if data.evaluated_id != leader_id:
                raise ValidationError("Can only evaluate leader")
            if data.evaluator_id not in members:
                raise PermissionError("Only members allowed")

        else:
            raise ValidationError("Invalid role")

    async def _validate_peer_scores(self, data: PeerEvaluationSubmit):
        template_name = (
            "peer_member_to_leader"
            if data.role == EvaluationRole.MEMBER_TO_LEADER.value
            else "peer_leader_to_member"
        )

        template = await self.rubric_repo.get_active_template(template_name)
        criteria = await self.rubric_repo.get_template_criteria(template.id)

        self._validate_scores(data.scores, criteria)


    async def get_current_session(self, project_id: int) -> Optional[PresentationSessionResponse]:
        """Get current active session for a project"""
        sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        for session in sessions:
            if session.status in [SessionStatus.PENDING.value, SessionStatus.ACTIVE.value]:
                return await self.get_session_status(session.id)
        return None
    
    """""
    async def get_current_session(self, project_id: int):
        sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        session = next((s for s in sessions if s.is_final), None)
        if not session:
            session = next((s for s in sessions if s.status == SessionStatus.EVALUATED.value), None)
        if not session:
            raise NotFoundError("No completed sessions")
        return session
    """
    async def _leader_grade(self, project_id, student_id, session_id, commission_avg):
        feedback = await self.get_leader_feedback(project_id, student_id, session_id)
        if not feedback.averages:
            return commission_avg, None

        avg = round(sum(feedback.averages.values()) / len(feedback.averages), 2)
        return round((commission_avg + avg) / 2, 2), avg

    async def _member_grade(self, project_id, student_id, session_id, commission_avg):
        feedback = await self.get_member_feedback(project_id, student_id, session_id)
        if not feedback:
            return commission_avg, None

        scores = [sum(f["scores"].values()) / len(f["scores"]) for f in feedback if f["scores"]]
        if not scores:
            return commission_avg, None

        leader_avg = round(sum(scores) / len(scores), 2)
        return round((commission_avg + leader_avg) / 2, 2), leader_avg

    def _to_5(self, value: float) -> int:
        if value < 2.5:
            return 2
        if value < 3.5:
            return 3
        if value < 4.5:
            return 4
        return 5

    # =========================================================
    # SESSION (COMPLEMENT - HOMOGENEOUS)
    # =========================================================

    async def complete_session(self, session_id: int) -> PresentationSessionResponse:
        """Mark a session as EVALUATED (atomic)."""
        await self._get_session_or_fail(session_id)
        async with self.evaluation_repo.uow:
            await self.evaluation_repo.update_session_status(
                session_id, SessionStatus.EVALUATED.value
            )
        return await self.get_session_status(session_id)

    async def get_session_status(self, session_id: int) -> PresentationSessionResponse:
        session = await self._get_session_or_fail(session_id)
        return PresentationSessionResponse(
            id=session.id,
            project_id=session.project_id,
            teacher_id=session.teacher_id,
            status=session.status,
            presentation_started_at=session.presentation_started_at,
            evaluation_opened_at=session.evaluation_opened_at,
            evaluation_closes_at=session.evaluation_closes_at,
            created_at=session.created_at,
        )

    # =========================================================
    # DEADLINES (COMPLEMENT - HOMOGENEOUS)
    # =========================================================

    async def can_submit_peer_evaluation(self, session_id: int) -> bool:
        session = await self._get_session_or_fail(session_id)
        if not session.presentation_started_at:
            return False
        deadline = await self._compute_deadline(session)
        return datetime.now(UTC) <= deadline

    async def get_peer_evaluation_deadline(self, session_id: int) -> Optional[datetime]:
        session = await self._get_session_or_fail(session_id)
        if not session.presentation_started_at:
            return None
        return await self._compute_deadline(session)

    async def get_remaining_peer_evaluation_days(self, session_id: int) -> Optional[int]:
        deadline = await self.get_peer_evaluation_deadline(session_id)
        if not deadline:
            return None
        seconds_left = (deadline - datetime.now(UTC)).total_seconds()
        if seconds_left <= 0:
            return 0
        return int(seconds_left // SECONDS_PER_DAY)

    async def _compute_deadline(self, session) -> datetime:
        config = await self.config_repo.get_or_create_default_config()
        return session.presentation_started_at + timedelta(days=config.peer_evaluation_days)

    # =========================================================
    # PROJECT STATUS (COMPLEMENT - HOMOGENEOUS)
    # =========================================================

    async def get_project_evaluation_status(self, project_id: int) -> ProjectEvaluationStatus:
        project = await self._get_project_or_fail(project_id)

        sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        session = next((s for s in sessions if s.is_final), None)
        if not session:
            session = next((s for s in sessions if s.status == SessionStatus.EVALUATED.value), None)

        if session:
            stats = await self.evaluation_repo.get_session_stats(session.id)
            commission_count = stats["commission_evaluations"]
            peer_count = stats["peer_evaluations"]
            session_status = session.status
        else:
            commission_count = 0
            peer_count = 0
            session_status = None

        can_be_finalized = (
            session is not None
            and session.status == SessionStatus.EVALUATED.value
            and commission_count > 0
            and peer_count > 0
        )

        return ProjectEvaluationStatus(
            project_id=project_id,
            project_name=project.name,
            session_id=session.id if session else None,
            session_status=session_status,
            commission_evaluations_count=commission_count,
            peer_evaluations_count=peer_count,
            is_complete=can_be_finalized,
            can_be_finalized=can_be_finalized,
        )

    # =========================================================
    # CONFIGURATION (COMPLEMENT - HOMOGENEOUS)
    # =========================================================

    async def get_evaluation_config(self) -> Dict:
        config = await self.config_repo.get_or_create_default_config()
        return {
            "peer_evaluation_days": config.peer_evaluation_days,
            "commission_evaluation_minutes": config.commission_evaluation_minutes,
            "presentation_minutes": config.presentation_minutes,
            "evaluation_opening_minutes": config.evaluation_opening_minutes,
            "is_active": config.is_active,
            "updated_at": config.updated_at,
        }

    async def update_evaluation_config(
        self,
        peer_evaluation_days: Optional[int] = None,
        commission_evaluation_minutes: Optional[int] = None,
        presentation_minutes: Optional[int] = None,
        evaluation_opening_minutes: Optional[int] = None,
        teacher_id: Optional[int] = None,
    ) -> Dict:
        if peer_evaluation_days is not None and peer_evaluation_days < 1:
            raise ValidationError("peer_evaluation_days must be >= 1")
        if commission_evaluation_minutes is not None and commission_evaluation_minutes < 1:
            raise ValidationError("commission_evaluation_minutes must be >= 1")
        if presentation_minutes is not None and presentation_minutes < 1:
            raise ValidationError("presentation_minutes must be >= 1")
        if evaluation_opening_minutes is not None and evaluation_opening_minutes < 1:
            raise ValidationError("evaluation_opening_minutes must be >= 1")

        async with self.evaluation_repo.uow:
            await self.config_repo.update_config(
                peer_evaluation_days=peer_evaluation_days,
                commission_evaluation_minutes=commission_evaluation_minutes,
                presentation_minutes=presentation_minutes,
                evaluation_opening_minutes=evaluation_opening_minutes,
                updated_by=teacher_id,
            )

        return await self.get_evaluation_config()

    # =========================================================
    # SCHEDULING (COMPLEMENT - HOMOGENEOUS)
    # =========================================================

    async def schedule_projects(self, schedule_data: List[Dict], teacher_id: int) -> Dict:
        """Schedule projects for multiple days"""
        grouped: Dict[str, List[Dict]] = {}
        for item in schedule_data:
            grouped.setdefault(item["date"], []).append(item)

        async with self.evaluation_repo.uow:
            for date_str, items in grouped.items():
                try:
                    date_obj = datetime.fromisoformat(date_str)
                except ValueError:
                    raise ValidationError(f"Invalid date format: {date_str}")

                start_of_day = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = start_of_day.replace(hour=23, minute=59, second=59)
                await self.evaluation_repo.delete_schedules_by_range(start_of_day, end_of_day)

                for item in items:
                    await self.evaluation_repo.create_schedule(
                        project_id=item["project_id"],
                        presentation_date=date_obj,
                        order_index=item["order"],
                    )

        return {
            "message": f"{len(schedule_data)} projects scheduled",
            "dates": list(grouped.keys()),
        }

    async def get_today_projects(self) -> List[Dict]:
        """
        Get projects scheduled for today with their statuses
        (Business logic moved from repository to service)
        """
        self.logger.info("Getting today's planned projects")
        
        # 1. Obtenir la plage UTC pour aujourd'hui (heure locale)
        from src.core.config import get_today_utc_range, utc_to_local
        
        start_utc, end_utc = get_today_utc_range()
        
        # 2. Récupérer les schedules dans cette plage (repository pur)
        schedules = await self.evaluation_repo.get_schedule_by_range(start_utc, end_utc)
        
        # 3. Enrichir avec les sessions et les flags business (service layer)
        projects_with_status = []
        for schedule in schedules:
            project = schedule.project
            
            # Récupérer la session du projet pour aujourd'hui
            session = await self.evaluation_repo.get_session_by_project_and_date_range(
                project.id, start_utc, end_utc
            )
            
            # Convertir la date en locale pour l'affichage
            presentation_date_local = utc_to_local(schedule.presentation_date).date()
            
            # Calculer les flags business
            can_start = (not session or session.status == SessionStatus.PENDING) and schedule.status == ScheduleStatus.PENDING
            can_open_evaluation = session and session.status == SessionStatus.ACTIVE
            can_skip = (session and session.status in [SessionStatus.PENDING, SessionStatus.ACTIVE]) or schedule.status == ScheduleStatus.PENDING
            can_resume = schedule.status == ScheduleStatus.SKIPPED
            
            projects_with_status.append({
                "schedule_id": schedule.id,
                "project": project.id,
                "session": session.id if session else None,
                "presentation_date": presentation_date_local.isoformat(),
                "status": session.status if session else schedule.status,
                "order_index": schedule.order_index,
                "can_start": can_start,
                "can_open_evaluation": can_open_evaluation,
                "can_skip": can_skip,
                "can_resume": can_resume,
            })
        
        return projects_with_status

    async def get_schedule_by_date(self, date: str) -> List[Dict]:
        try:
            date_obj = datetime.fromisoformat(date)
        except ValueError:
            raise ValidationError(f"Invalid date format: {date}")

        schedules = await self.evaluation_repo.get_schedule_by_date(date_obj)

        return [
            {
                "schedule_id": s.id,
                "project_id": s.project_id,
                "project_name": s.project.name,
                "project_type": s.project.project_type,
                "order": s.order_index,
                "status": s.status,
            }
            for s in schedules
        ]

    async def get_available_dates(self) -> List[str]:
        # Delegated to repository to avoid leaking SQL in service layer
        dates = await self.evaluation_repo.get_distinct_schedule_dates()
        return [d.date().isoformat() for d in dates]
    

    async def reorder_projects(self, date: str, project_order: List[int], teacher_id: int) -> Dict:
        """
        Reorder projects for a specific date
        """
        self.logger.info(f"Reordering projects for date {date}, teacher {teacher_id}")
        
        try:
            date_obj = datetime.fromisoformat(date)
        except ValueError:
            raise ValidationError(f"Invalid date format: {date}")
        
        async with self.evaluation_repo.uow:
            # Récupérer les schedules existants
            schedules = await self.evaluation_repo.get_schedule_by_date(date_obj)
            
            # Créer un mapping project_id -> schedule
            schedule_by_project = {s.project_id: s for s in schedules}
            
            # Mettre à jour les ordres
            for index, project_id in enumerate(project_order, start=1):
                if project_id in schedule_by_project:
                    await self.evaluation_repo.update_schedule_order(
                        schedule_by_project[project_id].id, index
                    )
        
        return {
            "message": f"Order updated for {len(project_order)} projects",
            "date": date,
            "projects": [
                {"id": pid, "order": idx + 1} 
                for idx, pid in enumerate(project_order)
            ]
        }

    # =========================================================
    # PUBLIC HELPERS (unchanged API)
    # =========================================================

    async def get_leader_feedback(self, project_id: int, leader_id: int, session_id: int = None) -> PeerEvaluationLeaderSummary:
        evaluations = await self.evaluation_repo.get_leader_evaluations_by_members(project_id, leader_id)

        if session_id:
            evaluations = [e for e in evaluations if e.session_id == session_id]

        if not evaluations:
            return PeerEvaluationLeaderSummary(averages={}, comments=[], evaluations_count=0)

        scores_sum = defaultdict(int)
        scores_count = defaultdict(int)

        for e in evaluations:
            for k, v in e.criteria_scores.items():
                scores_sum[k] += v
                scores_count[k] += 1

        averages = {k: round(scores_sum[k] / scores_count[k], 2) for k in scores_sum}
        comments = [e.comment for e in evaluations if e.comment]

        return PeerEvaluationLeaderSummary(
            averages=averages,
            comments=comments,
            evaluations_count=len(evaluations),
        )

    async def get_member_feedback(self, project_id: int, member_id: int, session_id: int = None) -> List[Dict]:
        evaluations = await self.evaluation_repo.get_member_evaluations_by_leader(project_id, member_id)

        if session_id:
            evaluations = [e for e in evaluations if e.session_id == session_id]

        return [
            {
                "scores": e.criteria_scores,
                "comment": e.comment,
                "submitted_at": e.submitted_at.isoformat() if e.submitted_at else None,
                "evaluation_id": e.id,
            }
            for e in evaluations
        ]
    
    # FINAL GRADE HELPERS
    # =========================================================

    async def _get_latest_session(self, project_id: int):
        """Get the latest session for final grade calculation"""
        sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        session = next((s for s in sessions if s.is_final), None)
        if not session:
            session = next((s for s in sessions if s.status == SessionStatus.EVALUATED.value), None)
        if not session:
            raise NotFoundError("No completed sessions")
        return session