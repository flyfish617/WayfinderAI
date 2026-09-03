from functools import lru_cache
from pathlib import Path

from app.services.auth_service import AuthService
from app.services.redis_service import redis_service
from app.services.trip_service import TripService


@lru_cache
def get_trip_service() -> TripService:
    return TripService(redis_service=redis_service)


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(redis_service=redis_service, upload_dir=Path("uploads/avatars"))
