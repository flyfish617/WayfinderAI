# 注册登录
from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies import get_auth_service
from app.middleware.auth import get_current_user
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
from app.models.trip_model import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=AuthToken)
def login(login_data: UserLogin, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.login(login_data)


@router.post("/register", response_model=AuthToken)
def register(register_data: UserRegister, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.register(register_data)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.get_current_user_info(current_user)


@router.put("/me", response_model=UserResponse)
def update_user_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.update_user_profile(current_user=current_user, update_data=update_data)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    password_data: ChangePassword,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.change_password(current_user=current_user, password_data=password_data)


@router.post("/logout", response_model=MessageResponse)
def logout(
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.logout(current_user)


@router.post("/guest", response_model=GuestSessionResponse)
def get_or_create_guest_session(
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return auth_service.get_or_create_guest_session(current_user)


@router.post("/upload-avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.upload_avatar(current_user=current_user, file=file)
