from __future__ import annotations

from sqlalchemy import select

from src.core.exceptions import NotFoundError, PermissionError
from src.model.models import ProjectParticipation, Role
from src.repository.project_repository import ProjectRepository
from src.repository.user_repository import UserRepository


class EvaluationAccessService:
    """
    Сервис проверки прав доступа модуля оценки
    Access control service for evaluation module

    Логика доступа строится на двух уровнях:
    1. Глобальная роль пользователя (teacher / student / commissioner)
    2. Контекстная роль внутри проекта (leader / member)

    Access logic is based on two levels:
    1. Global role of the user (teacher / student / commissioner)
    2. Context role inside a project (leader / member)
    """

    ROLE_TEACHER = "teacher"
    ROLE_STUDENT = "student"
    ROLE_COMMISSIONER = "commissioner"

    def __init__(
        self,
        project_repository: ProjectRepository,
        user_repository: UserRepository,
    ) -> None:
        self.project_repository = project_repository
        self.user_repository = user_repository

    async def get_project_or_raise(self, project_id: int):
        """
        Получить проект или вызвать ошибку
        Get project or raise error
        """
        project = await self.project_repository.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Проект с ID {project_id} не найден")
        return project

    async def get_user_or_raise(self, user_id: int):
        """
        Получить пользователя или вызвать ошибку
        Get user or raise error
        """
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"Пользователь с ID {user_id} не найден")
        return user

    async def get_user_role_name(self, user_id: int) -> str:
        """
        Получить имя роли пользователя
        Get user role name
        """
        user = await self.get_user_or_raise(user_id)

        result = await self.user_repository.uow.session.execute(
            select(Role.name).where(Role.id == user.role_id)
        )
        role_name = result.scalar_one_or_none()

        if not role_name:
            raise NotFoundError(f"Роль пользователя с ID {user_id} не найдена")

        return role_name

    async def is_teacher(self, user_id: int) -> bool:
        """
        Проверить, является ли пользователь преподавателем
        Check whether user is teacher
        """
        return await self.get_user_role_name(user_id) == self.ROLE_TEACHER

    async def is_student(self, user_id: int) -> bool:
        """
        Проверить, является ли пользователь студентом
        Check whether user is student
        """
        return await self.get_user_role_name(user_id) == self.ROLE_STUDENT

    async def is_commissioner(self, user_id: int) -> bool:
        """
        Проверить, является ли пользователь членом комиссии
        Check whether user is commissioner
        """
        return await self.get_user_role_name(user_id) == self.ROLE_COMMISSIONER

    async def get_project_leader_id(self, project_id: int) -> int:
        """
        Получить ID руководителя проекта
        Get project leader ID
        """
        project = await self.get_project_or_raise(project_id)
        return project.author_id

    async def get_project_member_ids(self, project_id: int) -> list[int]:
        """
        Получить ID участников проекта без руководителя
        Get member IDs excluding project leader
        """
        project = await self.get_project_or_raise(project_id)
        leader_id = project.author_id

        result = await self.project_repository.uow.session.execute(
            select(ProjectParticipation.participant_id).where(
                ProjectParticipation.project_id == project_id
            )
        )
        participant_ids = list(result.scalars().all())

        return [participant_id for participant_id in participant_ids if participant_id != leader_id]

    async def assert_teacher(self, user_id: int) -> None:
        """
        Проверить, что пользователь является преподавателем
        Ensure user is teacher
        """
        if not await self.is_teacher(user_id):
            raise PermissionError("Пользователь не может выполнять действия преподавателя")

    async def assert_commissioner(self, user_id: int) -> None:
        """
        Проверить, что пользователь является членом комиссии
        Ensure user is commissioner
        """
        if not await self.is_commissioner(user_id):
            raise PermissionError("Пользователь не является членом комиссии")

    async def assert_project_leader(self, project_id: int, user_id: int) -> None:
        """
        Проверить, что пользователь является руководителем проекта
        Ensure user is project leader
        """
        leader_id = await self.get_project_leader_id(project_id)
        if leader_id != user_id:
            raise PermissionError("Только руководитель проекта может выполнить это действие")

    async def assert_project_member(self, project_id: int, user_id: int) -> None:
        """
        Проверить, что пользователь является участником проекта
        Ensure user is a project member
        """
        member_ids = await self.get_project_member_ids(project_id)
        if user_id not in member_ids:
            raise PermissionError("Пользователь не является участником проекта")

    async def assert_project_member_or_leader(self, project_id: int, user_id: int) -> None:
        """
        Проверить, что пользователь является участником или руководителем
        Ensure user is either member or leader
        """
        leader_id = await self.get_project_leader_id(project_id)
        member_ids = await self.get_project_member_ids(project_id)

        if user_id != leader_id and user_id not in member_ids:
            raise PermissionError("Пользователь не относится к данному проекту")

    async def assert_project_member_or_leader_or_teacher(self, project_id: int, user_id: int) -> None:
        """
        Проверить, что пользователь является участником, руководителем или преподавателем
        Ensure user is member, leader, or teacher
        """
        if await self.is_teacher(user_id):
            return

        await self.assert_project_member_or_leader(project_id, user_id)

    async def assert_self_or_project_leader(
        self,
        project_id: int,
        current_user_id: int,
        target_user_id: int,
    ) -> None:
        """
        Разрешить доступ самому пользователю или руководителю проекта
        Allow access to the user themself or project leader
        """
        leader_id = await self.get_project_leader_id(project_id)
        if current_user_id != target_user_id and current_user_id != leader_id:
            raise PermissionError("Недостаточно прав для просмотра этих данных")

    async def assert_self_or_project_leader_or_teacher(
        self,
        project_id: int,
        current_user_id: int,
        target_user_id: int,
    ) -> None:
        """
        Разрешить доступ самому пользователю, руководителю проекта или преподавателю
        Allow access to the user themself, project leader, or teacher
        """
        if await self.is_teacher(current_user_id):
            return

        await self.assert_self_or_project_leader(
            project_id=project_id,
            current_user_id=current_user_id,
            target_user_id=target_user_id,
        )