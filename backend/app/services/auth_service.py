from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException, UploadFile, status

from app.middleware.auth import AuthMiddleware
from app.models.auth_model import (
    AuthToken,
    AvatarUploadResponse,
    ChangePassword,
    GuestSessionResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.observability.logger import default_logger as logger
from app.services.redis_service import RedisService


class AuthService:
    """Application service for auth and profile workflows."""

    def __init__(self, redis_service: RedisService, upload_dir: Path) -> None:
        self.redis_service = redis_service
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def login(self, login_data: UserLogin) -> AuthToken:
        user = self.redis_service.verify_user(login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        access_token = AuthMiddleware.generate_jwt_token(
            user_id=user["user_id"],
            username=user["username"],
        )
        return AuthToken(
            access_token=access_token,
            token_type="Bearer",
            user=self._build_user_response(user, user_type="registered"),
        )

    def register(self, register_data: UserRegister) -> AuthToken:
        user_id = str(uuid.uuid4())
        try:
            self.redis_service.create_user(
                user_id=user_id,
                username=register_data.username,
                password=register_data.password,
                phone=None,
                gender="other",
                birthday=None,
                bio=None,
                travel_preferences=[],
                avatar_url=None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed",
            ) from exc

        access_token = AuthMiddleware.generate_jwt_token(
            user_id=user_id,
            username=register_data.username,
        )
        return AuthToken(
            access_token=access_token,
            token_type="Bearer",
            user=UserResponse(user_id=user_id, username=register_data.username, user_type="registered"),
        )

    def get_current_user_info(self, current_user: Dict[str, Any]) -> UserResponse:
        if current_user.get("user_type") == "guest":
            return UserResponse(
                user_id=current_user.get("user_id", ""),
                username="guest",
                user_type="guest",
            )

        username = current_user.get("username", "")
        user = self.redis_service.get_user_by_username(username)
        if not user:
            return UserResponse(
                user_id=current_user["user_id"],
                username=username,
                user_type="registered",
            )
        return self._build_user_response(user, user_type=current_user.get("user_type", "registered"))

    def update_user_profile(self, current_user: Dict[str, Any], update_data: UserUpdate) -> UserResponse:
        self._ensure_registered_user(current_user)
        username = current_user.get("username", "")
        try:
            user = self.redis_service.update_user(
                username=username,
                phone=update_data.phone,
                gender=update_data.gender,
                birthday=update_data.birthday,
                bio=update_data.bio,
                travel_preferences=update_data.travel_preferences,
                avatar_url=update_data.avatar_url,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Profile update failed",
            ) from exc

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._build_user_response(user, user_type="registered")

    def change_password(self, current_user: Dict[str, Any], password_data: ChangePassword) -> dict[str, str]:
        self._ensure_registered_user(current_user)
        username = current_user.get("username", "")
        try:
            self.redis_service.update_password(
                username=username,
                old_password=password_data.old_password,
                new_password=password_data.new_password,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed",
            ) from exc
        return {"message": "Password changed successfully"}

    def logout(self, current_user: Dict[str, Any]) -> dict[str, str]:
        logger.info(
            "User logout",
            extra={
                "user_id": current_user.get("user_id", "unknown"),
                "user_type": current_user.get("user_type", "unknown"),
            },
        )
        return {"message": "Logout successful"}

    def get_or_create_guest_session(self, current_user: Dict[str, Any]) -> GuestSessionResponse:
        if current_user.get("user_type") == "guest":
            return GuestSessionResponse(
                user_id=current_user.get("user_id", ""),
                guest_session_id=current_user.get("guest_id"),
                user_type="guest",
                message="Guest session active",
            )

        return GuestSessionResponse(
            user_id=current_user.get("user_id", ""),
            user_type="registered",
            message="Current user is authenticated",
        )

    async def upload_avatar(self, current_user: Dict[str, Any], file: UploadFile) -> AvatarUploadResponse:
        self._ensure_registered_user(current_user)

        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image files are allowed")

        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        unique_filename = f"{current_user['user_id']}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = self.upload_dir / unique_filename

        contents = await file.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size exceeds 2MB")

        try:
            with open(file_path, "wb") as file_handle:
                file_handle.write(contents)
        except OSError as exc:
            logger.error("Avatar upload failed", extra={"user_id": current_user["user_id"], "error": str(exc)})
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Avatar upload failed",
            ) from exc

        return AvatarUploadResponse(url=f"/uploads/avatars/{unique_filename}")

    def _ensure_registered_user(self, current_user: Dict[str, Any]) -> None:
        if current_user.get("user_type") == "guest":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Guest users must register before modifying account data",
            )

    def _build_user_response(self, user: Dict[str, Any], user_type: str) -> UserResponse:
        return UserResponse(
            user_id=user["user_id"],
            username=user["username"],
            user_type=user_type,
            phone=user.get("phone") or None,
            gender=user.get("gender") or None,
            birthday=user.get("birthday") or None,
            bio=user.get("bio") or None,
            travel_preferences=user.get("travel_preferences") or [],
            avatar_url=user.get("avatar_url") or None,
        )
