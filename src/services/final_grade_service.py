from __future__ import annotations

from src.core.exceptions import NotFoundError
from src.repository.commission_evaluation_repository import CommissionEvaluationRepository
from src.repository.peer_evaluation_repository import PeerEvaluationRepository
from src.repository.presentation_session_repository import PresentationSessionRepository
from src.schema.final_grade import FinalGradeResponse
from src.services.evaluation_access_service import EvaluationAccessService


class FinalGradeService:
    """
    Сервис расчёта итоговой оценки
    Final grade calculation service
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

    async def _resolve_reference_session(self, project_id: int):
        """
        Определить сессию для итогового расчёта
        Resolve session used for final grade calculation
        """
        session = await self.session_repository.get_final_session(project_id)
        if session:
            return session

        session = await self.session_repository.get_latest_evaluated_session(project_id)
        if session:
            return session

        raise NotFoundError(f"Для проекта {project_id} нет завершённой сессии для расчёта итоговой оценки")

    @staticmethod
    def _convert_to_5_scale(value: float) -> int:
        """
        Перевести средний балл в пятибалльную шкалу
        Convert score to 5-grade scale
        """
        if value < 2.5:
            return 2
        if value < 3.5:
            return 3
        if value < 4.5:
            return 4
        return 5

    async def calculate_final_grade(
        self,
        current_user_id: int,
        project_id: int,
        student_id: int,
        role: str,
    ) -> FinalGradeResponse:
        """
        Рассчитать итоговую оценку
        Calculate final grade
        """
        await self.access_service.assert_self_or_project_leader(
            project_id=project_id,
            current_user_id=current_user_id,
            target_user_id=student_id,
        )

        session = await self._resolve_reference_session(project_id)

        commission_grade = await self.commission_repository.get_commission_average_by_session(session.id)
        if commission_grade is None:
            commission_grade = 0.0

        peer_grade = None
        leader_grade = None

        if role == "leader":
            evaluations = await self.peer_repository.get_leader_evaluations_by_members(
                project_id=project_id,
                leader_id=student_id,
                session_id=session.id,
            )

            criterion_means: dict[str, list[int]] = {}
            for evaluation in evaluations:
                for row in evaluation.criterion_scores:
                    criterion_means.setdefault(row.criterion.name, []).append(row.score)

            averages = []
            for _, values in criterion_means.items():
                if values:
                    averages.append(sum(values) / len(values))

            peer_grade = round(sum(averages) / len(averages), 2) if averages else None

            if peer_grade is not None and commission_grade > 0:
                final_grade = round((commission_grade + peer_grade) / 2, 2)
            elif peer_grade is not None:
                final_grade = round(peer_grade, 2)
            else:
                final_grade = round(commission_grade, 2)

        else:
            evaluations = await self.peer_repository.get_member_evaluations_by_leader(
                project_id=project_id,
                member_id=student_id,
                session_id=session.id,
            )

            evaluation_averages = []
            for evaluation in evaluations:
                values = [row.score for row in evaluation.criterion_scores]
                if values:
                    evaluation_averages.append(sum(values) / len(values))

            leader_grade = round(sum(evaluation_averages) / len(evaluation_averages), 2) if evaluation_averages else None

            if leader_grade is not None and commission_grade > 0:
                final_grade = round((commission_grade + leader_grade) / 2, 2)
            elif leader_grade is not None:
                final_grade = round(leader_grade, 2)
            else:
                final_grade = round(commission_grade, 2)

        return FinalGradeResponse(
            student_id=student_id,
            project_id=project_id,
            role=role,
            commission_grade=commission_grade,
            peer_grade=peer_grade,
            leader_grade=leader_grade,
            final_grade=final_grade,
            grade_5_scale=self._convert_to_5_scale(final_grade),
        )