# src/core/dependencies.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from fastapi import Depends, HTTPException, Request

from src.core.audit_context import set_audit_context
from src.core.logging_config import get_logger
from src.core.config import settings
from src.core.security import oauth2_scheme
from src.model.models import User

# ✅ Définir le logger au niveau du module (avant toutes les fonctions)
logger = get_logger(__name__)


def _create_test_user(user_id: int = 1, role: str = "teacher") -> User:
    """Create a test user for development"""
    logger.info(f"Creating test user: id={user_id}, role={role}")
    
    role_map = {
        "teacher": 1,
        "commission": 2,
        "leader": 3,
        "member": 4
    }
    
    user = User(
        id=user_id,
        email=f"test{user_id}@test.com",
        first_name=f"Test{user_id}",
        middle_name="Dev",
        last_name="User",
        password_hashed="dev_hash",
        role_id=role_map.get(role, 1),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    return user


# =========================================================
# AUTHENTICATION (DEVELOPMENT MODE - COMPLETE BYPASS)
# =========================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> User:
    """Get current user - DEVELOPMENT MODE: always returns test teacher"""
    logger.info("get_current_user called - DEVELOPMENT MODE")
    return _create_test_user(1, "teacher")


async def get_current_user_no_exception(
    token: str = Depends(oauth2_scheme),
) -> User | None:
    """Get current user without exception - DEVELOPMENT MODE: returns test user"""
    logger.info("get_current_user_no_exception called - DEVELOPMENT MODE")
    return _create_test_user(1, "teacher")


# =========================================================
# ROLE-SPECIFIC DEPENDENCIES (DEVELOPMENT MODE)
# =========================================================

async def get_current_teacher(
    token: str = Depends(oauth2_scheme),
) -> User:
    """Get current user with teacher role - DEVELOPMENT MODE: returns teacher"""
    logger.info("get_current_teacher called - DEVELOPMENT MODE")
    return _create_test_user(1, "teacher")


async def get_current_commission(
    token: str = Depends(oauth2_scheme),
) -> User:
    """Get current user with commission role - DEVELOPMENT MODE: returns commission"""
    logger.info("get_current_commission called - DEVELOPMENT MODE")
    return _create_test_user(26, "commission")


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    return current_user


async def get_current_super_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current super user"""
    return current_user


async def setup_audit(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Setup audit context"""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    user_id = current_user.id
    set_audit_context(user_id=user_id, ip_address=ip_address, user_agent=user_agent)