from __future__ import annotations

from src.core.exceptions import NotFoundError, PermissionError, ValidationError
from src.repository.process_metrics_repository import ProcessMetricsRepository
from src.schema.process_metrics import (
    LeaderProcessMetricsResponse,
    MemberProcessMetricsResponse,
)
from src.services.evaluation_access_service import EvaluationAccessService


class ProcessMetricsService:
    """
    Сервис автоматического сбора MVP-метрик процесса
    Service for automatic MVP process metrics collection
    """

    def __init__(
        self,
        metrics_repository: ProcessMetricsRepository,
        access_service: EvaluationAccessService,
    ) -> None:
        self.metrics_repository = metrics_repository
        self.access_service = access_service

    # ========== ВСПОМОГАТЕЛЬНЫЕ ПРОВЕРКИ / ACCESS HELPERS ==========

    async def _assert_member_metrics_access(
        self,
        current_user_id: int,
        project_id: int,
        member_id: int,
    ) -> None:
        """
        Доступ к метрикам участника:
        - сам участник
        - руководитель проекта
        - преподаватель
        Access to member metrics:
        - the member themself
        - project leader
        - teacher
        """
        leader_id = await self.access_service.get_project_leader_id(project_id)
        member_ids = await self.access_service.get_project_member_ids(project_id)
        is_teacher = await self.access_service.is_teacher(current_user_id)

        if member_id == leader_id:
            raise ValidationError("Для руководителя нужно использовать отдельный endpoint метрик")

        if member_id not in member_ids:
            raise NotFoundError(f"Участник с ID {member_id} не найден в проекте {project_id}")

        if is_teacher:
            return

        if current_user_id == member_id:
            return

        if current_user_id == leader_id:
            return

        raise PermissionError("Недостаточно прав для просмотра метрик участника")

    async def _assert_leader_metrics_access(
        self,
        current_user_id: int,
        project_id: int,
    ) -> int:
        """
        Доступ к метрикам руководителя:
        - сам руководитель
        - преподаватель
        Access to leader metrics:
        - leader themself
        - teacher
        """
        leader_id = await self.access_service.get_project_leader_id(project_id)
        is_teacher = await self.access_service.is_teacher(current_user_id)

        if is_teacher:
            return leader_id

        if current_user_id == leader_id:
            return leader_id

        raise PermissionError("Недостаточно прав для просмотра метрик руководителя")

    async def _get_done_column_id_or_raise(self, project_id: int) -> int:
        """
        Проверить, что в проекте есть колонка 'Завершено'
        Ensure the project has 'Завершено' column
        """
        done_column_id = await self.metrics_repository.get_done_column_id(project_id)
        if done_column_id is None:
            raise ValidationError(
                "В проекте не найдена колонка 'Завершено'. "
                "Невозможно рассчитать процессные метрики."
            )
        return done_column_id

    # ========== МЕТРИКИ УЧАСТНИКА / MEMBER METRICS ==========

    async def get_member_process_metrics(
        self,
        current_user_id: int,
        project_id: int,
        member_id: int,
    ) -> MemberProcessMetricsResponse:
        """
        Получить MVP-метрики участника проекта
        Get MVP process metrics for project member
        """
        await self.access_service.get_project_or_raise(project_id)
        await self._assert_member_metrics_access(current_user_id, project_id, member_id)

        done_column_id = await self._get_done_column_id_or_raise(project_id)

        assigned_tasks_count = await self.metrics_repository.count_member_assigned_tasks(
            project_id=project_id,
            member_id=member_id,
        )
        completed_tasks_count = await self.metrics_repository.count_member_completed_tasks(
            project_id=project_id,
            member_id=member_id,
            done_column_id=done_column_id,
        )
        completed_on_time_count = await self.metrics_repository.count_member_completed_on_time_tasks(
            project_id=project_id,
            member_id=member_id,
            done_column_id=done_column_id,
        )
        overdue_unfinished_count = await self.metrics_repository.count_member_overdue_unfinished_tasks(
            project_id=project_id,
            member_id=member_id,
            done_column_id=done_column_id,
        )
        active_days_count = await self.metrics_repository.count_member_active_days(
            project_id=project_id,
            member_id=member_id,
        )

        return MemberProcessMetricsResponse(
            project_id=project_id,
            member_id=member_id,
            assigned_tasks_count=assigned_tasks_count,
            completed_tasks_count=completed_tasks_count,
            completed_on_time_count=completed_on_time_count,
            overdue_unfinished_count=overdue_unfinished_count,
            active_days_count=active_days_count,
        )

    # ========== МЕТРИКИ РУКОВОДИТЕЛЯ / LEADER METRICS ==========

    async def get_leader_process_metrics(
        self,
        current_user_id: int,
        project_id: int,
    ) -> LeaderProcessMetricsResponse:
        """
        Получить MVP-метрики руководителя проекта
        Get MVP process metrics for project leader
        """
        await self.access_service.get_project_or_raise(project_id)
        leader_id = await self._assert_leader_metrics_access(current_user_id, project_id)

        done_column_id = await self._get_done_column_id_or_raise(project_id)

        created_tasks_count = await self.metrics_repository.count_leader_created_tasks(
            project_id=project_id,
            leader_id=leader_id,
        )
        assigned_tasks_count = await self.metrics_repository.count_leader_assigned_tasks(
            project_id=project_id,
            leader_id=leader_id,
        )
        team_completed_tasks_count = await self.metrics_repository.count_team_completed_tasks(
            project_id=project_id,
            leader_id=leader_id,
            done_column_id=done_column_id,
        )
        team_completed_on_time_rate = await self.metrics_repository.calculate_team_completed_on_time_rate(
            project_id=project_id,
            leader_id=leader_id,
            done_column_id=done_column_id,
        )
        team_balance_index = await self.metrics_repository.calculate_team_balance_index(
            project_id=project_id,
            leader_id=leader_id,
        )

        return LeaderProcessMetricsResponse(
            project_id=project_id,
            leader_id=leader_id,
            created_tasks_count=created_tasks_count,
            assigned_tasks_count=assigned_tasks_count,
            team_completed_tasks_count=team_completed_tasks_count,
            team_completed_on_time_rate=team_completed_on_time_rate,
            team_balance_index=team_balance_index,
        )