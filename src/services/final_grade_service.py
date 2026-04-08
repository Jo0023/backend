from __future__ import annotations

from src.core.exceptions import NotFoundError, ValidationError
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

    @staticmethod
    def _average(values: list[float]) -> float | None:
        """
        Посчитать среднее значение
        Calculate average value
        """
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    async def _validate_student_role_in_project(
        self,
        project_id: int,
        student_id: int,
        role: str,
    ) -> None:
        """
        Проверить, что студент действительно относится к проекту
        Validate that the student really belongs to the project
        """
        if role not in {"leader", "member"}:
            raise ValidationError("Поле role должно иметь значение 'leader' или 'member'")

        leader_id = await self.access_service.get_project_leader_id(project_id)
        member_ids = await self.access_service.get_project_member_ids(project_id)

        if role == "leader":
            if student_id != leader_id:
                raise ValidationError("Указанный student_id не является руководителем данного проекта")
        else:
            if student_id not in member_ids:
                raise ValidationError("Указанный student_id не является участником данного проекта")

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
        await self.access_service.assert_self_or_project_leader_or_teacher(
            project_id=project_id,
            current_user_id=current_user_id,
            target_user_id=student_id,
        )

        await self._validate_student_role_in_project(
            project_id=project_id,
            student_id=student_id,
            role=role,
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

            all_scores: list[float] = []
            for evaluation in evaluations:
                for row in evaluation.criterion_scores:
                    all_scores.append(float(row.score))

            peer_grade = self._average(all_scores)

            if peer_grade is not None and commission_grade > 0:
                final_grade = round((commission_grade + peer_grade) / 2, 2)
            elif peer_grade is not None:
                final_grade = peer_grade
            else:
                final_grade = round(commission_grade, 2)

        else:
            evaluations = await self.peer_repository.get_member_evaluations_by_leader(
                project_id=project_id,
                member_id=student_id,
                session_id=session.id,
            )

            all_scores: list[float] = []
            for evaluation in evaluations:
                for row in evaluation.criterion_scores:
                    all_scores.append(float(row.score))

            leader_grade = self._average(all_scores)

            if leader_grade is not None and commission_grade > 0:
                final_grade = round((commission_grade + leader_grade) / 2, 2)
            elif leader_grade is not None:
                final_grade = leader_grade
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