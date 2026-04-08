from __future__ import annotations

from src.repository.commission_evaluation_repository import CommissionEvaluationRepository
from src.repository.peer_evaluation_repository import PeerEvaluationRepository
from src.repository.presentation_session_repository import PresentationSessionRepository
from src.schema.final_grade import ProjectEvaluationStatus
from src.services.evaluation_access_service import EvaluationAccessService


class ProjectEvaluationStatusService:
    """
    Сервис сводного статуса оценивания проекта
    Service for aggregated project evaluation status
    """

    def __init__(
        self,
        session_repository: PresentationSessionRepository,
        commission_repository: CommissionEvaluationRepository,
        peer_repository: PeerEvaluationRepository,
        access_service: EvaluationAccessService,
    ) -> None:
        self.session_repository = session_repository
        self.commission_repository = commission_repository
        self.peer_repository = peer_repository
        self.access_service = access_service

    async def get_project_evaluation_status(
        self,
        current_user_id: int,
        project_id: int,
    ) -> ProjectEvaluationStatus:
        """
        Получить сводный статус оценивания проекта
        Get aggregated evaluation status for project
        """
        await self.access_service.assert_project_member_or_leader_or_teacher(project_id, current_user_id)
        project = await self.access_service.get_project_or_raise(project_id)

        session = await self.session_repository.get_current_session(project_id)

        if not session:
            session = await self.session_repository.get_final_session(project_id)

        if not session:
            session = await self.session_repository.get_latest_evaluated_session(project_id)

        if not session:
            return ProjectEvaluationStatus(
                project_id=project.id,
                project_name=project.name,
                session_id=None,
                session_status="NO_SESSION",
                commission_evaluations_count=0,
                peer_evaluations_count=0,
                is_complete=False,
                can_be_finalized=False,
            )

        commission_count = await self.commission_repository.count_commission_evaluations_by_session(session.id)
        peer_count = await self.peer_repository.count_peer_evaluations_by_session(session.id)

        can_be_finalized = (
            session.status == "EVALUATED"
            and commission_count > 0
            and peer_count > 0
        )

        is_complete = can_be_finalized

        return ProjectEvaluationStatus(
            project_id=project.id,
            project_name=project.name,
            session_id=session.id,
            session_status=session.status,
            commission_evaluations_count=commission_count,
            peer_evaluations_count=peer_count,
            is_complete=is_complete,
            can_be_finalized=can_be_finalized,
        )