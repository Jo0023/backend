from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import datetime, timezone, timedelta


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@postgres/backend_db"
    DEBUG: str = "false"

    # Development mode
    DEV_MODE: bool = True  # ← Ajouter cette ligne
    ENVIRONMENT: str = "development"


    # JWT
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200

    # CORS - исправленные настройки для Docker
    CORS_ORIGINS: list = [
        "http://localhost:3000/",
        "http://localhost:5173/",
        "http://localhost:8000",
        "http://localhost:5173",
        "http://backend:8000",
        "http://localhost",
        "http://localhost:8083",
        "http://frontend:80",
        "fpin-projects.ru",
        "http://fpin-projects.ru:1268/",
        "http://fpin-projects.ru:12683/",
    ]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "app.log"
    ENABLE_FILE_LOGGING: bool = True
    ENABLE_CONSOLE_LOGGING: bool = True

    # Timezone - для Saint-Pétersbourg (GMT+3 / MSK)
    TIMEZONE_OFFSET_HOURS: int = 3

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")


settings = Settings()

# ========== CONFIGURATION DU FUSEAU HORAIRE ==========
# Décalage horaire fixe (Saint-Pétersbourg = UTC+3, pas d'heure d'été)
SPB_OFFSET = timedelta(hours=settings.TIMEZONE_OFFSET_HOURS)

# Pour la compatibilité avec le code qui attend SPB_TZ (timezone-aware)
# On crée une classe simple qui imite un timezone
class SimpleTimezone:
    """Simple timezone class for UTC+3 offset"""
    def __init__(self, offset_hours):
        self.offset = timedelta(hours=offset_hours)
    
    def utcoffset(self, dt):
        return self.offset
    
    def tzname(self, dt):
        return f"UTC+{self.offset.seconds//3600}"
    
    def dst(self, dt):
        return timedelta(0)

# Créer un objet timezone pour SPB (compatible avec les fonctions existantes)
SPB_TZ = SimpleTimezone(settings.TIMEZONE_OFFSET_HOURS)


def now_local() -> datetime:
    """Heure actuelle à Saint-Pétersbourg (UTC+3)"""
    return datetime.now(timezone.utc) + SPB_OFFSET


def now_utc() -> datetime:
    """Heure actuelle en UTC"""
    return datetime.now(timezone.utc)


def local_to_utc(dt_local: datetime) -> datetime:
    """
    Convertit une date/heure locale (UTC+3) en UTC
    Si la date est naive, on suppose qu'elle est en UTC+3
    """
    if dt_local.tzinfo is not None:
        # Si déjà timezone-aware, on la convertit
        return dt_local.astimezone(timezone.utc)
    # Si naive, on suppose qu'elle est en UTC+3
    return dt_local - SPB_OFFSET


def utc_to_local(dt_utc: datetime) -> datetime:
    """Convertit une date/heure UTC en locale (UTC+3)"""
    if dt_utc.tzinfo is not None:
        dt_utc = dt_utc.astimezone(timezone.utc)
    return dt_utc + SPB_OFFSET


def get_today_local_start() -> datetime:
    """Début de la journée à Saint-Pétersbourg (00:00)"""
    local_now = now_local()
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_today_local_end() -> datetime:
    """Fin de la journée à Saint-Pétersbourg (23:59:59)"""
    return get_today_local_start().replace(hour=23, minute=59, second=59, microsecond=999999)


def get_today_utc_range() -> tuple[datetime, datetime]:
    """Plage UTC correspondant à la journée locale"""
    start_local = get_today_local_start()
    end_local = get_today_local_end()
    return local_to_utc(start_local), local_to_utc(end_local)


def get_local_date_from_utc(dt_utc: datetime) -> str:
    """Retourne la date locale au format YYYY-MM-DD"""
    local = utc_to_local(dt_utc)
    return local.strftime("%Y-%m-%d")


def get_local_datetime_from_utc(dt_utc: datetime) -> str:
    """Retourne la date/heure locale au format YYYY-MM-DD HH:MM:SS"""
    local = utc_to_local(dt_utc)
    return local.strftime("%Y-%m-%d %H:%M:%S")