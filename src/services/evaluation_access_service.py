from __future__ import annotations

from src.core.exceptions import NotFoundError, PermissionError
from src.repository.project_repository import ProjectRepository
from src.repository.user_repository import UserRepository


class EvaluationAccessService:
    """
    Сервис проверки прав доступа модуля оценки
    Access control service for evaluation module
    """

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

        members: list[int] = []
        for participation in project.participants:
            if participation.participant_id != leader_id:
                members.append(participation.participant_id)

        return members

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

    async def assert_teacher(self, user_id: int) -> None:
        """
        Проверить, что пользователь является преподавателем

        ВАЖНО:
        В текущем backend нет полноценной ролевой политики для преподавателя.
        Здесь используется role_id как минимальная опора.
        Adjust this rule later if your role model becomes stricter.
        """
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"Пользователь с ID {user_id} не найден")

        # Временное, но реальное правило:
        # пользователь должен иметь role_id, отличный от None.
        # При необходимости здесь можно заменить на точную проверку роли преподавателя.
        if user.role_id is None:
            raise PermissionError("Пользователь не может выполнять действия преподавателя")