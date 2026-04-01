from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.core.exceptions import NotFoundError, ValidationError
from src.repository.config_repository import ConfigRepository
from src.repository.evaluation_schedule_repository import EvaluationScheduleRepository
from src.repository.presentation_session_repository import PresentationSessionRepository
from src.schema.presentation import (
    PeerDeadlineResponse,
    PresentationSessionOpenResponse,
    PresentationSessionResponse,
    PresentationSessionStartResponse,
    ProjectSessionActionResponse,
    ReorderProjectsRequest,
    ReorderProjectsResponse,
    ScheduleForDateItem,
    SchedulePresentationsRequest,
    SchedulePresentationsResponse,
    TodayProjectItem,
)
from src.services.evaluation_access_service import EvaluationAccessService


class PresentationService:
    """
    Сервис управления презентациями и расписанием
    Presentation and scheduling service
    """

    def __init__(
        self,
        schedule_repository: EvaluationScheduleRepository,
        session_repository: PresentationSessionRepository,
        config_repository: ConfigRepository,
        access_service: EvaluationAccessService,
    ) -> None:
        self.schedule_repository = schedule_repository
        self.session_repository = session_repository
        self.config_repository = config_repository
        self.access_service = access_service

    async def schedule_presentations(
        self,
        current_user_id: int,
        data: SchedulePresentationsRequest,
    ) -> SchedulePresentationsResponse:
        """
        Сохранить расписание презентаций
        Save presentation schedule
        """
        await self.access_service.assert_teacher(current_user_id)

        if not data.items:
            raise ValidationError("Список планирования не может быть пустым")

        grouped_by_day: dict[str, list] = {}
        for item in data.items:
            key = item.presentation_date.date().isoformat()
            grouped_by_day.setdefault(key, []).append(item)

        for items_in_day in grouped_by_day.values():
            orders = [item.order_index for item in items_in_day]
            if len(orders) != len(set(orders)):
                raise ValidationError("Порядок выступлений в один день не должен повторяться")

        for _, items_in_day in grouped_by_day.items():
            first_item = items_in_day[0]
            await self.schedule_repository.clear_schedule_for_day(first_item.presentation_date)

            for item in sorted(items_in_day, key=lambda x: x.order_index):
                await self.access_service.get_project_or_raise(item.project_id)
                await self.schedule_repository.schedule_project(
                    project_id=item.project_id,
                    presentation_date=item.presentation_date,
                    order_index=item.order_index,
                )

        return SchedulePresentationsResponse(
            scheduled_count=len(data.items),
            dates=list(grouped_by_day.keys()),
            message="Планирование презентаций сохранено",
        )

    async def get_available_dates(self) -> list[str]:
        """
        Получить все даты, по которым есть расписание
        Get all dates that have schedule entries
        """
        dates = await self.schedule_repository.get_distinct_schedule_days()
        unique = []
        seen = set()

        for dt in dates:
            key = dt.date().isoformat()
            if key not in seen:
                seen.add(key)
                unique.append(key)

        return unique

    async def get_schedule_for_date(self, target_date: datetime) -> list[ScheduleForDateItem]:
        """
        Получить расписание на дату
        Get schedule for a given date
        """
        schedules = await self.schedule_repository.get_schedule_for_day(target_date)

        result: list[ScheduleForDateItem] = []
        for item in schedules:
            result.append(
                ScheduleForDateItem(
                    schedule_id=item.id,
                    project_id=item.project_id,
                    project_name=item.project.name,
                    project_type=item.project.project_type,
                    order_index=item.order_index,
                    status=item.status,
                )
            )

        return result

    async def reorder_projects(
        self,
        current_user_id: int,
        target_date: datetime,
        data: ReorderProjectsRequest,
    ) -> ReorderProjectsResponse:
        """
        Изменить порядок проектов на выбранную дату
        Reorder scheduled projects for a given date
        """
        await self.access_service.assert_teacher(current_user_id)

        schedules = await self.schedule_repository.get_schedule_for_day(target_date)
        scheduled_project_ids = {item.project_id for item in schedules}
        requested_project_ids = set(data.project_ids)

        if scheduled_project_ids != requested_project_ids:
            raise ValidationError("Новый порядок должен содержать ровно те же проекты, что и текущее расписание")

        updated = await self.schedule_repository.reorder_schedule(
            target_day=target_date,
            project_ids=data.project_ids,
        )

        ordered_projects = [
            {"project_id": item.project_id, "order_index": item.order_index}
            for item in updated
        ]

        return ReorderProjectsResponse(
            date=target_date.date().isoformat(),
            ordered_projects=ordered_projects,
            message="Порядок проектов обновлён",
        )

    async def get_today_projects(
        self,
        current_user_id: int,
        tz_name: str = "Europe/Moscow",
    ) -> list[TodayProjectItem]:
        """
        Получить список проектов сегодняшнего дня
        Get today's scheduled projects
        """
        await self.access_service.assert_teacher(current_user_id)

        schedules = await self.schedule_repository.get_today_planned_projects(tz_name=tz_name)

        result: list[TodayProjectItem] = []

        for schedule in schedules:
            session = await self.session_repository.get_today_session(
                project_id=schedule.project_id,
                tz_name=tz_name,
            )

            session_status = session.status if session else schedule.status

            result.append(
                TodayProjectItem(
                    project_id=schedule.project_id,
                    project_name=schedule.project.name,
                    project_type=schedule.project.project_type,
                    session_id=session.id if session else None,
                    status=session_status,
                    order_index=schedule.order_index,
                    presentation_started_at=session.presentation_started_at if session else None,
                    evaluation_opened_at=session.evaluation_opened_at if session else None,
                    evaluation_closes_at=session.evaluation_closes_at if session else None,
                    can_start=(session is None or session.status == "PENDING") and schedule.status == "PENDING",
                    can_open_evaluation=session is not None and session.status == "ACTIVE",
                    can_skip=(session is not None and session.status in ["PENDING", "ACTIVE"]) or schedule.status == "PENDING",
                    can_resume=schedule.status == "SKIPPED",
                )
            )

        return result

    async def get_current_project_session(
        self,
        current_user_id: int,
        project_id: int,
        include_pending: bool = True,
        include_active: bool = True,
    ) -> PresentationSessionResponse | None:
        """
        Получить текущую активную сессию проекта
        Get current project session
        """
        await self.access_service.assert_project_member_or_leader(project_id, current_user_id)

        sessions = await self.session_repository.get_sessions_by_project(project_id)
        allowed_statuses: list[str] = []

        if include_pending:
            allowed_statuses.append("PENDING")
        if include_active:
            allowed_statuses.append("ACTIVE")

        for session in sessions:
            if session.status in allowed_statuses:
                return PresentationSessionResponse.model_validate(session)

        return None

    async def start_presentation(
        self,
        current_user_id: int,
        project_id: int,
    ) -> PresentationSessionStartResponse:
        """
        Запустить презентацию проекта
        Start project presentation
        """
        await self.access_service.assert_teacher(current_user_id)
        await self.access_service.get_project_or_raise(project_id)

        existing = await self.session_repository.get_current_session(project_id)
        if existing:
            raise ValidationError(f"У проекта уже есть активная сессия (ID: {existing.id})")

        config = await self.config_repository.get_or_create_default_config()
        started_at = datetime.now(UTC)

        session = await self.session_repository.create_session(
            project_id=project_id,
            teacher_id=current_user_id,
            presentation_started_at=started_at,
            status="ACTIVE",
        )

        ends_at = started_at + timedelta(minutes=config.presentation_minutes)

        return PresentationSessionStartResponse(
            session_id=session.id,
            status=session.status,
            presentation_started_at=started_at,
            ends_at=ends_at,
            timer_seconds=config.presentation_minutes * 60,
            message="Презентация начата",
        )

    async def open_evaluation(
        self,
        current_user_id: int,
        session_id: int,
    ) -> PresentationSessionOpenResponse:
        """
        Открыть окно оценивания комиссии
        Open commission evaluation window
        """
        await self.access_service.assert_teacher(current_user_id)

        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        if session.status == "EVALUATED":
            raise ValidationError("Сессия уже завершена")
        if session.evaluation_opened_at is not None:
            raise ValidationError("Оценивание уже было открыто для этой сессии")

        config = await self.config_repository.get_or_create_default_config()

        opened_at = datetime.now(UTC)
        closes_at = opened_at + timedelta(minutes=config.commission_evaluation_minutes)

        updated = await self.session_repository.open_evaluation(
            session_id=session_id,
            evaluation_opened_at=opened_at,
            evaluation_closes_at=closes_at,
            status="ACTIVE",
        )
        if not updated:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        return PresentationSessionOpenResponse(
            session_id=updated.id,
            status=updated.status,
            evaluation_opened_at=opened_at,
            closes_at=closes_at,
            timer_seconds=config.commission_evaluation_minutes * 60,
            message="Окно оценивания открыто",
        )

    async def get_session_status(
        self,
        current_user_id: int,
        session_id: int,
    ) -> PresentationSessionResponse:
        """
        Получить статус сессии
        Get session status
        """
        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        await self.access_service.assert_project_member_or_leader(session.project_id, current_user_id)
        return PresentationSessionResponse.model_validate(session)

    async def complete_session(
        self,
        current_user_id: int,
        session_id: int,
    ) -> PresentationSessionResponse:
        """
        Завершить сессию презентации
        Complete presentation session
        """
        await self.access_service.assert_teacher(current_user_id)

        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        updated = await self.session_repository.update_session_status(session_id, "EVALUATED")
        if not updated:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        return PresentationSessionResponse.model_validate(updated)

    async def finalize_session(
        self,
        current_user_id: int,
        session_id: int,
    ) -> ProjectSessionActionResponse:
        """
        Отметить сессию как финальную
        Mark session as final
        """
        await self.access_service.assert_teacher(current_user_id)

        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        if session.status != "EVALUATED":
            raise ValidationError("Финализировать можно только завершённую сессию")

        all_sessions = await self.session_repository.get_sessions_by_project(session.project_id)
        for item in all_sessions:
            if item.id != session_id and item.is_final:
                await self.session_repository.mark_session_as_final(item.id, final=False)

        updated = await self.session_repository.mark_session_as_final(session_id, final=True)
        if not updated:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        return ProjectSessionActionResponse(
            project_id=session.project_id,
            project_name=session.project.name,
            session_id=session.id,
            status=updated.status,
            message="Сессия отмечена как финальная",
        )

    async def skip_project(
        self,
        current_user_id: int,
        project_id: int,
        tz_name: str = "Europe/Moscow",
    ) -> ProjectSessionActionResponse:
        """
        Пропустить проект текущего дня
        Skip today's project
        """
        await self.access_service.assert_teacher(current_user_id)
        project = await self.access_service.get_project_or_raise(project_id)

        local_tz = ZoneInfo(tz_name)
        today_local = datetime.now(local_tz).date()

        session = await self.session_repository.get_today_session(project_id, tz_name=tz_name)
        if session and session.status == "EVALUATED":
            raise ValidationError("Нельзя пропустить уже оценённый проект")

        if session:
            updated_session = await self.session_repository.skip_session(session.id)
            session_id = updated_session.id if updated_session else session.id
            status = updated_session.status if updated_session else "SKIPPED"
        else:
            session_id = None
            status = "SKIPPED"

        schedule = await self.schedule_repository.skip_scheduled_project(project_id, today_local)
        if not schedule and not session:
            raise NotFoundError("На сегодня для этого проекта не найдено ни расписания, ни сессии")

        return ProjectSessionActionResponse(
            project_id=project.id,
            project_name=project.name,
            session_id=session_id,
            status=status,
            message="Проект пропущен",
        )

    async def resume_project(
        self,
        current_user_id: int,
        project_id: int,
        tz_name: str = "Europe/Moscow",
    ) -> ProjectSessionActionResponse:
        """
        Возобновить пропущенный проект
        Resume skipped project
        """
        await self.access_service.assert_teacher(current_user_id)
        project = await self.access_service.get_project_or_raise(project_id)

        local_tz = ZoneInfo(tz_name)
        today_local = datetime.now(local_tz).date()

        session = await self.session_repository.get_today_session(project_id, tz_name=tz_name)
        session_id = None
        status = "PENDING"

        if session:
            resumed_session = await self.session_repository.resume_session(session.id)
            if resumed_session:
                session_id = resumed_session.id
                status = resumed_session.status

        resumed_schedule = await self.schedule_repository.resume_scheduled_project(project_id, today_local)
        if not resumed_schedule and not session_id:
            raise NotFoundError("Для проекта не найдено пропущенное состояние на сегодня")

        return ProjectSessionActionResponse(
            project_id=project.id,
            project_name=project.name,
            session_id=session_id,
            status=status,
            message="Проект возобновлён",
        )

    async def get_peer_deadline(
        self,
        current_user_id: int,
        session_id: int,
    ) -> PeerDeadlineResponse:
        """
        Получить дедлайн взаимной оценки
        Get peer evaluation deadline
        """
        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        await self.access_service.assert_project_member_or_leader(session.project_id, current_user_id)

        if not session.presentation_started_at:
            return PeerDeadlineResponse(
                session_id=session_id,
                deadline=None,
                remaining_days=None,
                is_expired=None,
            )

        config = await self.config_repository.get_or_create_default_config()
        deadline = session.presentation_started_at + timedelta(days=config.peer_evaluation_days)

        now = datetime.now(UTC)
        if now > deadline:
            remaining_days = 0
        else:
            remaining_days = (deadline - now).days

        return PeerDeadlineResponse(
            session_id=session_id,
            deadline=deadline,
            remaining_days=remaining_days,
            is_expired=(remaining_days == 0 if remaining_days is not None else None),
        )