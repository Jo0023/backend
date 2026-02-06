from __future__ import annotations

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """Схема токена для аутентификации"""

    access_token: str
    token_type: str


class PasswordResetRequest(BaseModel):
    """Схема для запроса сброса пароля"""

    email: EmailStr


class PasswordResetResponse(BaseModel):
    """Схема для ответа при запросе сброса"""

    message: str = "Письмо отправлено, если адрес существует"


class PasswordResetConfirm(BaseModel):
    """Схема для подтверждения нового пароля"""

    token: str
    new_password: str
