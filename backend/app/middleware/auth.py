"""
Authentication middleware with JWT support and guest fallback.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import uuid

import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.observability.logger import default_logger as logger
from app.services.redis_service import redis_service


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate registered users or assign guest sessions."""

    def __init__(self, app, jwt_secret: str = None, jwt_expiry_hours: int = 24):
        super().__init__(app)
        self.jwt_secret = jwt_secret or settings.JWT_SECRET
        self.jwt_expiry_hours = jwt_expiry_hours

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in ["/health", "/api/v1/auth/login", "/api/v1/auth/register"]:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        user_info = None
        need_set_guest_cookie = False
        guest_id = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            user_info = self._verify_jwt_token(token)
            if user_info:
                logger.info("JWT authentication succeeded", extra={"user_id": user_info["user_id"]})
            else:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "success": False,
                        "error_message": "Authentication failed",
                    },
                )

        if not user_info:
            guest_id = request.headers.get("X-Guest-Session") or request.cookies.get("guest_id")
            if guest_id:
                user_info = redis_service.create_or_get_guest_session(guest_id)
                logger.info("Guest authentication succeeded", extra={"guest_id": guest_id})
            else:
                guest_id = str(uuid.uuid4())
                user_info = redis_service.create_or_get_guest_session(guest_id)
                need_set_guest_cookie = True
                logger.info("Created guest session", extra={"guest_id": guest_id})

        request.state.user = user_info
        response = await call_next(request)

        if need_set_guest_cookie and guest_id:
            response.set_cookie(
                key="guest_id",
                value=guest_id,
                max_age=int(timedelta(days=30).total_seconds()),
                httponly=True,
                secure=settings.COOKIE_SECURE,
                samesite="lax",
            )

        return response

    def _verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                logger.info("JWT token expired")
                return None

            return {
                "user_id": payload.get("user_id"),
                "user_type": "registered",
                "username": payload.get("username"),
            }
        except jwt.ExpiredSignatureError:
            logger.info("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token")
            return None
        except Exception:
            logger.error("JWT verification failed", exc_info=True)
            return None

    @staticmethod
    def generate_jwt_token(
        user_id: str,
        username: str,
        jwt_secret: str = None,
        expiry_hours: int = 24,
    ) -> str:
        secret = jwt_secret or settings.JWT_SECRET
        payload = {
            "user_id": user_id,
            "username": username,
            "iat": int(datetime.now().timestamp()),
            "exp": int((datetime.now() + timedelta(hours=expiry_hours)).timestamp()),
        }
        return jwt.encode(payload, secret, algorithm="HS256")


def get_current_user(request: Request) -> Dict[str, Any]:
    if hasattr(request.state, "user"):
        return request.state.user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated user")


def get_user_id(request: Request) -> str:
    user = get_current_user(request)
    return user["user_id"]
