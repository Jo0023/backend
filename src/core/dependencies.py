from __future__ import annotations

from typing import TYPE_CHECKING


from src.core.audit_context import set_audit_context
from src.core.container import get_auth_service, get_user_repository
from src.core.config import settings
from fastapi import Depends, HTTPException, Request, status, Header

from src.core.audit_context import set_audit_context
from src.core.container import (
    get_auth_service,
    get_permission_repository,
)
from src.core.logging_config import get_logger
from src.core.security import oauth2_scheme

if TYPE_CHECKING:
    from src.model.models import User
    from src.repository.user_repository import UserRepository
    from src.repository.permission_repository import PermissionRepository
    from src.services.auth_service import AuthService


async def get_current_user(
    x_test_user_id: int | None = Header(default=None, alias="X-Test-User-Id"),
    token: str | None = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    """
    Получить текущего пользователя.
    В режиме разработки можно подставлять пользователя через заголовок X-Test-User-Id.
    Get current user.
    In development mode, user can be overridden with X-Test-User-Id header.
    """
    logger = get_logger(__name__)

    if settings.ENVIRONMENT != "production" and x_test_user_id is not None:
        logger.info(f"get_current_user called - DEVELOPMENT TEST MODE, X-Test-User-Id={x_test_user_id}")

        user = await user_repository.get_by_id(x_test_user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"Тестовый пользователь с ID {x_test_user_id} не найден",
            )

        return user

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user = await auth_service.get_current_user(token)
    except HTTPException as e:
        logger.warning(f"Failed to get current user - Status: {e.status_code}, Detail: {e.detail}")
        raise
    else:
        logger.debug(f"Successfully retrieved current user: {user.email} (ID: {user.id})")
        return user


def permission_required(permission: str):
    async def permission_dependency(
        current_user: User = Depends(get_current_user),
        permission_repository: PermissionRepository = Depends(get_permission_repository),
        auth_service: AuthService = Depends(get_auth_service),
    ):
        permission_obj = await permission_repository.get_by_name(permission)
        if not permission_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permission '{permission}' not found",
            )

        permissions = await auth_service.get_all_user_permissions(current_user)

        if permission in permissions:
            return current_user
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )

    return permission_dependency


async def get_current_user_no_exception(
    x_test_user_id: int | None = Header(default=None, alias="X-Test-User-Id"),
    token: str | None = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User | None:
    """
    Получить текущего пользователя без исключения.
    Get current user without raising exception.
    """
    logger = get_logger(__name__)

    if settings.ENVIRONMENT != "production" and x_test_user_id is not None:
        user = await user_repository.get_by_id(x_test_user_id)
        if not user:
            logger.debug(f"DEV auth bypass failed: user_id={x_test_user_id} not found")
            return None
        return user

    if not token:
        return None

    try:
        user = await auth_service.get_current_user(token)
    except HTTPException as e:
        logger.debug(f"Failed to get current user (no exception) - Status: {e.status_code}")
        return None
    else:
        logger.debug(f"Successfully retrieved current user (no exception): {user.email} (ID: {user.id})")
        return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Получить текущего активного пользователя.
    Get current active user.
    """
    return current_user


async def get_current_super_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Получить текущего суперпользователя.
    Get current super user.
    """
    return current_user


async def setup_audit(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Установить контекст аудита.
    Set audit context.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    set_audit_context(
        user_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )