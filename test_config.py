from __future__ import annotations

from src.core.config import settings

print(f"DATABASE_URL depuis settings: {settings.DATABASE_URL}")
print(f"DEBUG: {settings.DEBUG}")
print(f"ENVIRONMENT: {settings.ENVIRONMENT}")
