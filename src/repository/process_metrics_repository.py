from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Date, and_, cast, func, select

from src.core.uow import IUnitOfWork
from src.model.kanban_models import Column, Task, TaskAssignee, TaskHistory
from src.model.models import ProjectParticipation


class ProcessMetricsRepository:
    """
    Репозиторий автоматического сбора процессных метрик / Process metrics repository

    ВАЖНО:
    - учитываются только основные задачи / only main tasks are used
    - подзадачи в MVP не учитываются / subtasks are ignored in MVP
    - задача считается завершённой, если она хотя бы один раз попала в колонку 'Завершено'
      / task is considered completed if it reached 'Завершено' at least once
    """

    DONE_COLUMN_NAME = "Завершено"

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ / HELPER METHODS ==========

    async def get_done_column_id(self, project_id: int) -> int | None:
        """
        Получить ID финальной колонки 'Завершено' в рамках проекта
        Get 'Завершено' column ID for the project
        """
        result = await self.uow.session.execute(
            select(Column.id).where(
                and_(
                    Column.project_id == project_id,
                    func.lower(Column.name) == self.DONE_COLUMN_NAME.lower(),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_project_member_ids(self, project_id: int, leader_id: int) -> list[int]:
        """
        Получить ID участников проекта без руководителя
        Get project member IDs excluding leader
        """
        result = await self.uow.session.execute(
            select(ProjectParticipation.participant_id).where(
                ProjectParticipation.project_id == project_id
            )
        )
        participant_ids = list(result.scalars().all())
        return [participant_id for participant_id in participant_ids if participant_id != leader_id]

    def _done_tasks_subquery(self, done_column_id: int):
        """
        Подзапрос: все задачи, которые хотя бы один раз были переведены в 'Завершено'
        Subquery: tasks that reached 'Завершено' at least once
        """
        return (
            select(TaskHistory.task_id)
            .where(
                and_(
                    TaskHistory.change_type == "move",
                    TaskHistory.new_column_id == done_column_id,
                )
            )
            .distinct()
            .subquery()
        )

    def _first_done_at_subquery(self, done_column_id: int):
        """
        Подзапрос: первое время попадания задачи в 'Завершено'
        Subquery: first timestamp when task reached 'Завершено'
        """
        return (
            select(
                TaskHistory.task_id.label("task_id"),
                func.min(TaskHistory.created_at).label("first_done_at"),
            )
            .where(
                and_(
                    TaskHistory.change_type == "move",
                    TaskHistory.new_column_id == done_column_id,
                )
            )
            .group_by(TaskHistory.task_id)
            .subquery()
        )

    # ========== МЕТРИКИ УЧАСТНИКА / MEMBER METRICS ==========

    async def count_member_assigned_tasks(self, project_id: int, member_id: int) -> int:
        """
        Количество задач проекта, назначенных участнику
        Count tasks assigned to the member in the project
        """
        result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    TaskAssignee.user_id == member_id,
                )
            )
        )
        return int(result.scalar_one() or 0)

    async def count_member_completed_tasks(
        self,
        project_id: int,
        member_id: int,
        done_column_id: int,
    ) -> int:
        """
        Количество назначенных участнику задач, достигших 'Завершено'
        Count assigned tasks completed by reaching 'Завершено'
        """
        done_tasks = self._done_tasks_subquery(done_column_id)

        result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .join(done_tasks, done_tasks.c.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    TaskAssignee.user_id == member_id,
                )
            )
        )
        return int(result.scalar_one() or 0)

    async def count_member_completed_on_time_tasks(
        self,
        project_id: int,
        member_id: int,
        done_column_id: int,
    ) -> int:
        """
        Количество назначенных участнику задач, завершённых в срок
        Count assigned tasks completed on time
        """
        first_done = self._first_done_at_subquery(done_column_id)

        result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .join(first_done, first_done.c.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    TaskAssignee.user_id == member_id,
                    Task.due_date.is_not(None),
                    first_done.c.first_done_at <= Task.due_date,
                )
            )
        )
        return int(result.scalar_one() or 0)

    async def count_member_overdue_unfinished_tasks(
        self,
        project_id: int,
        member_id: int,
        done_column_id: int,
    ) -> int:
        """
        Количество назначенных участнику просроченных и незавершённых задач
        Count assigned overdue unfinished tasks
        """
        done_tasks = self._done_tasks_subquery(done_column_id)
        now = datetime.now(UTC)

        result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .outerjoin(done_tasks, done_tasks.c.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    TaskAssignee.user_id == member_id,
                    Task.due_date.is_not(None),
                    Task.due_date < now,
                    done_tasks.c.task_id.is_(None),
                )
            )
        )
        return int(result.scalar_one() or 0)

    async def count_member_active_days(self, project_id: int, member_id: int) -> int:
        """
        Количество дней активности участника по истории изменений задач проекта
        Count distinct active days by task history actions inside the project
        """
        result = await self.uow.session.execute(
            select(func.count(func.distinct(cast(TaskHistory.created_at, Date))))
            .select_from(TaskHistory)
            .join(Task, Task.id == TaskHistory.task_id)
            .where(
                and_(
                    Task.project_id == project_id,
                    TaskHistory.changed_by_id == member_id,
                )
            )
        )
        return int(result.scalar_one() or 0)

    # ========== МЕТРИКИ РУКОВОДИТЕЛЯ / LEADER METRICS ==========

    async def count_leader_created_tasks(self, project_id: int, leader_id: int) -> int:
        """
        Количество задач проекта, созданных руководителем
        Count tasks created by leader in the project
        """
        result = await self.uow.session.execute(
            select(func.count(Task.id)).where(
                and_(
                    Task.project_id == project_id,
                    Task.created_by_id == leader_id,
                )
            )
        )
        return int(result.scalar_one() or 0)

    async def count_leader_assigned_tasks(self, project_id: int, leader_id: int) -> int:
        """
        Количество задач, созданных руководителем и назначенных хотя бы одному участнику
        Count leader-created tasks assigned to at least one team member
        """
        result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    Task.created_by_id == leader_id,
                    TaskAssignee.user_id != leader_id,
                )
            )
        )
        return int(result.scalar_one() or 0)

    async def count_team_completed_tasks(
        self,
        project_id: int,
        leader_id: int,
        done_column_id: int,
    ) -> int:
        """
        Количество задач команды, созданных руководителем и завершённых
        Count team tasks created by leader and completed
        """
        done_tasks = self._done_tasks_subquery(done_column_id)

        result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .join(done_tasks, done_tasks.c.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    Task.created_by_id == leader_id,
                    TaskAssignee.user_id != leader_id,
                )
            )
        )
        return int(result.scalar_one() or 0)

    async def calculate_team_completed_on_time_rate(
        self,
        project_id: int,
        leader_id: int,
        done_column_id: int,
    ) -> float:
        """
        Процент задач команды, завершённых в срок
        Percentage of team tasks completed on time
        """
        first_done = self._first_done_at_subquery(done_column_id)

        total_result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    Task.created_by_id == leader_id,
                    TaskAssignee.user_id != leader_id,
                    Task.due_date.is_not(None),
                )
            )
        )
        total_tasks_with_due = int(total_result.scalar_one() or 0)

        if total_tasks_with_due == 0:
            return 0.0

        completed_on_time_result = await self.uow.session.execute(
            select(func.count(func.distinct(Task.id)))
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .join(first_done, first_done.c.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    Task.created_by_id == leader_id,
                    TaskAssignee.user_id != leader_id,
                    Task.due_date.is_not(None),
                    first_done.c.first_done_at <= Task.due_date,
                )
            )
        )
        completed_on_time = int(completed_on_time_result.scalar_one() or 0)

        return round((completed_on_time / total_tasks_with_due) * 100, 2)

    async def calculate_team_balance_index(self, project_id: int, leader_id: int) -> float:
        """
        Индекс равномерности распределения задач между участниками команды
        Team workload balance index

        MVP-формула / MVP formula:
        (min_assigned / max_assigned) * 100
        """
        member_ids = await self.get_project_member_ids(project_id, leader_id)
        if not member_ids:
            return 0.0

        result = await self.uow.session.execute(
            select(
                TaskAssignee.user_id,
                func.count(func.distinct(Task.id)).label("assigned_count"),
            )
            .select_from(Task)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .where(
                and_(
                    Task.project_id == project_id,
                    Task.created_by_id == leader_id,
                    TaskAssignee.user_id.in_(member_ids),
                )
            )
            .group_by(TaskAssignee.user_id)
        )

        counts_by_member = {user_id: int(assigned_count) for user_id, assigned_count in result.all()}

        # Добавляем участников без задач / Include members with zero assigned tasks
        all_counts = [counts_by_member.get(member_id, 0) for member_id in member_ids]

        if not all_counts:
            return 0.0

        max_assigned = max(all_counts)
        min_assigned = min(all_counts)

        if max_assigned == 0:
            return 0.0

        return round((min_assigned / max_assigned) * 100, 2)