from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.models import PresentationSession


class PresentationSessionRepository:
    """
    Репозиторий сессий презентации / Presentation session repository

    Отвечает только за работу с таблицей presentation_sessions.
    Handles only persistence logic for presentation_sessions table.
    """

    DEFAULT_TIMEZONE = "Europe/Moscow"

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    @classmethod
    def _get_timezone(cls, tz_name: str | None = None) -> ZoneInfo:
        """
        Получить объект временной зоны / Get timezone object
        """
        timezone_name = tz_name or cls.DEFAULT_TIMEZONE
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    @classmethod
    def _day_bounds_utc(
        cls,
        target: date | datetime,
        tz_name: str | None = None,
    ) -> tuple[datetime, datetime]:
        """
        Получить границы локального дня в UTC / Convert local day boundaries to UTC
        """
        local_tz = cls._get_timezone(tz_name)

        if isinstance(target, datetime):
            if target.tzinfo is None:
                local_date = target.date()
            else:
                local_date = target.astimezone(local_tz).date()
        else:
            local_date = target

        start_local = datetime.combine(local_date, time.min, tzinfo=local_tz)
        end_local = datetime.combine(local_date, time.max, tzinfo=local_tz)

        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    async def create_session(
        self,
        project_id: int,
        teacher_id: int,
        presentation_started_at: datetime,
        status: str = "PENDING",
    ) -> PresentationSession:
        """
        Создать новую сессию презентации / Create presentation session
        """
        session = PresentationSession(
            project_id=project_id,
            teacher_id=teacher_id,
            presentation_started_at=presentation_started_at,
            status=status,
        )
        self.uow.session.add(session)
        await self.uow.session.flush()
        await self.uow.session.refresh(session)
        return session

    async def get_session_by_id(self, session_id: int) -> PresentationSession | None:
        """
        Получить сессию по ID / Get session by ID
        """
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
        """
        Получить все сессии проекта / Get all sessions for project
        """
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(PresentationSession.project_id == project_id)
            .order_by(PresentationSession.created_at.desc(), PresentationSession.id.desc())
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return list(result.scalars().all())

    async def get_current_session(self, project_id: int) -> PresentationSession | None:
        """
        Получить текущую активную сессию проекта / Get current active session for project
        """
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.status.in_(["PENDING", "ACTIVE"]),
                )
            )
            .order_by(PresentationSession.created_at.desc(), PresentationSession.id.desc())
            .limit(1)
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return result.scalar_one_or_none()

    async def get_today_session(
        self,
        project_id: int,
        tz_name: str | None = None,
    ) -> PresentationSession | None:
        """
        Получить сегодняшнюю сессию проекта / Get today's session for project
        """
        local_tz = self._get_timezone(tz_name)
        today_local = datetime.now(local_tz).date()
        start_utc, end_utc = self._day_bounds_utc(today_local, tz_name=tz_name)

        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.created_at >= start_utc,
                    PresentationSession.created_at <= end_utc,
                )
            )
            .order_by(PresentationSession.created_at.desc(), PresentationSession.id.desc())
            .limit(1)
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_sessions(self) -> list[PresentationSession]:
        """
        Получить все активные сессии / Get all active sessions
        """
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(PresentationSession.status.in_(["PENDING", "ACTIVE"]))
            .order_by(PresentationSession.created_at.asc(), PresentationSession.id.asc())
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return list(result.scalars().all())

    async def update_session_status(self, session_id: int, status: str) -> PresentationSession | None:
        """
        Обновить статус сессии / Update session status
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            return None

        session.status = status
        await self.uow.session.flush()
        await self.uow.session.refresh(session)
        return session

    async def open_evaluation(
        self,
        session_id: int,
        evaluation_opened_at: datetime,
        evaluation_closes_at: datetime,
        status: str = "ACTIVE",
    ) -> PresentationSession | None:
        """
        Открыть окно оценивания / Open evaluation window
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            return None

        session.evaluation_opened_at = evaluation_opened_at
        session.evaluation_closes_at = evaluation_closes_at
        session.status = status

        await self.uow.session.flush()
        await self.uow.session.refresh(session)
        return session

    async def skip_session(self, session_id: int) -> PresentationSession | None:
        """
        Пометить сессию как пропущенную / Mark session as skipped
        """
        return await self.update_session_status(session_id, "SKIPPED")

    async def resume_session(self, session_id: int) -> PresentationSession | None:
        """
        Вернуть пропущенную сессию в состояние PENDING / Resume skipped session
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            return None

        if session.status != "SKIPPED":
            return None

        session.status = "PENDING"
        await self.uow.session.flush()
        await self.uow.session.refresh(session)
        return session

    async def mark_session_as_final(self, session_id: int, final: bool = True) -> PresentationSession | None:
        """
        Отметить сессию как финальную / Mark session as final
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            return None

        session.is_final = final
        await self.uow.session.flush()
        await self.uow.session.refresh(session)
        return session

    async def get_final_session(self, project_id: int) -> PresentationSession | None:
        """
        Получить финальную сессию проекта / Get final session for project
        """
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.is_final.is_(True),
                )
            )
            .order_by(PresentationSession.created_at.desc(), PresentationSession.id.desc())
            .limit(1)
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_evaluated_session(self, project_id: int) -> PresentationSession | None:
        """
        Получить последнюю завершённую сессию / Get latest evaluated session
        """
        result = await self.uow.session.execute(
            select(PresentationSession)
            .where(
                and_(
                    PresentationSession.project_id == project_id,
                    PresentationSession.status == "EVALUATED",
                )
            )
            .order_by(PresentationSession.created_at.desc(), PresentationSession.id.desc())
            .limit(1)
            .options(
                selectinload(PresentationSession.project),
                selectinload(PresentationSession.teacher),
            )
        )
        return result.scalar_one_or_none()