from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.models import PresentationSchedule


class EvaluationScheduleRepository:
    """
    Репозиторий планирования презентаций / Presentation schedule repository

    Отвечает только за работу с таблицей presentation_schedule.
    Handles only persistence logic for presentation_schedule table.
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    @staticmethod
    def _day_bounds_utc(target: date | datetime, tz_name: str = "Europe/Moscow") -> tuple[datetime, datetime]:
        """
        Получить границы локального дня в UTC / Convert local day boundaries to UTC
        """
        local_tz = ZoneInfo(tz_name)

        if isinstance(target, datetime):
            local_date = target.astimezone(local_tz).date() if target.tzinfo else target.date()
        else:
            local_date = target

        start_local = datetime.combine(local_date, time.min, tzinfo=local_tz)
        end_local = datetime.combine(local_date, time.max, tzinfo=local_tz)

        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    async def schedule_project(
        self,
        project_id: int,
        presentation_date: datetime,
        order_index: int,
    ) -> PresentationSchedule:
        """
        Запланировать проект / Schedule a project
        """
        schedule = PresentationSchedule(
            project_id=project_id,
            presentation_date=presentation_date,
            order_index=order_index,
            status="PENDING",
        )
        self.uow.session.add(schedule)
        await self.uow.session.flush()
        await self.uow.session.refresh(schedule)
        return schedule

    async def clear_schedule_for_day(self, target_day: date | datetime) -> int:
        """
        Удалить все записи расписания за день / Delete all schedule entries for a local day
        """
        start_utc, end_utc = self._day_bounds_utc(target_day)

        result = await self.uow.session.execute(
            select(PresentationSchedule).where(
                and_(
                    PresentationSchedule.presentation_date >= start_utc,
                    PresentationSchedule.presentation_date <= end_utc,
                )
            )
        )
        schedules = list(result.scalars().all())

        for schedule in schedules:
            await self.uow.session.delete(schedule)

        await self.uow.session.flush()
        return len(schedules)

    async def get_schedule_for_day(self, target_day: date | datetime) -> list[PresentationSchedule]:
        """
        Получить расписание на день / Get schedule for a local day
        """
        start_utc, end_utc = self._day_bounds_utc(target_day)

        result = await self.uow.session.execute(
            select(PresentationSchedule)
            .where(
                and_(
                    PresentationSchedule.presentation_date >= start_utc,
                    PresentationSchedule.presentation_date <= end_utc,
                )
            )
            .order_by(PresentationSchedule.order_index.asc())
            .options(selectinload(PresentationSchedule.project))
        )
        return list(result.scalars().all())

    async def get_distinct_schedule_days(self) -> list[datetime]:
        """
        Получить все уникальные даты расписания / Get all distinct presentation dates
        """
        result = await self.uow.session.execute(
            select(PresentationSchedule.presentation_date).order_by(PresentationSchedule.presentation_date.asc())
        )
        return list(result.scalars().all())

    async def reorder_schedule(
        self,
        target_day: date | datetime,
        project_ids: list[int],
    ) -> list[PresentationSchedule]:
        """
        Изменить порядок проектов на день / Reorder projects for a local day
        """
        schedules = await self.get_schedule_for_day(target_day)
        schedule_by_project_id = {item.project_id: item for item in schedules}

        for index, project_id in enumerate(project_ids, start=1):
            schedule = schedule_by_project_id.get(project_id)
            if schedule:
                schedule.order_index = index

        await self.uow.session.flush()
        return await self.get_schedule_for_day(target_day)

    async def get_schedule_entry_for_day(
        self,
        project_id: int,
        target_day: date | datetime,
    ) -> PresentationSchedule | None:
        """
        Получить запись расписания проекта за день / Get project schedule entry for a local day
        """
        start_utc, end_utc = self._day_bounds_utc(target_day)

        result = await self.uow.session.execute(
            select(PresentationSchedule)
            .where(
                and_(
                    PresentationSchedule.project_id == project_id,
                    PresentationSchedule.presentation_date >= start_utc,
                    PresentationSchedule.presentation_date <= end_utc,
                )
            )
            .options(selectinload(PresentationSchedule.project))
        )
        return result.scalar_one_or_none()

    async def skip_scheduled_project(
        self,
        project_id: int,
        target_day: date | datetime,
    ) -> PresentationSchedule | None:
        """
        Отметить проект как пропущенный / Mark scheduled project as skipped
        """
        schedule = await self.get_schedule_entry_for_day(project_id, target_day)
        if not schedule:
            return None

        schedule.status = "SKIPPED"
        await self.uow.session.flush()
        await self.uow.session.refresh(schedule)
        return schedule

    async def resume_scheduled_project(
        self,
        project_id: int,
        target_day: date | datetime,
    ) -> PresentationSchedule | None:
        """
        Вернуть пропущенный проект в состояние PENDING / Resume skipped scheduled project
        """
        schedule = await self.get_schedule_entry_for_day(project_id, target_day)
        if not schedule:
            return None

        if schedule.status != "SKIPPED":
            return None

        schedule.status = "PENDING"
        await self.uow.session.flush()
        await self.uow.session.refresh(schedule)
        return schedule

    async def get_today_planned_projects(self, tz_name: str = "Europe/Moscow") -> list[PresentationSchedule]:
        """
        Получить проекты, запланированные на сегодня / Get today's planned projects
        """
        local_tz = ZoneInfo(tz_name)
        today_local = datetime.now(local_tz).date()
        return await self.get_schedule_for_day(today_local)