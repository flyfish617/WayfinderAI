from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class UserLogin(BaseModel):
    username: str
    password: str


class UserRegister(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    birthday: Optional[str] = None
    bio: Optional[str] = None
    travel_preferences: Optional[List[str]] = None
    avatar_url: Optional[str] = None


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    user_type: str
    phone: Optional[str] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    birthday: Optional[str] = None
    bio: Optional[str] = None
    travel_preferences: List[str] = Field(default_factory=list)
    avatar_url: Optional[str] = None


class AuthToken(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class GuestSessionResponse(BaseModel):
    user_id: str
    user_type: str
    message: str
    guest_session_id: Optional[str] = None


class AvatarUploadResponse(BaseModel):
    url: str
