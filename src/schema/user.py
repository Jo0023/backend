from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from src.util.validator import validate_telegram_username



class UserBase(BaseModel):
    """Базовая схема пользователя"""

    email: EmailStr | None = None
    first_name: str = Field(..., min_length=1, max_length=100)  # Использует Field
    middle_name: str = Field(..., min_length=1, max_length=100)  # Использует Field
    last_name: str | None = Field(None, min_length=1, max_length=100)  # Использует Field
    telegram: Optional[str] = Field(  # Использует Field
        None,
        min_length=6,
        max_length=33,
        pattern=r'^@\w{5,32}$',
        description="Telegram username в формате @username (5-32 символа, только буквы, цифры и подчеркивания)"
    )

    @field_validator('telegram')
    @classmethod
    def validate_telegram(cls, v: Optional[str]) -> Optional[str]:
        """Валидация Telegram username"""
        return validate_telegram_username(v)

class UserCreate(UserBase):
    """Схема для создания пользователя"""

    password_string: str
    isu_number: int | None = None
    telegram: Optional[str] | None = None

    @field_validator('telegram')
    @classmethod
    def validate_telegram_on_create(cls, v: Optional[str]) -> Optional[str]:
        """Дополнительная валидация при создании"""
        validated = validate_telegram_username(v)

        if validated:
            username_part = validated[1:].lower()
            forbidden_names = {'admin', 'support', 'help', 'service', 'bot', 'system'}

            if username_part in forbidden_names:
                raise ValueError(f"Username '{validated}' зарезервирован")

        return validated


class UserFull(UserBase):
    """Полная схема пользователя"""

    id: int
    isu_number: int | None = None
    tg_nickname: str | None = None
    telegram: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""

    email: EmailStr | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    isu_number: int | None = None
    tg_nickname: str | None = None
    telegram: Optional[str] = Field(
        None,
        min_length=6,
        max_length=33,
        pattern=r'^@\w{5,32}$',
        description="Telegram username в формате @username"
    )
    itmo_id: int | None = None

    @field_validator('telegram')
    @classmethod
    def validate_telegram_update(cls, v: Optional[str]) -> Optional[str]:
        """Валидация Telegram при обновлении"""
        return validate_telegram_username(v)

class UserResponse(BaseModel):
    """Схема ответа с пользователем"""

    id: int
    email: EmailStr

    class Config:
        from_attributes = True


class UserListItem(BaseModel):
    """Схема элемента списка пользователей"""

    id: int
    email: EmailStr
    first_name: str
    middle_name: str
    last_name: str | None = None
    isu_number: int | None = None
    telegram: Optional[str] = None
    tg_nickname: str | None = None
    itmo_id: int | None = None
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Схема ответа со списком пользователей"""

    items: list[UserListItem]
    total: int
    page: int
    limit: int
    total_pages: int
