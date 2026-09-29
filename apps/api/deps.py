"""FastAPI route dependencies."""


from src.config.settings import get_settings
from src.database.cache import CacheService
from src.database.session import get_db

__all__ = ["CacheService", "get_db", "get_settings"]
