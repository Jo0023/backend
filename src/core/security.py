from __future__ import annotations

from fastapi.security import OAuth2PasswordBearer
from src.core.config import settings

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token")
# auto_error=False en développement, True en production
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="v1/auth/token",
    auto_error=settings.ENVIRONMENT == "production"
)
